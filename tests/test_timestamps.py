import unittest
from launcher import extract_video_id, parse_timestamp, timestamp_label


class TimestampTests(unittest.TestCase):
    def test_seconds_and_clock_formats(self):
        self.assertEqual(parse_timestamp("100"), 100)
        self.assertEqual(parse_timestamp("01:40"), 100)
        self.assertEqual(parse_timestamp("00:01:40.500"), 100.5)

    def test_rejects_invalid_timestamps(self):
        for value in ("", "-1", "NaN", "inf", "1:60", "1:2:60", "1:2:3:4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_timestamp(value)

    def test_filename_timestamp(self):
        self.assertEqual(timestamp_label(3661), "01-01-01")


class YouTubeUrlTests(unittest.TestCase):
    def test_watch_short_and_shorts(self):
        video_id = "dQw4w9WgXcQ"
        self.assertEqual(extract_video_id(f"https://youtube.com/watch?v={video_id}"), video_id)
        self.assertEqual(extract_video_id(f"https://youtu.be/{video_id}"), video_id)
        self.assertEqual(extract_video_id(f"https://youtube.com/shorts/{video_id}"), video_id)

    def test_rejects_non_youtube_url(self):
        self.assertIsNone(extract_video_id("https://example.com/video"))


if __name__ == "__main__":
    unittest.main()
