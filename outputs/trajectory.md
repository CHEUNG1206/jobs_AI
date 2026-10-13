# Trajectory

Run date: 2026-10-13. Profile: local Hong Kong permanent resident, research postgraduate (PhD or MPhil), Computing Mathematics, 2027/28 intake, monthly stipend first.

## Parallelism

One wave. Nine scouts were launched in the same turn and ran at the same time. There was no second wave.

- HKU: bc-c1593d32-af3b-5b4a-89f3-b14dfb07e15a
- CUHK: bc-aaac7ab1-16df-5721-b6a4-576348806229
- HKUST: bc-50412c2b-0116-5a68-971b-95b8bedd5bfa
- CityU: bc-9c7cb537-fdfb-5fa6-b791-fa2445c00bea
- PolyU: bc-a6283436-d816-520a-9f5f-15127ac07ac3
- HKBU: bc-cb37b019-0041-5845-9e81-bed485f9d568
- Lingnan: bc-0bc53960-6ecb-5eb7-8db0-d9de5bfae3b8
- EdUHK: bc-13d22307-299a-586b-8f8c-649f9413d741
- HKPFS: bc-47727a67-3225-584e-979b-6b272811dbad

Each scout wrote only its own file under `outputs/per_university/`.

## Orchestration

The parent confirmed the profile in chat, wrote `AGENTS.md` with the JSON shape, created branch `cursor/hk-scholarship-radar-e74d`, and assigned one scout per university plus one for the RGC/UGC HKPFS hub. The parent did not collect the university pages. After all nine files arrived, the parent checked that each file parsed and used the shared fields. The critic then ran alone. The parent applied the eight demands, re-sorted tags, and wrote `outputs/opportunities.json` and `outputs/match_summary.json`.

## Routing

Each scout was briefed with one code, one official host family, and search seeds for that university only. HKPFS was limited to `ugc.edu.hk` and `rgc.edu.hk`. University scouts could cite a UGC page only when it named their university. Login-only systems were marked `login_required` instead of being opened.

## Sequence

1. Profile collected in chat and restated.
2. Human ordered the nine scouts launched in parallel.
3. `AGENTS.md` written, then the nine scouts ran together.
4. Parent checked each JSON file as it arrived.
5. Critic pass on the nine files.
6. Parent applied the critic demands and merged.
7. Frontend Builder wrote `outputs/report/index.html` with local CSS and JS. The page loads 192 rows from `../opportunities.json` when a server is available, and from the embedded array when the file is opened directly. A browser check covered the strong filter (14), the CityU-plus-strong empty state, a search with no hits, a detail panel whose source link is the cited HKU postgraduate scholarship page, and a 390px-wide layout.

## Critique loop

Critic `bc-2ac8fcfa-37d3-56ca-b1c0-18f27c7ced97` returned `changes_required` with eight demands. PolyU, EdUHK, and the central HKPFS file passed. Applied afterward:

- `hku-international-postgraduate-scholarship-computer-science`: amount set to `unknown`. The page prints both 25% of tuition and the full 72-credit composition fee.
- `cuhk-hkpfs`: retagged to `strong`. PhD-only stays in the restrictions.
- `hkust-hkpfs`: retagged to `strong`.
- `hkust-pgs`: deadline set to `unknown`. The 1 Jun 2027 date is on the Mathematics catalog, not on the cited fees page.
- `cityu-postgraduate-studentship`: retagged to `possible`. The handbook rate remains the printed 2025/26 figure.
- `hkbu-hkpfs` and `hkbu-hkpfs-elite-scholar-award`: deadlines set to `unknown` because the cited introduction page does not print them.
- `lingnan-hkpfs`: retagged to `possible`. The cited Lingnan page does not show local eligibility.

No new HKD figure was added.

## Controls used

The profile was confirmed in the chat before the scouts were dispatched. `AGENTS.md` is the shared rule file. A separate written plan was not sitting in the repo when the human said to launch the scouts as planned; the launch instruction was the go-ahead used for this run. No Skill and no Memory entry was saved. Google Sheets was not used. Scouts used public web search and page fetches.

## Launch method

Cursor Task tool, subagent type `generalPurpose`, `run_in_background` true. The nine scouts were nine tool calls in one message. The critic was a later Task call with an isolated brief. This was not one parent thread collecting all eight universities.

## Failures / blockers

- PolyU PRPgS subpage returned HTTP 404. The amount came from the Graduate School schemes page.
- HKUST PGS terms PDF returned HTTP 500, so no monthly rate was copied. The Mathematics intranet studentship page did not load.
- `rgc.edu.hk/hkphd` returned HTTP 500. HKPFS procedure text came from the cerg1 apply page.
- CityU live `/pg/` scholarship pages returned no usable text. The studentship rate is the February 2026 handbook's 2025/26 figure.
- EdUHK HKPFS poster and one scholarship PDF redirected to a Microsoft sign-in. Those files were not read.
- Lingnan has no mathematics department. Data Science publishes numerical and computational mathematics as a research area. An ORKT conferences page returned HTTP 403.
- Several department pages still print older cycles (HKU Mathematics 2023–24, CUHK department dates, HKBU CMS 2024/25). Those older amounts and deadlines were not used when a later official page existed.
- Where a page did not print an amount or a deadline, the field stayed `unknown`.
