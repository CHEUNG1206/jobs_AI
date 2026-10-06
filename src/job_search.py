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
                "full_text": "",
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
                "full_text": "",
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
                "full_text": description,
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


def plain_html(markup: str) -> str:
    """Turn a job-ad fragment into readable lines without the tags."""
    text = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    text = re.sub(r"(?i)</p>|</li>|</div>|</h[1-6]>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def fetch_seek_content(origin: str, job_id: str, post) -> str:
    """Read the full advertisement from the SEEK GraphQL endpoint.

    The search API only returns a card. jobDetails returns the body the
    employer published, which is what a letter is allowed to quote.
    """
    query = 'query { jobDetails(id: "%s") { job { content } } }' % job_id
    payload = json.loads(post(origin + "/graphql", {"query": query}).decode("utf-8", errors="replace"))
    content = (((payload.get("data") or {}).get("jobDetails") or {}).get("job") or {}).get("content") or ""
    return plain_html(content)


def fetch_linkedin_content(job_id: str, get) -> str:
    """Read the public guest job page, which includes the description."""
    url = f"https://hk.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    page = get(url).decode("utf-8", errors="replace")
    match = re.search(r"show-more-less-html__markup[^>]*>(.*?)</div>", page, re.S)
    if not match:
        return ""
    return plain_html(match.group(1))


def http_post(url: str, payload: dict) -> bytes:
    """POST JSON. Used for the SEEK job-detail query."""
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=20) as response:
        return response.read()


def enrich_raw_job(raw: dict, get=http_get, post=http_post) -> dict:
    """Fill full_text from the employer page when the card does not have it."""
    if len((raw.get("full_text") or "").strip()) >= 280:
        return raw
    try:
        if raw["platform"] == "JobsDB":
            raw["full_text"] = fetch_seek_content("https://hk.jobsdb.com", raw["remote_id"], post)
        elif raw["platform"] == "JobStreet":
            raw["full_text"] = fetch_seek_content("https://sg.jobstreet.com", raw["remote_id"], post)
        elif raw["platform"] == "LinkedIn":
            raw["full_text"] = fetch_linkedin_content(raw["remote_id"], get)
    except Exception:
        raw["full_text"] = raw.get("full_text") or ""
    return raw


def enrich_curated_job(job: dict, post=http_post) -> dict:
    """Attach a full JobsDB or JobStreet advertisement to a saved listing."""
    if len((job.get("fullText") or "").strip()) >= 280:
        return job
    match = re.search(r"https://(?P<host>hk\.jobsdb\.com|sg\.jobstreet\.com)/job/(?P<id>\d+)", job.get("url") or "")
    if not match:
        return job
    origin = "https://" + match.group("host")
    try:
        text = fetch_seek_content(origin, match.group("id"), post)
    except Exception:
        return job
    if len(text) >= 280:
        job["fullText"] = text[:6000]
    return job


def platform_of(job: dict) -> str:
    """Map a saved listing back to the board that can return its body."""
    source = (job.get("source") or "").lower()
    job_id = job.get("id") or ""
    if "jobsdb" in source or job_id.startswith("live-jobsdb"):
        return "JobsDB"
    if "jobstreet" in source or job_id.startswith("live-jobstreet"):
        return "JobStreet"
    if "linkedin" in source or job_id.startswith("live-linkedin"):
        return "LinkedIn"
    if "remotive" in source or job_id.startswith("live-remotive"):
        return "Remotive"
    return job.get("source") or ""


def remote_id_of(job: dict) -> str:
    """Read the board id from the public URL or the saved job id."""
    match = re.search(r"(\d+)(?:/)?$", (job.get("url") or "").rstrip("/"))
    if match:
        return match.group(1)
    match = re.search(r"(\d{5,})", job.get("id") or "")
    return match.group(1) if match else ""


def card_only_gap(note: str) -> bool:
    """True when a penalty only existed because the body had not been read."""
    text = note.lower()
    return (
        "blocked the full advertisement" in text
        or "only the company-list summary" in text
        or "only the public search card" in text
        or "only the search-card" in text
        or "card summary was retrieved" in text
    )


