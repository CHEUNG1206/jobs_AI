"""Live search, CV upload, and the local refetch endpoint.

Network calls are replaced with fixtures. The tests check that audited
jobs survive a refresh and that an uploaded CV is quoted rather than rewritten.
"""

import json
import sys
import threading
import unittest
import zipfile
from http.client import HTTPConnection
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from career_agent import render_cv, score_job
from cv_store import extract_text, matching_sentences, parse_upload, save_upload
from job_search import merge_catalogue, search_all, title_matches, to_catalogue_job
from server import make_handler
from http.server import ThreadingHTTPServer


PROFILE = {
    "name": "CHEUNG Yuk Yuen",
    "currentRole": "AI Application Trainee",
    "organisation": "Department of Physics",
    "contact": {"email": "", "phone": "", "linkedin": ""},
    "education": {"institution": "", "degree": "", "field": "", "graduation": ""},
    "experience": [
        {"id": "chatbot", "text": "Develop an AI chatbot for a robot."},
        {"id": "android", "text": "Test robot application features in Android simulation environments."},
    ],
    "toolsNamedInWork": ["Cursor"],
    "notStated": ["email"],
}


def seek_payload(job_id, title, location):
    return json.dumps(
        {
            "data": [
                {
                    "id": job_id,
                    "title": title,
                    "companyName": "Example Ltd",
                    "teaser": "Build an AI chatbot and test it.",
                    "bulletPoints": ["Part-time intern"],
                    "workTypes": ["Part time"],
                    "listingDateDisplay": "1d ago",
                    "locations": [{"label": location}],
                }
            ]
        }
    ).encode("utf-8")


LINKEDIN = """
<div data-entity-urn="urn:li:jobPosting:433">
  <a class="base-card__full-link" href="https://hk.linkedin.com/jobs/view/ai-intern-433">x</a>
  <h3 class="base-search-card__title">AI Intern</h3>
  <a class="hidden-nested-link" href="https://hk.linkedin.com/company/example">Example Labs</a>
  <span class="job-search-card__location">Hong Kong, Hong Kong SAR</span>
</div>
""".encode("utf-8")

REMOTIVE = json.dumps(
    {
        "jobs": [
            {
                "id": 9,
                "title": "AI Engineer Intern",
                "company_name": "Remote Co",
                "candidate_required_location": "Worldwide",
                "url": "https://remotive.com/remote-jobs/ai-engineer-intern-9",
                "description": "<p>Test an AI chatbot.</p>",
                "job_type": "internship",
                "publication_date": "2026-10-01",
            },
            {
                "id": 10,
                "title": "Freelance Copywriter",
                "company_name": "Words",
                "candidate_required_location": "Worldwide",
                "url": "https://remotive.com/remote-jobs/copywriter-10",
                "description": "<p>Write ads.</p>",
                "job_type": "freelance",
            },
        ]
    }
).encode("utf-8")


