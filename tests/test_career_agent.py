"""Checks for the job-search workflow.

The tests lock the decisions that matter: closed listings stay out of the
draft pile, scores match the written points, and drafted text does not
invent a degree or a programming language.
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import tempfile

from career_agent import (
    classify,
    confirm_tracker,
    load_json,
    render_cv,
    render_letter,
    run,
    save_json,
    score_job,
    set_tracker_status,
)


class CareerAgentTest(unittest.TestCase):
    def setUp(self):
        self.profile = load_json(ROOT / "data" / "profile.json")
        self.jobs = load_json(ROOT / "data" / "jobs.json")["jobs"]
        self.by_id = {job["id"]: job for job in self.jobs}

    def test_closed_roles_are_excluded_and_not_scored_as_matches(self):
        groups = classify(self.jobs, {"items": {}})
        excluded_ids = {row["job"]["id"] for row in groups["excluded"]}
        self.assertIn("hkpc-technical-officer", excluded_ids)
        self.assertIn("macroview-solution-engineer", excluded_ids)
        self.assertIn("pharmcare-ai-trainee", excluded_ids)
        draft_ids = {row["job"]["id"] for row in groups["drafts"]}
        self.assertTrue(draft_ids.isdisjoint(excluded_ids))
        self.assertEqual(score_job(self.by_id["hkpc-technical-officer"])["score"], 0)

    def test_already_applied_roles_drop_out_of_drafts(self):
        groups = classify(
            self.jobs,
            {"items": {"ricoh-fde-associate": {"applied": True, "status": "applied"}}},
        )
        draft_ids = [row["job"]["id"] for row in groups["drafts"]]
        self.assertNotIn("ricoh-fde-associate", draft_ids)
        self.assertIn("ricoh-fde-associate", {row["job"]["id"] for row in groups["excluded"]})

    def test_scores_follow_the_audited_points(self):
        intern = score_job(self.by_id["ricoh-fde-intern"])["score"]
        # The -10 penalty applied only while the JobsDB body was missing.
        self.assertEqual(intern, 45 + 16 + 12 + 8 + 6 - 8)
        specialist = score_job(self.by_id["ricoh-ai-specialist"])["score"]
        self.assertLess(specialist, intern)
        self.assertLess(specialist, 40)

    def test_draft_text_does_not_invent_credentials(self):
        job = self.by_id["precision-robotics-intern"]
        cv = render_cv(self.profile, job)
        letter = render_letter(self.profile, job)
        combined = cv + letter
        self.assertIn("[fill in]", cv)
        self.assertNotIn("HKUST", combined)
        self.assertNotIn("proficient in C++", combined.lower())
        self.assertIn("C++ is not in my recorded work", letter)
        smartage = render_letter(self.profile, self.by_id["smartage-swe-ai"])
        self.assertIn("not part of the work recorded in my profile", smartage)

    def test_card_without_a_body_is_not_drafted(self):
        job = {
            "id": "card-only",
            "listingStatus": "open_live",
            "prepareApplication": True,
            "fullText": "too short",
            "baseScore": 80,
            "evidence": [],
            "gaps": [],
        }
        groups = classify([job], {"items": {}})
        self.assertEqual(groups["drafts"], [])
        self.assertEqual(groups["holds"][0]["job"]["id"], "card-only")

    def test_status_is_written_to_the_tracker_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.json"
            save_json(
                path,
                {"items": {"ricoh-fde-intern": {"status": "hold", "applied": False, "confirmed": False}}},
            )
            set_tracker_status("ricoh-fde-intern", "applied", path)
            item = load_json(path)["items"]["ricoh-fde-intern"]
            self.assertEqual(item["status"], "applied")
            self.assertTrue(item["applied"])
            confirm_tracker("ricoh-fde-intern", path)
            item = load_json(path)["items"]["ricoh-fde-intern"]
            self.assertTrue(item["confirmed"])
            self.assertEqual(item["status"], "applied")

    def test_run_writes_tracker_page_and_letters(self):
        report = run()
        self.assertIn("ricoh-fde-intern", report["drafts"])
        self.assertIn("dbs-map-2027-ai", report["holds"])
        self.assertIn("precision-robotics-intern", report["holds"])
        letter = ROOT / "applications" / "ricoh-fde-intern" / "cover-letter.md"
        self.assertTrue(letter.exists())
        letter_text = letter.read_text(encoding="utf-8")
        self.assertIn("quotes the full advertisement", letter_text)
        self.assertNotIn("full JobsDB text was not available", letter_text)
        self.assertFalse((ROOT / "applications" / "precision-robotics-intern" / "cover-letter.md").exists())
        page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("建議起草", page)
        self.assertIn("已排除", page)
        self.assertIn("未讀到完整職缺", page)
        self.assertIn("確認後才能下載", page)
        self.assertIn("檔案狀態", page)
        self.assertIn("立即重新搜尋", page)
        self.assertIn('id="cv-file"', page)
        self.assertNotIn("localStorage.setItem", page)
        self.assertNotIn("applications/hkpc-technical-officer/cv.md", page)
        tracker = json.loads((ROOT / "data" / "tracker.json").read_text(encoding="utf-8"))
        self.assertEqual(tracker["items"]["hkpc-technical-officer"]["status"], "closed")
        self.assertFalse(tracker["items"]["ricoh-fde-intern"]["applied"])
        self.assertIn("confirmed", tracker["items"]["ricoh-fde-intern"])


if __name__ == "__main__":
    unittest.main()
