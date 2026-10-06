"""Job-search workflow for CHEUNG Yuk Yuen.

The assignment splits this work into four steps: search from saved
criteria, drop closed or already-submitted roles, score the rest against
the recorded profile, and draft a CV and cover letter only where the
listing is still worth a human review.

Nothing here is submitted to an employer. Contact details and education
stay blank until the applicant fills them in.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cv_store import load_master_cv, matching_sentences
from logging_setup import build_logger

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
APPLICATIONS = ROOT / "applications"
WEB = ROOT / "web"
LOG_PATH = DATA / "career-agent.log"

CLOSED_STATUSES = {"closed", "expired"}
TRACKER_STATUSES = {"ready_for_review", "applied", "skipped"}


def has_full_listing(job: dict) -> bool:
    """A draft is allowed only when the employer text is long enough to quote."""
    return len((job.get("fullText") or "").strip()) >= 280


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def score_job(job: dict) -> dict:
    """Sum the audited points stored on the listing.

    Base, evidence, and gap points are written by hand next to the source
    text so a later reader can see each adjustment. Closed and expired
    roles stay at zero and are not dressed up as matches.
    """
    if job["listingStatus"] in CLOSED_STATUSES:
        return {"score": 0, "lines": ["Listing is closed or expired, so it is not scored."]}

    lines = [f"Base {job['baseScore']} for an AI-related listing that was still readable."]
    total = job["baseScore"]
    for item in job["evidence"]:
        total += item["points"]
        lines.append(f"+{item['points']}: {item['note']}")
    for item in job["gaps"]:
        total += item["points"]
        sign = "+" if item["points"] >= 0 else ""
        lines.append(f"{sign}{item['points']}: {item['note']}")
    total = max(0, min(100, total))
    lines.append(f"Total {total}")
    return {"score": total, "lines": lines}


def experience_map(profile: dict) -> dict:
    return {item["id"]: item["text"] for item in profile["experience"]}


def ordered_experience(profile: dict, job: dict) -> list[str]:
    facts = experience_map(profile)
    ordered = [facts[item_id] for item_id in job.get("cvOrder", []) if item_id in facts]
    for item_id, text in facts.items():
        if text not in ordered:
            ordered.append(text)
    return ordered


def render_cv(profile: dict, job: dict | None = None, master: dict | None = None) -> str:
    """Build a CV that uses only profile facts and labels missing fields.

    An uploaded master CV is copied underneath. Matching sentences are
    listed for the target job, and the upload itself is not rewritten.
    """
    if master is None:
        master = load_master_cv()
    angle = ""
    if job and job.get("summaryAngle"):
        angle = job["summaryAngle"]
    else:
        angle = (
            "AI Application Trainee in a Department of Physics, building and "
            "testing an AI chatbot for a robot."
        )
    bullets = ordered_experience(profile, job or {"cvOrder": []})
    bullet_block = "\n".join(f"- {line}" for line in bullets)
    tools = ", ".join(profile["toolsNamedInWork"])
    missing = "\n".join(f"- {item}" for item in profile["notStated"])
    target = "Master CV, not aimed at one advertisement."
    if job:
        target = f"{job.get('title', '')} — {job.get('company', '')}"
    uploaded = ""
    if master and master.get("text"):
        highlights = ""
        if job:
            matched = matching_sentences(master["text"], job)
            if matched:
                highlights = "\n".join(f"- {line}" for line in matched)
                highlights = f"\n\n## Sentences from the upload that share words with this listing\n\n{highlights}\n"
            else:
                highlights = (
                    "\n\n## Sentences from the upload that share words with this listing\n\n"
                    "None of the uploaded sentences share a distinctive word with this listing.\n"
                )
        uploaded = f"""
## Uploaded master CV

Source file: {master.get("filename", "upload")} ({master.get("uploadedAt", "")})
The text below is copied from that file.

{master["text"].strip()}
{highlights}"""
    return f"""# {profile["name"]}

