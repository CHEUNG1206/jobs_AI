"""Live search across public job boards.

JobsDB and JobStreet share SEEK's search API. LinkedIn is the public
guest listing, not a signed-in account. Remotive is the remote board.
Each result is scored from the saved profile and, when present, the
uploaded CV. Hand-written curated roles are left in place.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen

JUNIOR_WORDS = ("intern", "trainee", "graduate", "junior", "fresh", "student")
SENIOR_WORDS = ("senior", "lead", "principal", "director", "manager", "head of")
REMOTE_WORDS = ("worldwide", "remote", "anywhere")
TOPIC_WORDS = ("ai", "robot", "android", "chatbot", "llm")
HARD_TERMS = ("c++", "flutter", "pytorch")
EXPERIENCE_KEYS = (
    ("chatbot", ("chatbot", "conversational")),
    ("models", ("model", "llm", "latency")),
    ("android", ("android", "mobile")),
    ("debug", ("test", "debug")),
    ("research", ("research",)),
)


def http_get(url: str) -> bytes:
    """Fetch one public page. Callers record the failure and continue."""
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/html;q=0.9",
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read()


def search_all(keywords: str, get=http_get) -> dict:
    """Query every board. One board failing does not cancel the others."""
    query = keywords.strip() or "AI intern"
    found = []
    counts = {}
    errors = []
    for name, searcher in (
        ("JobsDB", lambda: search_seek(query, "HK-Main", "https://hk.jobsdb.com", "JobsDB", get)),
        ("JobStreet", lambda: search_seek(query, "SG-Main", "https://sg.jobstreet.com", "JobStreet", get)),
        ("LinkedIn", lambda: search_linkedin(query, get)),
        ("Remotive", lambda: search_remotive(query, get)),
    ):
        try:
            batch = [item for item in searcher() if title_matches(item["title"], query)]
            counts[name] = len(batch)
            found.extend(batch)
        except Exception as exc:
            counts[name] = 0
            errors.append(f"{name}: {exc}")
    return {"keywords": query, "jobs": dedupe(found), "counts": counts, "errors": errors}


def search_seek(keywords: str, site_key: str, origin: str, platform: str, get) -> list[dict]:
    """Read one page of the SEEK search API used by JobsDB and JobStreet."""
    url = (
        f"{origin}/api/jobsearch/v5/search?siteKey={site_key}"
        f"&keywords={quote(keywords)}&page=1&pageSize=15"
    )
    payload = json.loads(get(url).decode("utf-8", errors="replace"))
    jobs = []
    for item in payload.get("data") or []:
        locations = item.get("locations") or [{}]
        location = locations[0].get("label", "") if locations else ""
        bullets = [str(point) for point in item.get("bulletPoints") or []]
        teaser = str(item.get("teaser") or "").strip()
        company = item.get("companyName") or (item.get("advertiser") or {}).get("description") or ""
        jobs.append(
            {
                "platform": platform,
                "remote_id": str(item.get("id")),
                "title": str(item.get("title") or "").strip(),
                "company": company,
                "location": location,
                "url": f"{origin}/job/{item.get('id')}",
                "summary": teaser or " ".join(bullets) or str(item.get("title") or ""),
                "bullets": bullets,
                "work_types": [str(kind) for kind in item.get("workTypes") or []],
                "listed": str(item.get("listingDateDisplay") or item.get("listingDate") or ""),
            }
        )
    return jobs


def search_linkedin(keywords: str, get) -> list[dict]:
    """Parse LinkedIn's public guest cards for Hong Kong.

    The guest endpoint returns a list of cards, not a signed-in feed.
    Fields are read separately because the wrapper around each card changes.
    """
    url = (
        "https://hk.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={quote(keywords)}&location=Hong%20Kong&start=0"
    )
    page = get(url).decode("utf-8", errors="replace")
    return parse_linkedin_loose(page)


def parse_linkedin_loose(page: str) -> list[dict]:
    """Read title, company, place, and link when the card wrapper varies."""
    ids = re.findall(r'urn:li:jobPosting:(\d+)', page)
    titles = [clean(value) for value in re.findall(r'base-search-card__title">\s*(.*?)\s*</h3>', page, re.S)]
    companies = [clean(value) for value in re.findall(r'hidden-nested-link"[^>]*>\s*(.*?)\s*</a>', page, re.S)]
    places = [clean(value) for value in re.findall(r'job-search-card__location">\s*(.*?)\s*</span>', page, re.S)]
    links = re.findall(r'href="(https://[^"]+/jobs/view/[^"?]+)', page)
    jobs = []
    for index, remote_id in enumerate(ids):
        title = titles[index] if index < len(titles) else ""
        if not title:
            continue
        jobs.append(
            {
                "platform": "LinkedIn",
                "remote_id": remote_id,
                "title": title,
                "company": companies[index] if index < len(companies) else "",
                "location": places[index] if index < len(places) else "Hong Kong",
                "url": links[index] if index < len(links) else f"https://hk.linkedin.com/jobs/view/{remote_id}",
                "summary": title,
                "bullets": [],
                "work_types": [],
                "listed": "",
            }
        )
    return jobs


def search_remotive(keywords: str, get) -> list[dict]:
    """Read Remotive's public JSON board and keep title matches."""
    url = f"https://remotive.com/api/remote-jobs?search={quote(keywords)}&limit=30"
    payload = json.loads(get(url).decode("utf-8", errors="replace"))
    jobs = []
    for item in payload.get("jobs") or []:
        description = re.sub(r"<[^>]+>", " ", str(item.get("description") or ""))
        description = " ".join(description.split())
        jobs.append(
            {
                "platform": "Remotive",
                "remote_id": str(item.get("id")),
                "title": str(item.get("title") or "").strip(),
                "company": str(item.get("company_name") or "").strip(),
                "location": str(item.get("candidate_required_location") or "Remote"),
                "url": str(item.get("url") or ""),
                "summary": description[:500],
                "bullets": [],
                "work_types": [str(item.get("job_type") or "")] if item.get("job_type") else [],
                "listed": str(item.get("publication_date") or ""),
            }
        )
    return jobs


