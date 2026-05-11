from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "midia"
WINDOW_NAME = "VanCoco"


class AppState(Enum):
    WARMING_UP = "warming_up"
    IDLE_BLACK_SCREEN = "idle_black_screen"
    PLAYING_VIDEO = "playing_video"
    WAITING_PRESENTATION = "waiting_presentation"
    WAITING_COCOMAG_ACTION = "waiting_cocomag_action"
    WAITING_COCOMAG_ACTION_COMPLETION = "waiting_cocomag_action_completion"
    WAITING_VIDEO5_TRIGGER = "waiting_video5_trigger"
    WAITING_COCOVISION_ACTION_COMPLETION = "waiting_cocovision_action_completion"
    WAITING_COLOR = "waiting_color"
    WAITING_VIDEO6_TRIGGER = "waiting_video6_trigger"
    WAITING_COCOVISION_RETURN_COMPLETION = "waiting_cocovision_return_completion"
    WAITING_VIDEO8_TRIGGER = "waiting_video8_trigger"
    WAITING_VIDEO9_TRIGGER = "waiting_video9_trigger"


class GestureName(Enum):
    HAND_OPEN = "HAND_OPEN"
    POINT = "POINT"
    V_SIGN = "V_SIGN"
    THUMB_UP = "THUMB_UP"
    CLOSED_FIST = "CLOSED_FIST"
    DOUBLE_CLOSED_FIST = "DOUBLE_CLOSED_FIST"
    PRAYER_HANDS = "PRAYER_HANDS"


class CameraTriggerName(Enum):
    MAGNIFIER_MARKER_DETECTED = "magnifier_marker_detected"
    DOUBLE_CLOSED_FIST_DETECTED = "double_closed_fist_detected"


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
    GestureName.CLOSED_FIST: VideoAction(
        gesture=GestureName.CLOSED_FIST,
        video_path=MEDIA_DIR / "video6.mp4",
    ),
}

VIDEO3_PATH = MEDIA_DIR / "video3.mp4"
VIDEO4_PATH = MEDIA_DIR / "video4.mp4"
VIDEO7_PATH = MEDIA_DIR / "video7.mp4"
VIDEO8_PATH = MEDIA_DIR / "video8.mp4"
VIDEO9_SUCCESS_PATH = MEDIA_DIR / "video9a.mp4"
VIDEO9_FAILURE_PATH = MEDIA_DIR / "video9b.mp4"
COLOR_VIDEO_PATHS = {
    "COLOR_BLUE": VIDEO7_PATH,
}

#if you want to change the final outcome -> FINAL_OUTCOME = "failure"
# or FINAL_OUTCOME = "success"
FINAL_OUTCOME = "failure"  
FINAL_VIDEO_PATHS = {
    "success": VIDEO9_SUCCESS_PATH,
    "failure": VIDEO9_FAILURE_PATH,
}


KEY_ACTIONS = {
    ord("1"): GestureName.HAND_OPEN,
    ord("2"): GestureName.POINT,
}


EXIT_KEYS = {ord("q"), 27}
CAMERA_INDEX = 0
CAMERA_WARMUP_FRAMES = 5
VISION_READY_FRAMES = 8
CAMERA_FRAME_WIDTH = 640
CAMERA_FRAME_HEIGHT = 360
CAMERA_BUFFER_SIZE = 1
CAMERA_TARGET_FPS = 30
CAMERA_USE_MJPG = True
VISION_PROCESSING_SCALE = 0.9
DETECTION_CONFIDENCE = 0.65
TRACKING_CONFIDENCE = 0.65
DEBOUNCE_SECONDS = 1.5
GESTURE_STABLE_FRAMES = 2
GESTURE_MISSING_FRAME_TOLERANCE = 2
VISION_PERF_LOG = False
VISION_PERF_LOG_EVERY = 30
PERF_DIAGNOSTICS = True
VISION_GESTURE_DEBUG = False
TEST_GESTURES_MODE = False
VISION_REJECTION_STATS = True
VISION_CALIBRATION_VIEW = True
VISION_ROI_ENABLED = True
VISION_ROI_X_MIN_RATIO = 0.15
VISION_ROI_X_MAX_RATIO = 0.85
VISION_ROI_Y_MIN_RATIO = 0.05
VISION_ROI_Y_MAX_RATIO = 0.95
VISION_HAND_QUALITY_ENABLED = True
VISION_HAND_MIN_PALM_RATIO = 0.06
VISION_HAND_BORDER_MARGIN_RATIO = 0.01
VISION_HAND_MIN_LANDMARKS_IN_ROI_RATIO = 0.58
ROBOT_NAMES = ("COCOMAG", "COCOVISION")
ROBOT_COMMAND_PRESENT = "PRESENT"
ROBOT_COMMAND_ACTION = "ACTION"
ROBOT_COMMAND_RETURN = "RETURN"
ROBOT_COMMAND_RESET = "RESET"
ROBOT_COMMAND_COLOR_CONFIRMED = "COLOR_CONFIRMED"
MOCK_VIDEO_DURATION_SECONDS = 2.0
PRESENTATION_MODE = True
MOCK_ROBOTS = False
COCOMAG_BAUDRATE = 115200
COCOVISION_BAUDRATE = 115200
CENTRAL_FALLBACK_BAUDRATE = 115200
CENTRAL_FALLBACK_PORT = "/dev/ttyUSB0"
CENTRAL_FALLBACK_TRIGGER_LINE = "CENTRAL_FALLBACK_TRIGGER"
# Linux RFCOMM example:
#   sudo rfcomm bind /dev/rfcomm0 XX:XX:XX:XX:XX:XX 1
COCOMAG_COMM_MODE = "rfcomm"
COCOMAG_PORT = ""
COCOVISION_COMM_MODE = "rfcomm"
COCOVISION_PORT = ""
ARUCO_MARKER_ID = 7
ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8 = True
DOUBLE_CLOSED_FIST_ROI_Y_MAX_RATIO = 0.78
POSE_VISIBILITY_THRESHOLD = 0.6
PRAYER_WRIST_DISTANCE_RATIO = 0.35
PRAYER_CENTER_OFFSET_RATIO = 0.35
PRAYER_CHEST_HEIGHT_MIN_RATIO = -0.1
PRAYER_CHEST_HEIGHT_MAX_RATIO = 0.9