{profile["currentRole"]}, {profile["organisation"]}

Hong Kong

Email: {profile["contact"]["email"] or "[fill in]"}
Phone: {profile["contact"]["phone"] or "[fill in]"}
LinkedIn: {profile["contact"]["linkedin"] or "[fill in]"}

Prepared for: {target}

## Summary

{angle}

## Experience

### {profile["currentRole"]} — {profile["organisation"]}

{bullet_block}

## Tools used in that work

{tools}

## Education

Institution: {profile["education"]["institution"] or "[fill in]"}
Degree: {profile["education"]["degree"] or "[fill in]"}
Field: {profile["education"]["field"] or "[fill in]"}
Graduation: {profile["education"]["graduation"] or "[fill in]"}

## Do not invent these before sending

{missing}
{uploaded}
This CV was drafted from the assignment work context and any uploaded master CV. It is not a submitted application.
"""


def render_letter(profile: dict, job: dict, master: dict | None = None) -> str:
    if master is None:
        master = load_master_cv()
    paragraphs = "\n\n".join(job["letter"])
    if master and master.get("text"):
        paragraphs += (
            f"\n\nThe CV draft includes the master CV file "
            f"{master.get('filename', 'upload')} uploaded on {master.get('uploadedAt', 'the upload date')}."
        )
    return f"""# Cover letter

{profile["name"]}
{profile["currentRole"]}, {profile["organisation"]}
Email: {profile["contact"]["email"] or "[fill in]"}
Phone: {profile["contact"]["phone"] or "[fill in]"}

{job["title"]}
{job["company"]}
{job["location"]}
{job["url"]}

Dear Hiring Team,

{paragraphs}

Yours sincerely,
{profile["name"]}
"""


def render_fit_notes(job: dict, scored: dict) -> str:
    requirements = "\n".join(f"- {item}" for item in job["requirements"])
    breakdown = "\n".join(f"- {line}" for line in scored["lines"])
    action = (
        "Review the draft CV and cover letter, fill the blank fields, and open the source link before deciding to apply."
        if job["prepareApplication"]
        else "No application draft. Read the reason below before spending time on a CV for this role."
    )
    return f"""# Fit notes

{job["title"]}
{job["company"]} · {job["location"]}
Status: {job["listingStatus"]}
Source: {job["source"]} ({job["retrievedOn"]})
Link: {job["url"]}

## What the listing says

{job["summary"]}

## Requirements captured from that source

{requirements}

## Score {scored["score"]} / 100

{breakdown}

## Next action

