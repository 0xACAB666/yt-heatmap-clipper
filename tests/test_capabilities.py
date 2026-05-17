import unittest
from types import SimpleNamespace
from unittest.mock import mock_open, patch

from yt_heatmap_clipper.capabilities import detect_capabilities, recommend_acceleration
from yt_heatmap_clipper import subtitles


class CapabilityTests(unittest.TestCase):
    def test_cpu_fallback_recommends_int8_and_base(self):
        report = detect_capabilities(
            ffmpeg_lookup=lambda _: None,
            module_available=lambda _: False,
            cuda_device_count=lambda: 0,
        )

        self.assertFalse(report.ffmpeg_available)
        self.assertFalse(report.subtitle_backend_available)
        self.assertEqual(report.acceleration.device, "cpu")
        self.assertEqual(report.acceleration.compute_type, "int8")
        self.assertEqual(report.whisper_model.name, "base")

    def test_cuda_branch_recommends_float16_and_small(self):
        report = detect_capabilities(
            ffmpeg_lookup=lambda _: "/usr/bin/ffmpeg",
            module_available=lambda _: True,
            cuda_device_count=lambda: 1,
        )

        self.assertTrue(report.ffmpeg_available)
        self.assertTrue(report.subtitle_backend_available)
        self.assertEqual(report.acceleration.device, "cuda")
        self.assertEqual(report.acceleration.compute_type, "float16")
        self.assertEqual(report.whisper_model.name, "small")

    def test_requested_model_beats_configured_model(self):
        report = detect_capabilities(
            requested_model="large-v3",
            configured_model="tiny",
            cuda_device_count=lambda: 0,
        )

        self.assertEqual(report.whisper_model.name, "large-v3")
        self.assertIn("explicitly requested", report.whisper_model.reason)

    def test_configured_model_beats_automatic_default(self):
        acceleration = recommend_acceleration(1)
        report = detect_capabilities(
            configured_model="medium",
            cuda_device_count=lambda: 1,
        )

        self.assertEqual(acceleration.device, "cuda")
        self.assertEqual(report.whisper_model.name, "medium")
        self.assertIn("configured default", report.whisper_model.reason)

    def test_generate_subtitle_uses_recommended_device_and_compute_type(self):
        constructor_args = {}

        class FakeWhisperModel:
            def __init__(self, model_name, *, device, compute_type):
                constructor_args.update(
                    model_name=model_name,
                    device=device,
                    compute_type=compute_type,
                )

            def transcribe(self, *_args, **_kwargs):
                return [SimpleNamespace(start=0, end=1, text=" hello ")], None

        fake_report = SimpleNamespace(
            whisper_model=SimpleNamespace(name="small"),
            acceleration=SimpleNamespace(
                device="cuda",
                compute_type="float16",
                reason="test",
            ),
        )

        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=FakeWhisperModel)}):
            with patch.object(subtitles, "detect_capabilities", return_value=fake_report):
                with patch("builtins.open", mock_open()) as file_handle:
                    self.assertTrue(subtitles.generate_subtitle("clip.mp4", "clip.srt"))

        self.assertEqual(
            constructor_args,
            {"model_name": "small", "device": "cuda", "compute_type": "float16"},
        )
        file_handle.assert_called_once_with("clip.srt", "w", encoding="utf-8")

    def test_generate_subtitle_uses_cpu_recommendation_without_override(self):
        constructor_args = {}

        class FakeWhisperModel:
            def __init__(self, model_name, *, device, compute_type):
                constructor_args.update(
                    model_name=model_name,
                    device=device,
                    compute_type=compute_type,
                )

            def transcribe(self, *_args, **_kwargs):
                return [], None

        def detect_cpu_capabilities(*, requested_model=None, configured_model=None):
            return detect_capabilities(
                requested_model=requested_model,
                configured_model=configured_model,
                ffmpeg_lookup=lambda _: "/usr/bin/ffmpeg",
                module_available=lambda _: True,
                cuda_device_count=lambda: 0,
            )

        with patch.dict("sys.modules", {"faster_whisper": SimpleNamespace(WhisperModel=FakeWhisperModel)}):
            with patch.object(subtitles, "WHISPER_MODEL", None):
                with patch.object(subtitles, "detect_capabilities", side_effect=detect_cpu_capabilities):
                    with patch("builtins.open", mock_open()):
                        self.assertTrue(subtitles.generate_subtitle("clip.mp4", "clip.srt"))

        self.assertEqual(
            constructor_args,
            {"model_name": "base", "device": "cpu", "compute_type": "int8"},
        )


if __name__ == "__main__":
    unittest.main()