def title_matches(title: str, keywords: str) -> bool:
    """Keep a card when its title contains one of the query words."""
    haystack = title.lower()
    tokens = [token for token in re.findall(r"[a-z0-9+#]{2,}", keywords.lower()) if token not in {"or", "and", "the", "in"}]
    if not tokens:
        return True
    return any(token in haystack for token in tokens)


def dedupe(jobs: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for job in jobs:
        key = job["url"].split("?")[0].rstrip("/").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def merge_catalogue(catalogue: dict, live_jobs: list[dict], meta: dict) -> dict:
    """Replace the previous live page and keep the audited listings."""
    curated = []
    for job in catalogue.get("jobs") or []:
        if job.get("origin") == "live":
            continue
        job.setdefault("origin", "curated")
        curated.append(job)
    known = {job["url"].split("?")[0].rstrip("/").lower() for job in curated}
    fresh = []
    for job in live_jobs:
        key = job["url"].split("?")[0].rstrip("/").lower()
        if key in known:
            continue
        fresh.append(job)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        **catalogue,
        "searchedOn": now,
        "lastLiveSearch": {
            "keywords": meta.get("keywords", ""),
            "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "counts": meta.get("counts") or {},
            "errors": meta.get("errors") or [],
            "added": len(fresh),
        },
        "jobs": curated + fresh,
    }


def to_catalogue_job(raw: dict, profile: dict, corpus: str) -> dict:
    """Turn a board card into the record the scorer and the page expect."""
    base, evidence, gaps, prepare = assess(raw, corpus)
    requirements = list(raw["bullets"])
    if raw["work_types"]:
        requirements.append("Work type: " + ", ".join(kind for kind in raw["work_types"] if kind))
    if not requirements:
        requirements.append("Only the search-card title and summary were retrieved.")
    job_id = f"live-{raw['platform'].lower()}-{raw['remote_id']}"
    return {
        "id": job_id,
        "origin": "live",
        "title": raw["title"],
        "company": raw["company"],
        "location": raw["location"],
        "employmentType": ", ".join(raw["work_types"]) or "See listing",
        "url": raw["url"],
        "source": raw["platform"],
        "retrievedOn": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "listingStatus": "open_live",
        "listed": raw["listed"],
        "createdAt": "",
        "prepareApplication": prepare,
        "baseScore": base,
        "summary": raw["summary"],
        "requirements": requirements,
        "evidence": [{"points": points, "note": note} for points, note in evidence],
        "gaps": [{"points": points, "note": note} for points, note in gaps],
        "cvOrder": ordered_ids(raw, profile),
        "summaryAngle": (
            f"{profile.get('currentRole', 'Applicant')} comparing this {raw['platform']} "
            f"listing with the recorded trainee work."
        ),
        "letter": live_letter(profile, raw),
    }