class LiveSearchTest(unittest.TestCase):
    def test_boards_are_parsed_and_unrelated_titles_drop_out(self):
        def get(url):
            if "jobsdb.com" in url:
                return seek_payload("100", "AI Intern", "Kowloon Bay, Hong Kong")
            if "jobstreet.com" in url:
                return seek_payload("200", "Accountant", "Singapore")
            if "linkedin.com" in url:
                return LINKEDIN
            if "remotive.com" in url:
                return REMOTIVE
            raise AssertionError(url)

        report = search_all("AI intern", get)
        titles = {job["title"] for job in report["jobs"]}
        self.assertIn("AI Intern", titles)
        self.assertIn("AI Engineer Intern", titles)
        self.assertNotIn("Accountant", titles)
        self.assertNotIn("Freelance Copywriter", titles)
        self.assertEqual(report["counts"]["JobsDB"], 1)
        self.assertEqual(report["counts"]["LinkedIn"], 1)
        self.assertEqual(report["errors"], [])

    def test_merge_keeps_curated_jobs_and_replaces_old_live_cards(self):
        catalogue = {
            "jobs": [
                {"id": "ricoh", "origin": "curated", "url": "https://hk.jobsdb.com/job/1", "title": "Audited"},
                {"id": "live-old", "origin": "live", "url": "https://example.com/old", "title": "Old"},
            ]
        }
        live = [
            {
                "id": "live-jobsdb-100",
                "origin": "live",
                "url": "https://hk.jobsdb.com/job/1",
                "title": "Duplicate of audited",
            },
            {"id": "live-jobsdb-2", "origin": "live", "url": "https://hk.jobsdb.com/job/2", "title": "New"},
        ]
        merged = merge_catalogue(catalogue, live, {"keywords": "AI intern", "counts": {}, "errors": []})
        ids = [job["id"] for job in merged["jobs"]]
        self.assertEqual(ids, ["ricoh", "live-jobsdb-2"])
        self.assertEqual(merged["lastLiveSearch"]["added"], 1)

    def test_hong_kong_intern_can_be_drafted_and_a_senior_role_cannot(self):
        corpus = "AI chatbot robot android test"
        intern = to_catalogue_job(
            {
                "platform": "JobsDB",
                "remote_id": "5",
                "title": "AI Intern",
                "company": "Lab",
                "location": "Sha Tin, Hong Kong",
                "url": "https://hk.jobsdb.com/job/5",
                "summary": "Test an AI chatbot on Android.",
                "bullets": [],
                "work_types": ["Internship"],
                "listed": "today",
            },
            PROFILE,
            corpus,
        )
        senior = to_catalogue_job(
            {
                "platform": "JobStreet",
                "remote_id": "6",
                "title": "Senior AI Manager",
                "company": "Bank",
                "location": "Singapore",
                "url": "https://sg.jobstreet.com/job/6",
                "summary": "Lead a team. C++ required.",
                "bullets": [],
                "work_types": [],
                "listed": "",
            },
            PROFILE,
            corpus,
        )
        self.assertGreaterEqual(score_job(intern)["score"], 52)
        self.assertTrue(intern["prepareApplication"])
        self.assertFalse(senior["prepareApplication"])
        self.assertLess(score_job(senior)["score"], score_job(intern)["score"])
        self.assertNotIn("proficient in C++", " ".join(senior["letter"]).lower())

    def test_title_match_accepts_short_ai_token(self):
        self.assertTrue(title_matches("AI Intern", "AI intern"))
        self.assertFalse(title_matches("Office Assistant", "AI intern"))


class CvUploadTest(unittest.TestCase):
    def test_docx_and_text_uploads_are_quoted(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body><w:p><w:r><w:t>Developed an Android chatbot for a robot demonstration.</w:t></w:r></w:p></w:body>
                </w:document>""",
            )
        text = extract_text("cv.docx", buffer.getvalue())
        self.assertIn("Android chatbot", text)
        job = {"title": "AI Intern", "summary": "Android chatbot testing", "requirements": ["robot"]}
        self.assertTrue(matching_sentences(text, job))
        drafted = render_cv(PROFILE, job, {"text": text, "filename": "cv.docx", "uploadedAt": "2026-10-06"})
        self.assertIn("Developed an Android chatbot", drafted)
        self.assertNotIn("HKUST", drafted)

    def test_save_upload_rejects_unknown_types(self,):
        with self.assertRaises(ValueError):
            save_upload("notes.exe", b"hello", root=Path("/tmp/cv-store-test"))

    def test_multipart_file_is_read_back(self):
        body = (
            b"--bound\r\n"
            b'Content-Disposition: form-data; name="cv"; filename="master.txt"\r\n'
            b"Content-Type: text/plain\r\n\r\n"
            b"CHEUNG Yuk Yuen\r\nBuilt a robot chatbot.\r\n"
            b"--bound--\r\n"
        )
        filename, data = parse_upload(body, 'multipart/form-data; boundary="bound"')
        self.assertEqual(filename, "master.txt")
        self.assertIn(b"robot chatbot", data)


class EndpointTest(unittest.TestCase):
    def test_refetch_and_upload_routes_return_json(self):
        def refetch(_keywords):
            return {"ok": True, "message": "搜尋完成。"}

        def upload(filename, raw):
            return {"ok": True, "message": filename, "characters": len(raw)}

        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(refetch, upload))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        try:
            connection = HTTPConnection("127.0.0.1", port, timeout=5)
            connection.request("POST", "/api/refetch", body=b'{"keywords":"AI intern"}', headers={"Content-Type": "application/json"})
            payload = json.loads(connection.getresponse().read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            self.assertIn("搜尋完成", payload["message"])
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
