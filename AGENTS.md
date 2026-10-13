# Hong Kong Studentship / Scholarship Radar

Workspace rules for every agent. Read this file before writing anything.

## Profile (confirmed)

- Degree: research postgraduate, PhD or MPhil
- Field: Computing Mathematics (applied / computational mathematics). Mathematics departments and computing-related mathematics programmes both count.
- Intake: 2027/28, the round open on official pages as of this run
- Residency: local student, Hong Kong permanent resident
- Funding priority: monthly living stipend (postgraduate studentship) first. Fellowships and tuition waivers are a plus, not a substitute.
- Ranking: tag and sort strong matches first. Keep weaker and out-of-scope schemes visible and tagged.
- Sources: official university, RGC, or UGC public pages only
- Unknown amounts and deadlines stay `unknown`. Never invent HKD figures or dates.
- Login-only systems: set `login_required` true and skip private details
- Schemes restricted to non-local students: `weak` or `out_of_scope`

## Who writes where

- Orchestrator owns `AGENTS.md`, merge files, `outputs/trajectory.md`, and the final HTML ship.
- Each University Scout writes only `outputs/per_university/<code>.json`.
- Codes: `hku`, `cuhk`, `hkust`, `cityu`, `polyu`, `hkbu`, `lingnan`, `eduhk`, `hkpfs`.
- Do not edit another scout's file. Do not commit or push.

## Research rules

- Official public pages only. Discover real URLs by search and open them. Do not invent portals.
- Acceptable hosts: the assigned university's official domain, `ugc.edu.hk`, and `rgc.edu.hk` (including subdomains).
- If a page is behind login, record `login_required: true` and only the public text.
- If an amount or deadline is not printed on the page, use the string `unknown`. Do not estimate, convert, or recall a figure from memory.
- If a page states an amount or date, copy it as printed and keep the source URL on that row. Do not round or annualise unless the page itself does.
- Record schemes that do not fit the profile. Tag them. Do not drop them.
- Empty search is allowed. Write the file anyway, with `opportunities: []` and a `blockers` note. Never fabricate a scheme to fill the list.

## Match tags

- `strong`: local students eligible, PhD and/or MPhil, monthly stipend or postgraduate studentship, and the scheme is university-wide or open to mathematics / computational mathematics. Intake is the current open round or explicitly 2027/28.
- `possible`: same population might qualify, but field, intake, stipend, or deadline is not stated, or the scheme is a fellowship / tuition waiver rather than a monthly studentship.
- `weak`: poor fit that is still a real scheme (taught-master only, undergraduate, another faculty with no mathematics path, or non-local preference that does not fully exclude locals).
- `out_of_scope`: restricted to non-local students, or clearly not a research-postgraduate funding scheme.

## JSON shape

Write one JSON object. UTF-8. No trailing commentary.

```json
{
  "university_code": "hku",
  "university_name": "The University of Hong Kong",
  "scouted_at": "2026-10-13",
  "profile_ref": "rpg-computing-mathematics-local-2027-28",
  "sources_consulted": [
    {
      "url": "https://example.edu/page",
      "title": "Page title as fetched",
      "accessed": "2026-10-13",
      "note": "what this page contributed"
    }
  ],
  "opportunities": [
    {
      "id": "hku-short-slug",
      "name": "Scheme name as printed",
      "university": "HKU",
      "university_code": "hku",
      "type": "studentship",
      "eligibility_clues": ["short facts copied from the page"],
      "amount": "unknown",
      "amount_note": "quote or unknown",
      "deadline": "unknown",
      "deadline_note": "quote or unknown",
      "source_url": "https://example.edu/page",
      "match_tag": "strong",
      "match_rationale": "one or two sentences tied to the confirmed profile",
      "login_required": false,
      "intake_relevance": "unknown",
      "restrictions": []
    }
  ],
  "blockers": []
}
```

`type` is one of: `studentship`, `fellowship`, `tuition_waiver`, `scholarship`, `other`.

`amount` and `deadline` are either the string `unknown` or a short verbatim phrase from the page (for example `HK$18,000 per month` only if that phrase appears on the cited URL).

Sort `opportunities` by match tag: strong, possible, weak, out_of_scope.
