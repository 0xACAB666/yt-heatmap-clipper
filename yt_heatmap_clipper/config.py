OUTPUT_DIR = "clips"
MAX_DURATION = 60
MIN_SCORE = 0.40
MAX_CLIPS = 10
MAX_WORKERS = 1
PADDING = 10
TOP_HEIGHT = 960
BOTTOM_HEIGHT = 320
USE_SUBTITLE = True
# Set to a model name to force a shared default; keep None to use hardware-based
# automatic recommendation when a run does not request a model explicitly.
WHISPER_MODEL = None

MODEL_SIZES = {
    "tiny": "75 MB",
    "base": "142 MB",
    "small": "466 MB",
    "medium": "1.5 GB",
    "large-v1": "2.9 GB",
    "large-v2": "2.9 GB",
    "large-v3": "2.9 GB",
}
