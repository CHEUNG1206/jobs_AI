"""Local site for live search and master-CV upload.

The page is static until this process is running. The refetch button and
the upload form post here, then the tracker is rebuilt from the new
listings or the uploaded text.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from career_agent import DATA, ROOT, load_json, run, save_json, score_job
from cv_store import load_master_cv, parse_upload, save_upload
from job_search import merge_catalogue, profile_corpus, search_all, to_catalogue_job
from logging_setup import build_logger

LOG_PATH = DATA / "career-agent.log"
HOST = "127.0.0.1"
PORT = 8765
LIVE_LIMIT = 18


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
    live = [to_catalogue_job(raw, profile, corpus) for raw in meta["jobs"]]
    live.sort(key=lambda job: score_job(job)["score"], reverse=True)
    catalogue = load_json(DATA / "jobs.json")
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
    """Save the master CV and rebuild drafts so they quote it."""
    logger = build_logger(LOG_PATH)
    payload = save_upload(filename, raw)
    profile = attach_upload_to_profile(load_json(DATA / "profile.json"), payload)
    save_json(DATA / "profile.json", profile)
    run()
    logger.info("Stored master CV %s (%s characters)", payload["filename"], payload["characters"])
    return {
        "ok": True,
        "message": f"已讀取 {payload['filename']}，共 {payload['characters']} 字。草稿已改為引用這份履歷。",
        "filename": payload["filename"],
        "characters": payload["characters"],
    }


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
            content_type = "text/html; charset=utf-8" if target.suffix == ".html" else "text/plain; charset=utf-8"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def attach_upload_to_profile(profile: dict, payload: dict) -> dict:
    """Remember the upload, and fill a blank email only when the CV states one."""
    if payload.get("email") and not profile.get("contact", {}).get("email"):
        profile.setdefault("contact", {})["email"] = payload["email"]
    profile["masterCv"] = {
        "filename": payload.get("filename", ""),
        "uploadedAt": payload.get("uploadedAt", ""),
    }
    return profile


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), make_handler())
    print(f"http://{HOST}:{PORT}/web/index.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