def install_full_advertisement(job: dict, profile: dict, corpus: str) -> dict:
    """Quote the employer text in the letter once that text is long enough.

    Hand-scored curated roles keep their other points. The penalty for a
    missing advertisement is removed after the body arrives. Live rows are
    scored again from that body, because the card score is not reused.
    """
    full = (job.get("fullText") or "").strip()
    if len(full) < 280:
        if job.get("origin") == "live":
            job["prepareApplication"] = False
            job["letter"] = []
        return job
    raw = {
        "platform": platform_of(job),
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "summary": job.get("summary", ""),
        "location": job.get("location", ""),
        "full_text": full,
    }
    if job.get("origin") == "live":
        base, evidence, gaps, prepare = assess(raw, corpus)
        job["baseScore"] = base
        job["evidence"] = [{"points": points, "note": note} for points, note in evidence]
        job["gaps"] = [{"points": points, "note": note} for points, note in gaps]
        job["prepareApplication"] = prepare
        job["listingStatus"] = "open_full"
        job["requirements"] = requirement_lines(full) or [full[:240]]
        job["summary"] = full[:500]
        job["cvOrder"] = ordered_ids(raw, profile)
        job["summaryAngle"] = (
            f"{profile.get('currentRole', 'Applicant')} for {job.get('title', '')} at {job.get('company', '')}."
        )
        job["letter"] = live_letter(profile, raw) if prepare else []
        return job
    if job.get("listingStatus") not in {"closed", "expired"}:
        job["listingStatus"] = "open_full"
    job["gaps"] = [gap for gap in job.get("gaps") or [] if not card_only_gap(gap.get("note", ""))]
    job["requirements"] = requirement_lines(full) or job.get("requirements") or []
    job["letter"] = live_letter(profile, raw)
    return job


def backfill_catalogue(jobs: list[dict], profile: dict, corpus: str, get=http_get, post=http_post, limit: int = 12) -> int:
    """Read full advertisements for saved rows that still only have a card.

    Curated JobsDB and JobStreet links are always tried. Live cards are
    capped so one refresh does not request every result.
    """
    filled = 0
    for job in jobs:
        if job.get("origin") == "live":
            continue
        before = len((job.get("fullText") or "").strip())
        enrich_curated_job(job, post)
        if len((job.get("fullText") or "").strip()) >= 280:
            install_full_advertisement(job, profile, corpus)
            if before < 280:
                filled += 1
    pending = []
    for job in jobs:
        if job.get("origin") != "live" or len((job.get("fullText") or "").strip()) >= 280:
            continue
        raw = {
            "platform": platform_of(job),
            "remote_id": remote_id_of(job),
            "title": job.get("title", ""),
            "summary": job.get("summary", ""),
            "location": job.get("location", ""),
            "full_text": "",
        }
        pending.append((card_rank(raw), job, raw))
    pending.sort(key=lambda item: item[0], reverse=True)
    for _rank, job, raw in pending[:limit]:
        enrich_raw_job(raw, get, post)
        text = (raw.get("full_text") or "").strip()
        if len(text) >= 280:
            job["fullText"] = text[:6000]
            filled += 1
        install_full_advertisement(job, profile, corpus)
    # Cards that were not opened must not keep a letter written from the title.
    for job in jobs:
        if job.get("origin") == "live" and len((job.get("fullText") or "").strip()) < 280:
            job["prepareApplication"] = False
            job["letter"] = []
    return filled


def card_rank(raw: dict) -> int:
    """Order cards so detail fetches prefer junior Hong Kong AI roles."""
    blob = f"{raw.get('title', '')} {raw.get('summary', '')} {raw.get('location', '')}".lower()
    score = 0
    if any(word in blob for word in JUNIOR_WORDS):
        score += 3
    if "hong kong" in blob or "香港" in blob:
        score += 2
    if any(word in blob for word in TOPIC_WORDS):
        score += 2
    if any(word in blob for word in SENIOR_WORDS) and not any(word in blob for word in JUNIOR_WORDS):
        score -= 3
    return score


def requirement_lines(full_text: str) -> list[str]:
    """Pull duty or requirement lines out of a full advertisement."""
    chunks = [" ".join(line.split()) for line in full_text.splitlines() if len(" ".join(line.split())) >= 50]
    if len(chunks) < 2:
        chunks = [" ".join(part.split()) for part in re.split(r"(?<=[.!?])\s+", full_text) if len(part) >= 50]
    cues = ("you will", "responsible", "requirement", "experience", "skill", "develop", "test", "build", "design", "intern")
    preferred = [line for line in chunks if any(cue in line.lower() for cue in cues)]
    chosen = []
    for line in preferred or chunks:
        short = line[:240].rsplit(" ", 1)[0] if len(line) > 240 else line
        if short not in chosen:
            chosen.append(short)
        if len(chosen) == 4:
            break
    return chosen


