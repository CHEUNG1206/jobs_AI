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

from logging_setup import build_logger

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
APPLICATIONS = ROOT / "applications"
WEB = ROOT / "web"
LOG_PATH = DATA / "career-agent.log"

CLOSED_STATUSES = {"closed", "expired"}


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


def render_cv(profile: dict, job: dict | None = None) -> str:
    """Build a CV that uses only profile facts and labels missing fields."""
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
        target = f"{job['title']} — {job['company']}"
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

This CV was drafted on 2026-10-06 from the assignment work context. It is not a submitted application.
"""


def render_letter(profile: dict, job: dict) -> str:
    paragraphs = "\n\n".join(job["letter"])
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
        if job["listingStatus"] in CLOSED_STATUSES or state.get("applied"):
            excluded.append(row)
            continue
        if job["prepareApplication"] and not state.get("applied"):
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
        items[job["id"]] = {
            "status": status,
            "viewed": True,
            "applied": bool(current.get("applied")),
            "notes": current.get("notes", ""),
        }
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


def card(row: dict, kind: str) -> str:
    job = row["job"]
    score = row["score"]["score"]
    requirements = "".join(f"<li>{html_escape(item)}</li>" for item in job["requirements"])
    gaps = "".join(f"<li>{html_escape(item['note'])}</li>" for item in job["gaps"])
    materials = ""
    caution = ""
    if job["prepareApplication"] and kind == "draft":
        materials = (
            f'<p class="links"><a href="../applications/{html_escape(job["id"])}/cv.md">CV draft</a>'
            f' · <a href="../applications/{html_escape(job["id"])}/cover-letter.md">Cover letter</a>'
            f' · <a href="../applications/{html_escape(job["id"])}/fit-notes.md">Fit notes</a></p>'
        )
        if score < 45:
            caution = "<p class=\"score\">不建議現在提交。職缺點名的技能尚未出現在履歷來源裡。</p>"
    else:
        materials = (
            f'<p class="links"><a href="../applications/{html_escape(job["id"])}/fit-notes.md">Fit notes</a></p>'
        )
    return f"""
    <article class="card" data-id="{html_escape(job["id"])}" data-kind="{html_escape(kind)}">
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
        <button type="button" data-mark="ready_for_review">Keep for review</button>
        <button type="button" data-mark="applied">Mark submitted</button>
        <button type="button" data-mark="skipped">Skip</button>
      </div>
      <p class="state" data-state></p>
    </article>
    """


def render_html(profile: dict, groups: dict) -> str:
    draft_cards = "\n".join(card(row, "draft") for row in groups["drafts"])
    hold_cards = "\n".join(card(row, "hold") for row in groups["holds"])
    excluded_cards = "\n".join(card(row, "excluded") for row in groups["excluded"])
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
    button {{
      font: inherit;
      margin: 8px 8px 0 0;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--ink);
      background: transparent;
      cursor: pointer;
    }}
    button[aria-pressed="true"] {{ background: var(--ink); color: white; }}
    .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 4px; }}
  </style>
</head>
<body>
  <main>
    <h1>職位搜尋與申請草稿</h1>
    <p class="lead">{html_escape(profile["name"])}（{html_escape(profile["nameZh"])}），{html_escape(profile["currentRole"])}。搜尋日為 2026-10-06。這些是草稿，尚未向任何僱主提交。</p>
    <p class="lead">偏好地區是香港，目標是 AI 應用、機械人軟件、見習或實習。履歷只使用作業裡寫過的工作內容。電郵、電話、院校和學位留空，避免把沒有來源的資料寫進申請。</p>
    <p><a href="../applications/master/cv.md">主履歷草稿</a></p>
    <div class="filters">
      <button type="button" data-filter="draft" aria-pressed="true">建議起草</button>
      <button type="button" data-filter="hold" aria-pressed="true">先不要投</button>
      <button type="button" data-filter="excluded" aria-pressed="true">已排除</button>
    </div>
    <h2>建議起草</h2>
    <p class="lead">已去掉已截止的職位。提交前請打開原連結，核對完整職缺，並補上聯絡資料。</p>
    <section id="drafts">{draft_cards}</section>
    <h2>先不要投</h2>
    <p class="lead">職位仍可能開放，但地點、入學狀態或技術條件與現有資料差太遠。</p>
    <section id="holds">{hold_cards}</section>
    <h2>已排除</h2>
    <p class="lead">僱主頁面顯示已額滿、廣告已過期，或申請已關閉。保留紀錄是為了避免重複申請。</p>
    <section id="excluded">{excluded_cards}</section>
  </main>
  <script>
    const storageKey = "cheung-job-tracker-2026-10-06";
    const saved = JSON.parse(localStorage.getItem(storageKey) || "{{}}");

    function paint(card) {{
      const id = card.dataset.id;
      const state = saved[id] || {{}};
      card.querySelectorAll("button[data-mark]").forEach((button) => {{
        button.setAttribute("aria-pressed", String(button.dataset.mark === state.status));
      }});
      const label = card.querySelector("[data-state]");
      label.textContent = state.status ? "本機狀態：" + state.status : "本機狀態：尚未標記";
    }}

    document.querySelectorAll(".card").forEach((card) => {{
      paint(card);
      card.querySelectorAll("button[data-mark]").forEach((button) => {{
        button.addEventListener("click", () => {{
          saved[card.dataset.id] = {{ status: button.dataset.mark, viewed: true }};
          localStorage.setItem(storageKey, JSON.stringify(saved));
          paint(card);
        }});
      }});
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


def write_site(profile: dict, groups: dict, logger) -> None:
    WEB.mkdir(parents=True, exist_ok=True)
    (WEB / "index.html").write_text(render_html(profile, groups), encoding="utf-8")
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
    write_site(profile, groups, logger)
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
