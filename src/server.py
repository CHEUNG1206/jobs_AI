"""Local site for live search and master-CV upload.

The page is static until this process is running. The refetch button and
the upload form post here, then the tracker is rebuilt from the new
listings or the uploaded text. Review marks and download confirmation
are written to data/tracker.json. Tailored files stay on this machine.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from career_agent import APPLICATIONS, DATA, ROOT, confirm_tracker, load_json, run, save_json, score_job, set_tracker_status
from cv_store import load_master_cv, parse_upload, save_upload
from job_search import (
    backfill_catalogue,
    card_rank,
    enrich_raw_job,
    merge_catalogue,
    profile_corpus,
    search_all,
    to_catalogue_job,
)
from logging_setup import build_logger

LOG_PATH = DATA / "career-agent.log"
HOST = "127.0.0.1"
PORT = 8765
LIVE_LIMIT = 18
DETAIL_LIMIT = 12
JOB_ID = re.compile(r"[A-Za-z0-9_-]+")
DRAFT_FILES = {"cv.md", "cover-letter.md"}


def apply_refetch(keywords: str, search_fn=search_all) -> dict:
    """Search the boards, keep audited jobs, and rebuild the page.

    A board that returns nothing is reported. Previous live cards stay
    put when every board fails, so a network error does not empty the list.
    """
    logger = build_logger(LOG_PATH)
    meta = search_fn(keywords)
    logger.info("Live search %s counts %s", meta.get("keywords"), meta.get("counts"))
    for error in meta.get("errors") or []:
        logger.warning("Live search error: %s", error)
    if not meta.get("jobs"):
        message = "這次沒有取回職缺。" + format_search(meta)
        return {"ok": False, "message": message, "errors": meta.get("errors") or []}

    profile = load_json(DATA / "profile.json")
    corpus = profile_corpus(profile, load_master_cv())
    catalogue = load_json(DATA / "jobs.json")
    # Curated rows keep their hand scores, but a JobsDB or JobStreet body
    # replaces the card before a letter is written.
    curated_filled = backfill_catalogue(catalogue.get("jobs") or [], profile, corpus, limit=0)
    logger.info("Filled %s curated advertisements", curated_filled)
    ranked = sorted(meta["jobs"], key=card_rank, reverse=True)
    filled = 0
    for raw in ranked[:DETAIL_LIMIT]:
        before = len((raw.get("full_text") or "").strip())
        enrich_raw_job(raw)
        if before < 280 <= len((raw.get("full_text") or "").strip()):
            filled += 1
    logger.info("Read %s full advertisements out of %s detail requests", filled, min(DETAIL_LIMIT, len(ranked)))
    live = [to_catalogue_job(raw, profile, corpus) for raw in ranked]
    live.sort(key=lambda job: score_job(job)["score"], reverse=True)
    merged = merge_catalogue(catalogue, live[:LIVE_LIMIT], meta)
    save_json(DATA / "jobs.json", merged)
    report = run()
    logger.info("Refetch added %s live cards", merged["lastLiveSearch"]["added"])
    return {
        "ok": True,
        "message": "搜尋完成。" + format_search(merged["lastLiveSearch"]),
        "added": merged["lastLiveSearch"]["added"],
        "drafts": report["drafts"],
        "errors": meta.get("errors") or [],
    }


def apply_upload(filename: str, raw: bytes) -> dict:
    """Save the master CV beside the project and rebuild drafts so they quote it.

    The upload is not copied into data/profile.json. That file is shared
    with the repository, and the CV stays on this machine.
    """
    logger = build_logger(LOG_PATH)
    payload = save_upload(filename, raw)
    run()
    logger.info("Stored master CV %s (%s characters)", payload["filename"], payload["characters"])
    return {
        "ok": True,
        "message": f"已讀取 {payload['filename']}，共 {payload['characters']} 字。草稿已改為引用這份履歷。",
        "filename": payload["filename"],
        "characters": payload["characters"],
    }


def apply_status(job_id: str, status: str) -> dict:
    """Persist a review mark, then rebuild the page from that file."""
    logger = build_logger(LOG_PATH)
    require_job_id(job_id)
    set_tracker_status(job_id, status)
    run()
    logger.info("Wrote tracker status %s for %s", status, job_id)
    return {"ok": True, "status": status, "message": "已寫入 data/tracker.json。"}


def apply_confirm(job_id: str) -> dict:
    """Allow downloads only after the letter file exists and a person checks it."""
    logger = build_logger(LOG_PATH)
    require_job_id(job_id)
    letter = APPLICATIONS / job_id / "cover-letter.md"
    if not letter.is_file():
        raise ValueError("還沒有求職信可以確認。請先重新搜尋並讀到完整職缺。")
    confirm_tracker(job_id)
    run()
    logger.info("Confirmed draft %s", job_id)
    return {"ok": True, "message": "已確認。現在可以下載這份履歷和求職信。"}


def apply_preview(job_id: str) -> dict:
    """Return the letter text without unlocking the download."""
    require_job_id(job_id)
    letter = APPLICATIONS / job_id / "cover-letter.md"
    if not letter.is_file():
        raise ValueError("還沒有求職信可以預覽。")
    return {"ok": True, "text": letter.read_text(encoding="utf-8")}


def require_job_id(job_id: str) -> None:
    if not job_id or not JOB_ID.fullmatch(job_id):
        raise ValueError("找不到這個職位。")


def draft_download_block(relative: str, tracker: dict | None = None) -> str | None:
    """Refuse a tailored CV or letter until tracker.json records confirmation.

    Fit notes and the blank master CV stay readable. Those files are not
    the application a person would send.
    """
    parts = Path(relative).parts
    if len(parts) != 3 or parts[0] != "applications" or parts[2] not in DRAFT_FILES:
        return None
    if parts[1] == "master":
        return None
    if tracker is None:
        tracker_path = DATA / "tracker.json"
        tracker = load_json(tracker_path) if tracker_path.exists() else {"items": {}}
    item = (tracker.get("items") or {}).get(parts[1]) or {}
    if item.get("confirmed"):
        return None
    return "請先確認這份草稿，才能下載。"


def format_search(meta: dict) -> str:
    counts = meta.get("counts") or {}
    count_text = "，".join(f"{name} {number} 則" for name, number in counts.items())
    added = meta.get("added")
    added_text = f"新加入 {added} 則。" if added is not None else ""
    error_text = ""
    if meta.get("errors"):
        error_text = "未能連上：" + "；".join(meta["errors"])
    return " ".join(part for part in (count_text + "。" if count_text else "", added_text, error_text) if part)


def make_handler(refetch_fn=apply_refetch, upload_fn=apply_upload):
    """Build a request handler closed over the search and upload functions."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path in {"/", "/web", "/web/"}:
                path = "/web/index.html"
            if path == "/api/status":
                master = load_master_cv()
                self._send_json(
                    {
                        "ok": True,
                        "masterCv": master.get("filename") if master else "",
                    }
                )
                return
            self._send_file(path)

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            try:
                if path == "/api/refetch":
                    keywords = ""
                    if body:
                        keywords = json.loads(body.decode("utf-8") or "{}").get("keywords", "")
                    self._send_json(refetch_fn(keywords))
                    return
                if path == "/api/cv":
                    filename, data = parse_upload(body, self.headers.get("Content-Type", ""))
                    self._send_json(upload_fn(filename, data))
                    return
                if path in {"/api/tracker", "/api/confirm", "/api/preview"}:
                    payload = json.loads(body.decode("utf-8") or "{}") if body else {}
                    job_id = payload.get("id", "")
                    if path == "/api/tracker":
                        self._send_json(apply_status(job_id, payload.get("status", "")))
                    elif path == "/api/confirm":
                        self._send_json(apply_confirm(job_id))
                    else:
                        self._send_json(apply_preview(job_id))
                    return
            except Exception as exc:
                self._send_json({"ok": False, "message": str(exc)}, status=400)
                return
            self._send_json({"ok": False, "message": "找不到這個操作。"}, status=404)

        def log_message(self, fmt, *args):
            # The career logger already records search and upload. Skip the
            # default stderr line for every static file.
            return

        def _send_json(self, payload, status=200):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _send_file(self, path):
            relative = path.lstrip("/")
            target = (ROOT / relative).resolve()
            allowed = target.is_file() and (
                str(target).startswith(str((ROOT / "web").resolve()))
                or str(target).startswith(str((ROOT / "applications").resolve()))
            )
            if not allowed:
                self._send_json({"ok": False, "message": "找不到頁面。"}, status=404)
                return
            block = draft_download_block(str(target.relative_to(ROOT)))
            if block:
                self._send_json({"ok": False, "message": block}, status=403)
                return
            content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "text/plain; charset=utf-8"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), make_handler())
    print(f"http://{HOST}:{PORT}/web/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