def best_fact(line: str, facts: list[dict]) -> dict | None:
    """Pick the saved experience line that shares the most distinctive words."""
    words = {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z+#]{4,}", line)}
    best = None
    score = 0
    for fact in facts:
        tokens = {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z+#]{4,}", fact.get("text", ""))}
        overlap = len(words & tokens)
        if overlap > score:
            score = overlap
            best = fact
    return best


def to_catalogue_job(raw: dict, profile: dict, corpus: str) -> dict:
    """Turn a board result into the record the scorer and the page expect.

    A letter is stored only after the full advertisement has been read.
    Card text alone cannot set prepareApplication.
    """
    full = (raw.get("full_text") or "").strip()
    base, evidence, gaps, prepare = assess(raw, corpus)
    if len(full) >= 280:
        requirements = requirement_lines(full) or [full[:240]]
        summary = full[:500]
    else:
        requirements = ["The full advertisement was not retrieved, so no application was drafted."]
        summary = raw["summary"]
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
        "listingStatus": "open_full" if len(full) >= 280 else "open_live",
        "listed": raw["listed"],
        "createdAt": "",
        "prepareApplication": prepare,
        "fullText": full[:6000],
        "baseScore": base,
        "summary": summary,
        "requirements": requirements,
        "evidence": [{"points": points, "note": note} for points, note in evidence],
        "gaps": [{"points": points, "note": note} for points, note in gaps],
        "cvOrder": ordered_ids(raw, profile),
        "summaryAngle": (
            f"{profile.get('currentRole', 'Applicant')} for {raw['title']} at {raw['company']}."
        ),
        "letter": live_letter(profile, raw) if prepare else [],
    }


def assess(raw: dict, corpus: str) -> tuple[int, list, list, bool]:
    """Score from the full advertisement when it was retrieved."""
    full = (raw.get("full_text") or "").strip()
    blob = f"{raw['title']} {raw['summary']} {full} {raw['location']}".lower()
    corpus_l = corpus.lower()
    evidence = []
    gaps = []
    junior = any(word in blob for word in JUNIOR_WORDS)
    senior = any(word in blob for word in SENIOR_WORDS)
    if junior:
        evidence.append((12, "The advertisement uses intern, trainee, graduate, junior, or student wording."))
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
        evidence.append((6, "The advertisement mentions AI, robotics, Android, a chatbot, or an LLM."))
    matched = 0
    for label, words in EXPERIENCE_KEYS:
        if matched >= 3:
            break
        if any(word in blob and word in corpus_l for word in words):
            evidence.append((6, f"The advertisement and the profile both mention {label}."))
            matched += 1
    has_full = len(full) >= 280
    if not has_full:
        gaps.append((-30, "The full advertisement was not retrieved, so no application was drafted."))
    for term in HARD_TERMS:
        if term in blob and term not in corpus_l:
            gaps.append((-8, f"{term} appears in the advertisement and is not in the profile or uploaded CV."))
    total = 30 + sum(points for points, _note in evidence) + sum(points for points, _note in gaps)
    total = max(0, min(100, total))
    prepare = has_full and total >= 52 and not (senior and not junior)
    return 30, evidence, gaps, prepare


def ordered_ids(raw: dict, profile: dict) -> list[str]:
    """Put the experience lines that share words with the advertisement first."""
    blob = f"{raw['title']} {raw.get('summary', '')} {raw.get('full_text', '')}".lower()
    key_map = {label: words for label, words in EXPERIENCE_KEYS}
    ranked = []
    for item in profile.get("experience") or []:
        hits = sum(1 for token in key_map.get(item["id"], ()) if token in blob)
        ranked.append((hits, item["id"]))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [item_id for _hits, item_id in ranked]


def live_letter(profile: dict, raw: dict) -> list[str]:
    """Write a letter that quotes this advertisement and only matching experience.

    Two roles do not share a body. A requirement is quoted, then paired with
    one saved fact, or named as uncovered when the profile does not meet it.
    """
    role = profile.get("currentRole") or "an applicant"
    if role.lower().startswith(("a ", "an ")):
        role_phrase = role
    else:
        article = "an" if role[:1].lower() in "aeiou" else "a"
        role_phrase = f"{article} {role}"
    organisation = profile.get("organisation") or "the recorded organisation"
    if not organisation.lower().startswith(("the ", "a ", "an ")):
        organisation = "the " + organisation
    full = raw.get("full_text") or ""
    facts = profile.get("experience") or []
    corpus = " ".join(item.get("text", "") for item in facts).lower()
    matched = []
    unmatched = []
    used = set()
    for line in requirement_lines(full):
        fact = best_fact(line, facts)
        if fact and fact["id"] not in used:
            matched.append((line, fact["text"]))
            used.add(fact["id"])
        else:
            unmatched.append(line)
    paragraphs = [
        (
            f"I am applying for the {raw['title']} role at {raw['company']}. "
            f"I am {role_phrase} in {organisation}."
        )
    ]
    if matched:
        quote, fact = matched[0]
        paragraphs.append(
            f"The full {raw['platform']} advertisement says: \"{quote}\" "
            f"The closest work I can point to is this: {fact}"
        )
    if len(matched) > 1:
        quote, fact = matched[1]
        paragraphs.append(
            f"It also says: \"{quote}\" That lines up with this part of my work: {fact}"
        )
    named_gap = False
    for term in HARD_TERMS:
        if term in full.lower() and term not in corpus:
            paragraphs.append(
                f"The advertisement mentions {term}. That is not in my recorded work, so I am not claiming it."
            )
            named_gap = True
            break
    if unmatched and not named_gap:
        paragraphs.append(
            f"One part of this advertisement is not covered by my recorded work: \"{unmatched[0]}\""
        )
    paragraphs.append(
        "This letter quotes the full advertisement, not the search card. "
        "Download it only after a person has checked the wording."
    )
    return paragraphs


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
