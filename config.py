from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "midia"
WINDOW_NAME = "VanCoco"


class AppState(Enum):
    IDLE_BLACK_SCREEN = "idle_black_screen"
    PLAYING_VIDEO = "playing_video"


class GestureName(Enum):
    HAND_OPEN = "HAND_OPEN"
    POINT = "POINT"


@dataclass(frozen=True)
class VideoAction:
    gesture: GestureName
    video_path: Path


VIDEO_ACTIONS = {
    GestureName.HAND_OPEN: VideoAction(
        gesture=GestureName.HAND_OPEN,
        video_path=MEDIA_DIR / "video1.mp4",
    ),
    GestureName.POINT: VideoAction(
        gesture=GestureName.POINT,
        video_path=MEDIA_DIR / "video2.mp4",
    ),
}


KEY_ACTIONS = {
    ord("1"): GestureName.HAND_OPEN,
    ord("2"): GestureName.POINT,
}


EXIT_KEYS = {ord("q"), 27}
CAMERA_INDEX = 0
CAMERA_WARMUP_FRAMES = 5
DETECTION_CONFIDENCE = 0.65
TRACKING_CONFIDENCE = 0.65
DEBOUNCE_SECONDS = 1.5