def assess(raw: dict, corpus: str) -> tuple[int, list, list, bool]:
    """Score a live card from wording the board actually returned."""
    blob = f"{raw['title']} {raw['summary']} {raw['location']}".lower()
    corpus_l = corpus.lower()
    evidence = []
    gaps = []
    junior = any(word in blob for word in JUNIOR_WORDS)
    senior = any(word in blob for word in SENIOR_WORDS)
    if junior:
        evidence.append((12, "The card uses intern, trainee, graduate, junior, or student wording."))
    if senior and not junior:
        gaps.append((-20, "The title reads as a senior role."))
    location = raw["location"].lower()
    if "hong kong" in location or "香港" in location:
        evidence.append((10, "The listing is in Hong Kong."))
    elif any(word in location for word in REMOTE_WORDS):
        evidence.append((4, "The listing is remote."))
    else:
        gaps.append((-14, "The listing is outside Hong Kong."))
    if any(word in blob for word in TOPIC_WORDS):
        evidence.append((6, "The card mentions AI, robotics, Android, a chatbot, or an LLM."))
    matched = 0
    for _label, words in EXPERIENCE_KEYS:
        if matched >= 3:
            break
        if any(word in blob and word in corpus_l for word in words):
            evidence.append((6, "A word in the card also appears in the profile or uploaded CV."))
            matched += 1
    gaps.append((-6, "Only the public search card was saved. Open the listing before applying."))
    for term in HARD_TERMS:
        if term in blob and term not in corpus_l:
            gaps.append((-8, f"{term} appears in the card and is not in the profile or uploaded CV."))
    total = 30 + sum(points for points, _note in evidence) + sum(points for points, _note in gaps)
    total = max(0, min(100, total))
    prepare = total >= 52 and not (senior and not junior)
    return 30, evidence, gaps, prepare


def ordered_ids(raw: dict, profile: dict) -> list[str]:
    """Put the experience lines that share words with the card first."""
    blob = f"{raw['title']} {raw['summary']}".lower()
    key_map = {label: words for label, words in EXPERIENCE_KEYS}
    ranked = []
    for item in profile.get("experience") or []:
        hits = sum(1 for token in key_map.get(item["id"], ()) if token in blob)
        ranked.append((hits, item["id"]))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item_id for _hits, item_id in ranked]


def live_letter(profile: dict, raw: dict) -> list[str]:
    """Draft a letter that cites the card and the saved trainee work only."""
    name_role = profile.get("currentRole", "an applicant")
    organisation = profile.get("organisation", "the recorded organisation")
    facts = [item["text"] for item in profile.get("experience") or []]
    fact_text = " ".join(facts)
    return [
        (
            f"I am applying for the {raw['title']} role at {raw['company']}. "
            f"I am {name_role} in {organisation}."
        ),
        (
            f"This draft uses the {raw['platform']} search card retrieved for "
            f"{raw['location'] or 'the listed location'}. The card says: {raw['summary']}"
        ),
        (
            "The work I can point to is the following. "
            + fact_text
        ),
        (
            "I will open the full advertisement before sending this letter, "
            "and I will not treat a skill as mine unless it is in my CV. "
            "Contact details that are still blank need to be filled in first."
        ),
    ]


def profile_corpus(profile: dict, master: dict | None) -> str:
    """Join the assignment facts and the uploaded CV into one comparison text."""
    parts = [profile.get("currentRole", ""), profile.get("organisation", "")]
    parts.extend(item.get("text", "") for item in profile.get("experience") or [])
    parts.extend(profile.get("toolsNamedInWork") or [])
    if master and master.get("text"):
        parts.append(master["text"])
    return "\n".join(parts)


def clean(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())