{action}
"""


def classify(jobs: list[dict], tracker: dict) -> dict:
    """Split listings into drafts, holds, and exclusions.

    A role leaves the draft pile if the employer closed it, the tracker
    already marks it submitted, or the source was not strong enough to
    justify a tailored CV.
    """
    drafts = []
    holds = []
    excluded = []
    items = tracker.get("items", {})
    for job in jobs:
        state = items.get(job["id"], {})
        scored = score_job(job)
        row = {"job": job, "score": scored}
        if job["listingStatus"] in CLOSED_STATUSES or state.get("applied") or state.get("status") == "skipped":
            excluded.append(row)
            continue
        if job["prepareApplication"] and has_full_listing(job) and not state.get("applied"):
            drafts.append(row)
            continue
        holds.append(row)
    drafts.sort(key=lambda row: row["score"]["score"], reverse=True)
    holds.sort(key=lambda row: row["score"]["score"], reverse=True)
    return {"drafts": drafts, "holds": holds, "excluded": excluded}


def write_applications(profile: dict, groups: dict, logger) -> None:
    master_dir = APPLICATIONS / "master"
    master_dir.mkdir(parents=True, exist_ok=True)
    (master_dir / "cv.md").write_text(render_cv(profile), encoding="utf-8")
    logger.info("Wrote master CV")

    for row in groups["drafts"]:
        job = row["job"]
        folder = APPLICATIONS / job["id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "cv.md").write_text(render_cv(profile, job), encoding="utf-8")
        (folder / "cover-letter.md").write_text(render_letter(profile, job), encoding="utf-8")
        (folder / "fit-notes.md").write_text(render_fit_notes(job, row["score"]), encoding="utf-8")
        logger.info("Drafted materials for %s (%s)", job["id"], row["score"]["score"])
        for gap in job["gaps"]:
            logger.warning("%s gap: %s", job["id"], gap["note"])

    for row in groups["holds"] + groups["excluded"]:
        job = row["job"]
        folder = APPLICATIONS / job["id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "fit-notes.md").write_text(render_fit_notes(job, row["score"]), encoding="utf-8")
        # A role that is no longer a draft must not keep a downloadable letter.
        for name in ("cv.md", "cover-letter.md"):
            stale = folder / name
            if stale.exists():
                stale.unlink()
                logger.info("Removed draft %s for %s because it is not ready to send", name, job["id"])
        logger.info("Recorded fit notes only for %s (%s)", job["id"], job["listingStatus"])


def ensure_tracker(jobs: list[dict], groups: dict) -> dict:
    """Keep statuses that a person has already set, and seed the rest."""
    path = DATA / "tracker.json"
    existing = load_json(path) if path.exists() else {"items": {}}
    items = existing.get("items", {})
    draft_ids = {row["job"]["id"] for row in groups["drafts"]}
    for job in jobs:
        current = items.get(job["id"], {})
        if job["listingStatus"] in CLOSED_STATUSES:
            status = "closed"
        elif job["id"] in draft_ids:
            status = current.get("status") or "ready_for_review"
        else:
            status = current.get("status") or "hold"
        if current.get("applied"):
            status = "applied"
        elif current.get("status") == "skipped":
            status = "skipped"
        items[job["id"]] = {
            "status": status,
            "viewed": True,
            "applied": bool(current.get("applied")) or status == "applied",
            "confirmed": bool(current.get("confirmed")),
            "notes": current.get("notes", ""),
        }
    # Drop tracker rows whose listings are no longer in the catalogue,
    # including live cards that the latest search did not return.
    current_ids = {job["id"] for job in jobs}
    items = {key: value for key, value in items.items() if key in current_ids}
    tracker = {"updatedOn": "2026-10-06", "items": items}
    save_json(path, tracker)
    return tracker


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def set_tracker_status(job_id: str, status: str, path: Path | None = None) -> dict:
    """Write a review mark into tracker.json so a reload shows the same state."""
    if status not in TRACKER_STATUSES:
        raise ValueError("不認識的狀態。")
    tracker_path = path or (DATA / "tracker.json")
    tracker = load_json(tracker_path) if tracker_path.exists() else {"items": {}}
    item = tracker.setdefault("items", {}).get(job_id)
    if item is None:
        raise ValueError("找不到這個職位。")
    item["status"] = status
    item["viewed"] = True
    item["applied"] = status == "applied"
    save_json(tracker_path, tracker)
    return item


def confirm_tracker(job_id: str, path: Path | None = None) -> dict:
    """Record that a person has checked the letter and may download it."""
    tracker_path = path or (DATA / "tracker.json")
    tracker = load_json(tracker_path)
    item = tracker.setdefault("items", {}).get(job_id)
    if item is None:
        raise ValueError("找不到這個職位。")
    item["confirmed"] = True
    if item.get("status") in {None, "", "hold"}:
        item["status"] = "ready_for_review"
    save_json(tracker_path, tracker)
    return item


def card(row: dict, kind: str, state: dict | None = None) -> str:
    job = row["job"]
    score = row["score"]["score"]
    requirements = "".join(f"<li>{html_escape(item)}</li>" for item in job["requirements"])
    gaps = "".join(f"<li>{html_escape(item['note'])}</li>" for item in job["gaps"])
    state = state or {}
    confirmed = bool(state.get("confirmed"))
    status = state.get("status") or ""
    materials = ""
    caution = ""
    if job["prepareApplication"] and has_full_listing(job) and kind == "draft":
        hidden = "" if confirmed else " hidden"
        confirm_button = "" if confirmed else '<button type="button" data-confirm>我已核對，允許下載</button>'
        waiting = "" if confirmed else "<p class=\"score\">確認後才能下載。</p>"
        materials = (
            f'<p class="links"><a href="../applications/{html_escape(job["id"])}/fit-notes.md">Fit notes</a></p>'
            f'<p><button type="button" data-preview>預覽求職信</button> {confirm_button}</p>'
            f'<pre class="letter-preview" hidden></pre>'
            f'{waiting}'
            f'<p class="links downloads"{hidden}>'
            f'<a href="../applications/{html_escape(job["id"])}/cv.md">下載履歷</a>'
            f' · <a href="../applications/{html_escape(job["id"])}/cover-letter.md">下載求職信</a></p>'
        )
        if score < 45:
            caution = "<p class=\"score\">不建議現在提交。職缺點名的技能尚未出現在履歷來源裡。</p>"
    else:
        if not has_full_listing(job) and job["listingStatus"] not in CLOSED_STATUSES:
            caution = "<p class=\"score\">未讀到完整職缺，所以沒有起草。</p>"
        materials = (
            f'<p class="links"><a href="../applications/{html_escape(job["id"])}/fit-notes.md">Fit notes</a></p>'
        )
    return f"""
    <article class="card" data-id="{html_escape(job["id"])}" data-kind="{html_escape(kind)}" data-status="{html_escape(status)}" data-confirmed="{"true" if confirmed else "false"}">
      <header>
        <h3>{html_escape(job["title"])}</h3>
        <p class="meta">{html_escape(job["company"])} · {html_escape(job["location"])}</p>
        <p class="score">Fit {score}/100 · {html_escape(job["listingStatus"])}</p>
      </header>
      <p>{html_escape(job["summary"])}</p>
      <h4>Requirements</h4>
      <ul>{requirements}</ul>
      <h4>Gaps</h4>
      <ul>{gaps}</ul>
      <p><a href="{html_escape(job["url"])}">Open listing</a></p>
      {caution}
      {materials}
      <div class="actions">
        <button type="button" data-mark="ready_for_review">保留審閱</button>
        <button type="button" data-mark="applied">已提交</button>
        <button type="button" data-mark="skipped">略過</button>
      </div>
      <p class="state" data-state>檔案狀態：{html_escape(status) if status else "尚未標記"}</p>
    </article>
    """


def render_html(
    profile: dict,
    groups: dict,
    searched_on: str = "2026-10-06",
    last_search: dict | None = None,
    tracker: dict | None = None,
) -> str:
    states = (tracker or {}).get("items", {})
    draft_cards = "\n".join(card(row, "draft", states.get(row["job"]["id"])) for row in groups["drafts"])
    hold_cards = "\n".join(card(row, "hold", states.get(row["job"]["id"])) for row in groups["holds"])
    excluded_cards = "\n".join(card(row, "excluded", states.get(row["job"]["id"])) for row in groups["excluded"])
    master = load_master_cv()
    if master:
        cv_status = (
            f"已上傳 {master.get('filename', 'CV')}（{master.get('uploadedAt', '')}，"
            f"{master.get('characters', 0)} 字）。草稿會原文引用這份履歷。"
        )
    else:
        cv_status = "尚未上傳。評分和草稿仍用作業裡的經歷。"
    if last_search:
        counts = last_search.get("counts") or {}
        count_text = "，".join(f"{name} {number} 則" for name, number in counts.items())
        error_text = ""
        if last_search.get("errors"):
            error_text = " 未能連上：" + "；".join(last_search["errors"])
        search_status = (
            f"上次搜尋 {last_search.get('at', searched_on)}，關鍵字「{last_search.get('keywords', '')}」。"
            f"{count_text}。新加入 {last_search.get('added', 0)} 則。{error_text}"
        )
    else:
        search_status = "尚未用按鈕搜尋。下面是已保存的職缺。"
    keyword_value = html_escape((last_search or {}).get("keywords") or "AI intern")
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>職位搜尋與申請草稿</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1c1915;
      --muted: #5c564e;
      --line: #e4ddd2;
      --paper: #faf7f2;
      --card: #fffdf9;
      --accent: #8c3d2f;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", Palatino, "Palatino Linotype", "Songti TC", serif;
      color: var(--ink);
      background: var(--paper);
      line-height: 1.5;
    }}
    main {{ max-width: 920px; margin: 0 auto; padding: 32px 20px 80px; }}
    h1 {{ font-size: 2rem; line-height: 1.2; margin-bottom: 0.2em; }}
    h2 {{ margin-top: 2.2em; font-size: 1.35rem; }}
    h3 {{ margin: 0 0 0.2em; font-size: 1.2rem; }}
    h4 {{ margin: 0.8em 0 0.2em; font-size: 0.95rem; }}
    p, li {{ font-size: 1rem; }}
    .lead {{ color: var(--muted); max-width: 68ch; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px 18px 14px;
      margin: 14px 0;
    }}
    .meta, .score, .state {{ color: var(--muted); margin: 0.15em 0; }}
    .score {{ color: var(--accent); font-weight: 650; }}
    a {{ color: var(--accent); }}
    button, input[type="text"] {{
      font: inherit;
      margin: 8px 8px 0 0;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--ink);
      background: transparent;
      cursor: pointer;
    }}
    input[type="text"] {{ cursor: text; min-width: 16rem; background: white; }}
    input[type="file"] {{ font: inherit; margin-top: 8px; }}
    button[aria-pressed="true"], button.primary {{ background: var(--ink); color: white; }}
    button:disabled {{ opacity: 0.55; cursor: wait; }}
    .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px; }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 18px 18px 14px;
      margin: 14px 0;
    }}
    .panel h2 {{ margin-top: 0.4em; }}
    pre.letter-preview {{
      white-space: pre-wrap;
      max-height: 240px;
      overflow: auto;
      background: white;
      border: 1px solid var(--line);
      padding: 10px;
      font-size: 0.92rem;
    }}
    [hidden] {{ display: none !important; }}
  </style>
</head>
<body>
  <main>
    <h1>職位搜尋與申請草稿</h1>
    <p class="lead">{html_escape(profile["name"])}，{html_escape(profile["currentRole"])}。搜尋日為 {html_escape(searched_on)}。這些是草稿，尚未向任何僱主提交。</p>
    <p class="lead">偏好地區是香港。JobsDB 與 LinkedIn 搜尋香港職缺，JobStreet 搜尋新加坡，Remotive 搜尋遠端職位。只有讀到完整職缺才會起草。搜尋卡本身不會生成求職信。</p>
    <section class="panel">
      <h2>即時搜尋</h2>
      <label for="keywords">關鍵字</label>
      <input id="keywords" type="text" value="{keyword_value}">
      <button id="refetch" class="primary" type="button">立即重新搜尋</button>
      <p id="search-status" class="state">{html_escape(search_status)}</p>
      <h2>主履歷</h2>
      <form id="cv-form">
        <label for="cv-file">上傳 PDF、DOCX、TXT 或 Markdown</label><br>
        <input id="cv-file" name="cv" type="file" accept=".pdf,.docx,.txt,.md,.markdown" required>
        <button type="submit">上傳主履歷</button>
      </form>
      <p id="cv-status" class="state">{html_escape(cv_status)}</p>
      <p><a href="../applications/master/cv.md">主履歷草稿</a></p>
    </section>
    <div class="filters">
      <button type="button" data-filter="draft" aria-pressed="true">建議起草</button>
      <button type="button" data-filter="hold" aria-pressed="true">先不要投</button>
      <button type="button" data-filter="excluded" aria-pressed="true">已排除</button>
    </div>
    <h2>建議起草</h2>
    <p class="lead">這裡只放已讀到完整職缺的草稿。預覽求職信後按確認，下載連結才會出現。標記會寫入 data/tracker.json。</p>
    <section id="drafts">{draft_cards}</section>
    <h2>先不要投</h2>
    <p class="lead">這些職位可能仍開放。未讀到完整職缺的不會起草。地點或條件差太遠的也不會起草。</p>
    <section id="holds">{hold_cards}</section>
    <h2>已排除</h2>
    <p class="lead">僱主頁面顯示已額滿、廣告已過期，或申請已關閉。保留紀錄是為了避免重複申請。</p>
    <section id="excluded">{excluded_cards}</section>
  </main>
  <script>
    // Older pages stored marks only in the browser. Drop that copy so the
    // file in data/tracker.json is the only status a reload can show.
    localStorage.removeItem("cheung-job-tracker-2026-10-06");

    function paint(card) {{
      const status = card.dataset.status || "";
      card.querySelectorAll("button[data-mark]").forEach((button) => {{
        button.setAttribute("aria-pressed", String(button.dataset.mark === status));
      }});
    }}

    async function postJson(url, payload) {{
      const response = await fetch(url, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      let body = {{}};
      try {{
        body = await response.json();
      }} catch (error) {{
        body = {{}};
      }}
      if (!response.ok || !body.ok) {{
        throw new Error(body.message || "操作失敗");
      }}
      return body;
    }}

    document.querySelectorAll(".card").forEach((card) => {{
      paint(card);
      card.querySelectorAll("button[data-mark]").forEach((button) => {{
        button.addEventListener("click", async () => {{
          const label = card.querySelector("[data-state]");
          const mark = button.dataset.mark;
          label.textContent = "正在寫入檔案…";
          try {{
            await postJson("/api/tracker", {{ id: card.dataset.id, status: mark }});
            if (mark === "applied" || mark === "skipped") {{
              window.location.reload();
              return;
            }}
            card.dataset.status = mark;
            label.textContent = "檔案狀態：" + mark;
            paint(card);
          }} catch (error) {{
            label.textContent = error.message;
          }}
        }});
      }});
      const preview = card.querySelector("[data-preview]");
      if (preview) {{
        preview.addEventListener("click", async () => {{
          const box = card.querySelector(".letter-preview");
          box.hidden = false;
          box.textContent = "正在讀取求職信…";
          try {{
            const payload = await postJson("/api/preview", {{ id: card.dataset.id }});
            box.textContent = payload.text;
          }} catch (error) {{
            box.textContent = error.message;
          }}
        }});
      }}
      const confirmButton = card.querySelector("[data-confirm]");
      if (confirmButton) {{
        confirmButton.addEventListener("click", async () => {{
          confirmButton.disabled = true;
          try {{
            await postJson("/api/confirm", {{ id: card.dataset.id }});
            window.location.reload();
          }} catch (error) {{
            confirmButton.disabled = false;
            const box = card.querySelector(".letter-preview");
            box.hidden = false;
            box.textContent = error.message;
          }}
        }});
      }}
    }});

    const refetchButton = document.getElementById("refetch");
    const searchStatus = document.getElementById("search-status");
    refetchButton.addEventListener("click", async () => {{
      refetchButton.disabled = true;
      searchStatus.textContent = "正在搜尋 JobsDB、JobStreet、LinkedIn 和 Remotive…";
      try {{
        const response = await fetch("/api/refetch", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ keywords: document.getElementById("keywords").value }})
        }});
        const payload = await response.json();
        if (!response.ok || !payload.ok) {{
          searchStatus.textContent = payload.message || "搜尋失敗";
          refetchButton.disabled = false;
          return;
        }}
        searchStatus.textContent = payload.message;
        window.location.reload();
      }} catch (error) {{
        searchStatus.textContent = "連不到搜尋服務。請在專案目錄執行 python3 src/server.py 後再開啟這個頁面。";
        refetchButton.disabled = false;
      }}
    }});

    document.getElementById("cv-form").addEventListener("submit", async (event) => {{
      event.preventDefault();
      const status = document.getElementById("cv-status");
      const fileInput = document.getElementById("cv-file");
      if (!fileInput.files.length) {{
        status.textContent = "請先選擇檔案。";
        return;
      }}
      const body = new FormData();
      body.append("cv", fileInput.files[0]);
      status.textContent = "正在讀取履歷…";
      try {{
        const response = await fetch("/api/cv", {{ method: "POST", body }});
        const payload = await response.json();
        if (!response.ok || !payload.ok) {{
          status.textContent = payload.message || "上傳失敗";
          return;
        }}
        status.textContent = payload.message;
        window.location.reload();
      }} catch (error) {{
        status.textContent = "連不到上傳服務。請在專案目錄執行 python3 src/server.py 後再開啟這個頁面。";
      }}
    }});

    document.querySelectorAll("button[data-filter]").forEach((button) => {{
      button.addEventListener("click", () => {{
        const on = button.getAttribute("aria-pressed") !== "true";
        button.setAttribute("aria-pressed", String(on));
        const kind = button.dataset.filter;
        const section = document.getElementById(kind === "draft" ? "drafts" : kind === "hold" ? "holds" : "excluded");
        const lead = section.previousElementSibling;
        const heading = lead.previousElementSibling;
        const display = on ? "" : "none";
        section.style.display = display;
        lead.style.display = display;
        heading.style.display = display;
      }});
    }});
  </script>
</body>
</html>
"""


