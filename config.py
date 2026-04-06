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
    WAITING_PRESENTATION = "waiting_presentation"
    WAITING_COCOMAG_ACTION = "waiting_cocomag_action"
    WAITING_COCOMAG_ACTION_COMPLETION = "waiting_cocomag_action_completion"
    WAITING_VIDEO5_TRIGGER = "waiting_video5_trigger"
    WAITING_COCOVISION_ACTION_COMPLETION = "waiting_cocovision_action_completion"
    WAITING_COLOR = "waiting_color"


class GestureName(Enum):
    HAND_OPEN = "HAND_OPEN"
    POINT = "POINT"
    V_SIGN = "V_SIGN"
    THUMB_UP = "THUMB_UP"


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
    GestureName.THUMB_UP: VideoAction(
        gesture=GestureName.THUMB_UP,
        video_path=MEDIA_DIR / "video5.mp4",
    ),
}

VIDEO3_PATH = MEDIA_DIR / "video3.mp4"
VIDEO4_PATH = MEDIA_DIR / "video4.mp4"
VIDEO5_PATH = MEDIA_DIR / "video5.mp4"
COLOR_VIDEO_PATHS = {
    "COLOR_RED": MEDIA_DIR / "video6_red.mp4",
    "COLOR_GREEN": MEDIA_DIR / "video6_green.mp4",
    "COLOR_BLUE": MEDIA_DIR / "video6_blue.mp4",
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
ROBOT_NAMES = ("COCOMAG", "COCOVISION")
ROBOT_COMMAND_PRESENT = "PRESENT"
ROBOT_COMMAND_ACTION = "ACTION"
ROBOT_COMMAND_SCAN = "SCAN"
MOCK_VIDEO_DURATION_SECONDS = 2.0
COCOMAG_BAUDRATE = 115200
COCOVISION_BAUDRATE = 115200
