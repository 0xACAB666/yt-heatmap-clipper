import unittest
from unittest.mock import patch

from yt_heatmap_clipper.engine import run_clip_job
from yt_heatmap_clipper.models import ClipJobRequest, HeatmapSegment
from yt_heatmap_clipper.rendering import build_crop_command
from yt_heatmap_clipper.youtube import extract_video_id


class YoutubeTests(unittest.TestCase):
    def test_extract_video_id_preserves_supported_urls(self):
        self.assertEqual(extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(
            extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=share"),
            "dQw4w9WgXcQ",
        )
        self.assertEqual(extract_video_id("https://youtube.com/shorts/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertIsNone(extract_video_id("https://example.com/watch?v=dQw4w9WgXcQ"))

    def test_extract_video_id_rejects_unsafe_or_invalid_ids(self):
        self.assertIsNone(extract_video_id("https://www.youtube.com/watch?v=<script>"))
        self.assertIsNone(extract_video_id("https://youtu.be/too-short"))
        self.assertIsNone(extract_video_id("https://youtube.com/shorts/invalid/extra"))


class RenderingTests(unittest.TestCase):
    def test_build_crop_command_preserves_filters(self):
        default_command = build_crop_command("default", "input.mp4", "output.mp4")
        split_left_command = build_crop_command("split_left", "input.mp4", "output.mp4")
        split_right_command = build_crop_command("split_right", "input.mp4", "output.mp4")

        self.assertIn("scale=-2:1280,crop=720:1280:(iw-720)/2:(ih-1280)/2", default_command)
        self.assertIn("[s2]crop=720:320:0:ih-320[bottom]", " ".join(split_left_command))
        self.assertIn("[s2]crop=720:320:iw-720:ih-320[bottom]", " ".join(split_right_command))


class EngineTests(unittest.TestCase):
    @patch("yt_heatmap_clipper.engine.os.makedirs")
    @patch("yt_heatmap_clipper.engine.process_clip")
    @patch("yt_heatmap_clipper.engine.get_duration", return_value=120)
    @patch("yt_heatmap_clipper.engine.fetch_most_replayed")
    def test_run_clip_job_emits_synchronous_progress_events(
        self,
        fetch_most_replayed,
        get_duration,
        process_clip,
        makedirs,
    ):
        fetch_most_replayed.return_value = [
            HeatmapSegment(start=10, duration=20, score=0.9),
            HeatmapSegment(start=50, duration=10, score=0.8),
        ]
        process_clip.side_effect = [True, True]
        events = []

        result = run_clip_job(ClipJobRequest("abc123"), on_event=events.append)

        self.assertEqual(result.success_count, 2)
        self.assertEqual(result.total_segments, 2)
        self.assertEqual(
            [event.type for event in events],
            [
                "queued",
                "running",
                "clip_started",
                "clip_finished",
                "clip_started",
                "clip_finished",
                "completed",
            ],
        )
        self.assertEqual(events[1].total_segments, 2)
        process_clip.assert_any_call(
            "abc123",
            fetch_most_replayed.return_value[0],
            1,
            120,
            "default",
            False,
            None,
            "clips",
            None,
        )
        process_clip.assert_any_call(
            "abc123",
            fetch_most_replayed.return_value[1],
            2,
            120,
            "default",
            False,
            None,
            "clips",
            None,
        )


if __name__ == "__main__":
    unittest.main()
