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

from career_agent import classify, load_json, render_cv, render_letter, run, score_job


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
        self.assertEqual(intern, 45 + 16 + 12 + 8 + 6 - 10 - 8)
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

    def test_run_writes_tracker_page_and_letters(self):
        report = run()
        self.assertIn("ricoh-fde-intern", report["drafts"])
        self.assertIn("dbs-map-2027-ai", report["holds"])
        letter = ROOT / "applications" / "ricoh-fde-intern" / "cover-letter.md"
        self.assertTrue(letter.exists())
        self.assertIn("College of Science Information Day", letter.read_text(encoding="utf-8"))
        page = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("建議起草", page)
        self.assertIn("已排除", page)
        self.assertIn("不建議現在提交", page)
        self.assertIn("立即重新搜尋", page)
        self.assertIn('id="cv-file"', page)
        self.assertNotIn("applications/hkpc-technical-officer/cv.md", page)
        tracker = json.loads((ROOT / "data" / "tracker.json").read_text(encoding="utf-8"))
        self.assertEqual(tracker["items"]["hkpc-technical-officer"]["status"], "closed")
        self.assertFalse(tracker["items"]["ricoh-fde-intern"]["applied"])


if __name__ == "__main__":
    unittest.main()
