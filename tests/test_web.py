import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from yt_heatmap_clipper.models import ClipJobResult, ProgressEvent
from yt_heatmap_clipper.web.app import JobRegistry, create_app


class WebDashboardTests(unittest.TestCase):
    def setUp(self):
        self.registry = JobRegistry()
        self.client = TestClient(create_app(self.registry))

    def test_landing_page_renders_form_and_capabilities(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Local utility dashboard", response.text)
        self.assertIn("YouTube URL", response.text)
        self.assertIn("Environment", response.text)

    def test_invalid_submission_is_rejected(self):
        response = self.client.post("/jobs", data={"youtube_url": "https://example.com/watch?v=dQw4w9WgXcQ"})

        self.assertEqual(response.status_code, 422)

    @patch("yt_heatmap_clipper.web.app.Thread")
    def test_submission_creates_isolated_job_and_redirects(self, thread_class):
        response = self.client.post(
            "/jobs",
            data={
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "crop_mode": "split_right",
                "use_subtitle": "on",
                "requested_model": "base",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        job = self.registry.recent()[0]
        self.assertTrue(job.request.output_dir.endswith(job.id))
        self.assertTrue(job.request.work_dir.endswith(job.id))
        self.assertEqual(job.request.requested_model, "base")
        self.assertEqual(response.headers["location"], f"/jobs/{job.id}")
        thread_class.assert_called_once()

    def test_status_and_clip_routes_report_job_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "clips"
            output_dir.mkdir()
            clip_path = output_dir / "clip_1.mp4"
            clip_path.write_bytes(b"video")
            job = self.registry.create(
                request=_request_for(output_dir),
                job_id="job123",
            )
            self.registry.update_event("job123", ProgressEvent("running", total_segments=2))
            self.registry.complete("job123", ClipJobResult("abc123", success_count=1, total_segments=2))

            status_response = self.client.get("/jobs/job123/status")
            clip_response = self.client.get("/jobs/job123/clips/clip_1.mp4")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "completed")
        self.assertEqual(status_response.json()["latest_event"]["type"], "completed")
        self.assertEqual(status_response.json()["clips"], ["clip_1.mp4"])
        self.assertEqual(clip_response.status_code, 200)
        self.assertEqual(clip_response.content, b"video")

    def test_job_page_includes_live_status_polling(self):
        self.registry.create(request=_request_for(Path("clips/web/job123")), job_id="job123")

        response = self.client.get("/jobs/job123")

        self.assertEqual(response.status_code, 200)
        self.assertIn('fetch("/jobs/job123/status")', response.text)
        self.assertIn('setInterval(refreshJob, 1500)', response.text)

    def test_submission_rejects_malicious_video_id(self):
        response = self.client.post(
            "/jobs",
            data={"youtube_url": "https://www.youtube.com/watch?v=<script>alert(1)</script>"},
        )

        self.assertEqual(response.status_code, 422)

    def test_job_page_escapes_dynamic_video_id(self):
        from yt_heatmap_clipper.models import ClipJobRequest

        self.registry.create(
            request=ClipJobRequest(
                "<script>alert(1)</script>",
                output_dir="clips/web/job123",
                work_dir="clips/web/job123/work",
            ),
            job_id="job123",
        )

        response = self.client.get("/jobs/job123")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>alert(1)</script>", response.text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", response.text)


def _request_for(output_dir: Path):
    from yt_heatmap_clipper.models import ClipJobRequest

    return ClipJobRequest("abc123", output_dir=str(output_dir), work_dir=str(output_dir / "work"))


if __name__ == "__main__":
    unittest.main()