def write_site(
    profile: dict,
    groups: dict,
    logger,
    searched_on: str = "2026-10-06",
    last_search: dict | None = None,
    tracker: dict | None = None,
) -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "index.html").write_text(
        render_html(profile, groups, searched_on, last_search, tracker),
        encoding="utf-8",
    )
    logger.info(
        "Wrote tracker page with %s drafts, %s holds, %s excluded",
        len(groups["drafts"]),
        len(groups["holds"]),
        len(groups["excluded"]),
    )


def run() -> dict:
    logger = build_logger(LOG_PATH)
    profile = load_json(DATA / "profile.json")
    catalogue = load_json(DATA / "jobs.json")
    logger.info(
        "Loaded profile for %s and %s listings from %s",
        profile["name"],
        len(catalogue["jobs"]),
        catalogue["searchedOn"],
    )
    if not profile["contact"]["email"]:
        logger.warning("Contact email is blank. Drafts must be completed before any submission.")
    prior = load_json(DATA / "tracker.json") if (DATA / "tracker.json").exists() else {"items": {}}
    groups = classify(catalogue["jobs"], prior)
    for row in groups["excluded"]:
        logger.info("Excluded %s (%s)", row["job"]["id"], row["job"]["listingStatus"])
    write_applications(profile, groups, logger)
    tracker = ensure_tracker(catalogue["jobs"], groups)
    write_site(
        profile,
        groups,
        logger,
        catalogue.get("searchedOn", "2026-10-06"),
        catalogue.get("lastLiveSearch"),
        tracker,
    )
    report = {
        "drafts": [row["job"]["id"] for row in groups["drafts"]],
        "holds": [row["job"]["id"] for row in groups["holds"]],
        "excluded": [row["job"]["id"] for row in groups["excluded"]],
        "scores": {row["job"]["id"]: row["score"]["score"] for row in groups["drafts"] + groups["holds"]},
    }
    save_json(DATA / "recommendations.json", report)
    logger.info("Recommendations ready: %s", ", ".join(report["drafts"]))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh job drafts and the local tracker page.")
    parser.parse_args()
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
