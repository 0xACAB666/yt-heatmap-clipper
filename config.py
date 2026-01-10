"""
Configuration constants for YouTube Heatmap Clipper.
"""

# Output settings
OUTPUT_DIR = "clips"      # Directory where generated clips will be saved
MAX_CLIPS = 10            # Maximum number of clips to generate per video
MAX_WORKERS = 1           # Number of parallel workers (reserved for future concurrency)

# Clip settings
MAX_DURATION = 60         # Maximum duration (in seconds) for each clip
MIN_SCORE = 0.40          # Minimum heatmap intensity score to be considered viral
PADDING = 10              # Extra seconds added before and after each detected segment

# Crop settings
TOP_HEIGHT = 960          # Height for top section (center content) in split mode
BOTTOM_HEIGHT = 320       # Height for bottom section (facecam) in split mode

# AI settings
USE_SUBTITLE = True       # Enable auto subtitle using Faster-Whisper (4-5x faster)
WHISPER_MODEL = "tiny"   # Whisper model size: tiny, base, small, medium, large
USE_AI_FALLBACK = True    # Use AI-based engagement detection if heatmap unavailable
AI_MIN_SCORE = 0.50       # Minimum AI engagement score (0.0-1.0)
