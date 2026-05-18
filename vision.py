from __future__ import annotations

from dataclasses import dataclass
from math import hypot
import platform
import time
from typing import Optional

import cv2
import mediapipe as mp

from config import (
    ARUCO_MARKER_ID,
    CAMERA_BUFFER_SIZE,
    CAMERA_INDEX,
    CAMERA_FRAME_HEIGHT,
    CAMERA_FRAME_WIDTH,
    CAMERA_WARMUP_FRAMES,
    CAMERA_TARGET_FPS,
    CAMERA_USE_MJPG,
    DETECTION_CONFIDENCE,
    DOUBLE_CLOSED_FIST_ROI_Y_MAX_RATIO,
    DOUBLE_CLOSED_FIST_MIN_CENTER_DISTANCE,
    DOUBLE_CLOSED_FIST_STABLE_FRAMES,
    GestureName,
    PERF_DIAGNOSTICS,
    POSE_VISIBILITY_THRESHOLD,
    PRAYER_CENTER_OFFSET_RATIO,
    PRAYER_CHEST_HEIGHT_MAX_RATIO,
    PRAYER_CHEST_HEIGHT_MIN_RATIO,
    PRAYER_WRIST_DISTANCE_RATIO,
    TEST_GESTURES_MODE,
    TRACKING_CONFIDENCE,
    VISION_CALIBRATION_VIEW,
    VISION_GESTURE_DEBUG,
    VISION_HAND_BORDER_MARGIN_RATIO,
    VISION_HAND_QUALITY_ENABLED,
    VISION_HAND_MIN_LANDMARKS_IN_ROI_RATIO,
    VISION_HAND_MIN_PALM_RATIO,
    VISION_PREVIEW_OVERLAY,
    VISION_READY_FRAMES,
    VISION_REJECTION_STATS,
    VISION_PERF_LOG,
    VISION_PERF_LOG_EVERY,
    VISION_PROCESSING_SCALE,
    VISION_ROI_ENABLED,
    VISION_ROI_X_MAX_RATIO,
    VISION_ROI_X_MIN_RATIO,
    VISION_ROI_Y_MAX_RATIO,
    VISION_ROI_Y_MIN_RATIO,
)


def _resolve_hands_api():
    hands_module = getattr(mp, "solutions", None)
    if hands_module is not None and hasattr(hands_module, "hands"):
        return hands_module.hands

    raise RuntimeError(
        "A instalacao atual do MediaPipe nao expoe 'mediapipe.solutions.hands'. "
        "Este projeto usa a API classica Hands. "
        "Instale uma versao compativel com: "
        "'python3 -m pip uninstall -y mediapipe && "
        "python3 -m pip install mediapipe==0.10.9'"
    )


def _resolve_pose_api():
    pose_module = getattr(mp, "solutions", None)
    if pose_module is not None and hasattr(pose_module, "pose"):
        return pose_module.pose

    raise RuntimeError(
        "A instalacao atual do MediaPipe nao expoe 'mediapipe.solutions.pose'. "
        "Este projeto usa a API classica Pose. "
        "Instale uma versao compativel com: "
        "'python3 -m pip uninstall -y mediapipe && "
        "python3 -m pip install mediapipe==0.10.9'"
    )


@dataclass(frozen=True)
class FingerState:
    is_complete: bool
    thumb_open: bool
    thumb_up: bool
    index_open: bool
    middle_open: bool
    ring_open: bool
    pinky_open: bool
    index_reach: float
    middle_reach: float
    ring_reach: float
    pinky_reach: float
    index_middle_spread: float
    middle_ring_spread: float
    ring_pinky_spread: float
    curled_fingers: int


@dataclass(frozen=True)
class VisionInputs:
    gesture: Optional[GestureName]
    marker_detected: bool
    rejection_reason: Optional[str] = None


class GestureClassifier:
    def classify(
        self,
        hand_landmarks,
        image_width: int,
        image_height: int,
        expected_gesture: Optional[GestureName] = None,
    ) -> Optional[GestureName]:
        finger_state = self._extract_finger_state(hand_landmarks, image_width, image_height)
        if not finger_state.is_complete:
            return None

        candidates = self._candidate_matches(finger_state)

        if expected_gesture is GestureName.HAND_OPEN:
            reason, extended_fingers = self._hand_open_rejection_reason(finger_state)
            self._log_hand_open_result(extended_fingers, reason)
            return GestureName.HAND_OPEN if reason is None else None

        if expected_gesture is GestureName.V_SIGN:
            return GestureName.V_SIGN if candidates[GestureName.V_SIGN] else None

        if expected_gesture is GestureName.THUMB_UP:
            return GestureName.THUMB_UP if candidates[GestureName.THUMB_UP] else None

        if expected_gesture is GestureName.POINT:
            reason, index_extended, other_fingers_extended = self._point_rejection_reason(
                finger_state
            )
            self._log_point_result(index_extended, other_fingers_extended, reason)
            return GestureName.POINT if reason is None else None

        if expected_gesture is GestureName.CLOSED_FIST:
            return (
                GestureName.CLOSED_FIST
                if self.closed_fist_rejection_reason(finger_state) is None
                else None
            )

        for gesture_name in (
            GestureName.HAND_OPEN,
            GestureName.V_SIGN,
            GestureName.THUMB_UP,
            GestureName.POINT,
            GestureName.CLOSED_FIST,
        ):
            if candidates[gesture_name]:
                return gesture_name

        return None

    def describe_hand(
        self,
        hand_landmarks,
        image_width: int,
        image_height: int,
    ) -> tuple[FingerState, dict[GestureName, bool]]:
        finger_state = self._extract_finger_state(hand_landmarks, image_width, image_height)
        return finger_state, self._candidate_matches(finger_state)

    def _candidate_matches(self, finger_state: FingerState) -> dict[GestureName, bool]:
        return {
            GestureName.HAND_OPEN: self._is_hand_open(finger_state),
            GestureName.V_SIGN: self._is_v_sign(finger_state),
            GestureName.THUMB_UP: self._is_thumb_up(finger_state),
            GestureName.POINT: self._is_point(finger_state),
            GestureName.CLOSED_FIST: self._is_closed_fist(finger_state),
        }

    def _extract_finger_state(self, hand_landmarks, image_width: int, image_height: int) -> FingerState:
        landmark = hand_landmarks.landmark

        def to_pixel(index: int) -> tuple[float, float]:
            point = landmark[index]
            return point.x * image_width, point.y * image_height

        def point(index: int):
            return landmark[index]

        def distance(first_index: int, second_index: int) -> float:
            first_x, first_y = to_pixel(first_index)
            second_x, second_y = to_pixel(second_index)
            return hypot(first_x - second_x, first_y - second_y)

        is_complete = all(
            0.0 <= point(index).x <= 1.0 and 0.0 <= point(index).y <= 1.0
            for index in range(21)
        )

        wrist_x, _ = to_pixel(0)
        thumb_tip_x, _ = to_pixel(4)
        thumb_ip_x, _ = to_pixel(3)
        thumb_tip_y = to_pixel(4)[1]
        thumb_ip_y = to_pixel(3)[1]
        thumb_mcp_y = to_pixel(2)[1]
        index_mcp_y = to_pixel(5)[1]

        index_tip_y = to_pixel(8)[1]
        index_pip_y = to_pixel(6)[1]
        index_mcp_x, index_mcp_y = to_pixel(5)
        middle_tip_y = to_pixel(12)[1]
        middle_pip_y = to_pixel(10)[1]
        middle_mcp_y = to_pixel(9)[1]
        ring_tip_y = to_pixel(16)[1]
        ring_pip_y = to_pixel(14)[1]
        ring_mcp_y = to_pixel(13)[1]
        pinky_tip_y = to_pixel(20)[1]
        pinky_pip_y = to_pixel(18)[1]
        pinky_mcp_y = to_pixel(17)[1]

        palm_size = max(distance(0, 9), distance(5, 17), 1.0)
        thumb_reach = distance(4, 5) / palm_size
        index_reach = distance(8, 5) / palm_size
        middle_reach = distance(12, 9) / palm_size
        ring_reach = distance(16, 13) / palm_size
        pinky_reach = distance(20, 17) / palm_size
        index_middle_spread = distance(8, 12) / palm_size
        middle_ring_spread = distance(12, 16) / palm_size
        ring_pinky_spread = distance(16, 20) / palm_size

        thumb_open = self._is_thumb_extended(thumb_tip_x, thumb_ip_x, wrist_x)
        thumb_up = all(
            (
                thumb_open,
                thumb_reach > 0.7,
                thumb_tip_y < thumb_ip_y < thumb_mcp_y,
                thumb_tip_y < index_mcp_y,
            )
        )
        return FingerState(
            is_complete=is_complete,
            thumb_open=thumb_open,
            thumb_up=thumb_up,
            index_open=index_tip_y < index_pip_y and index_reach > 0.9,
            middle_open=middle_tip_y < middle_pip_y and middle_reach > 0.9,
            ring_open=ring_tip_y < ring_pip_y and ring_reach > 0.85,
            pinky_open=pinky_tip_y < pinky_pip_y and pinky_reach > 0.8,
            index_reach=index_reach,
            middle_reach=middle_reach,
            ring_reach=ring_reach,
            pinky_reach=pinky_reach,
            index_middle_spread=index_middle_spread,
            middle_ring_spread=middle_ring_spread,
            ring_pinky_spread=ring_pinky_spread,
            curled_fingers=sum(
                (
                    index_reach < 0.75 and index_tip_y > index_mcp_y,
                    middle_reach < 0.75 and middle_tip_y > middle_mcp_y,
                    ring_reach < 0.75 and ring_tip_y > ring_mcp_y,
                    pinky_reach < 0.75 and pinky_tip_y > pinky_mcp_y,
                )
            ),
        )

    @staticmethod
    def _is_thumb_extended(thumb_tip_x: float, thumb_ip_x: float, wrist_x: float) -> bool:
        thumb_points_right = thumb_tip_x > wrist_x
        thumb_tip_is_outside = thumb_tip_x > thumb_ip_x
        thumb_points_left = thumb_tip_x < wrist_x
        thumb_tip_is_inside = thumb_tip_x < thumb_ip_x
        return (thumb_points_right and thumb_tip_is_outside) or (
            thumb_points_left and thumb_tip_is_inside
        )

    @staticmethod
    def _is_hand_open(finger_state: FingerState) -> bool:
        reason, _ = GestureClassifier._hand_open_rejection_reason(finger_state)
        return reason is None

    @staticmethod
    def _hand_open_rejection_reason(finger_state: FingerState) -> tuple[Optional[str], int]:
        extended_flags = (
            finger_state.index_reach >= 0.82,
            finger_state.middle_reach >= 0.85,
            finger_state.ring_reach >= 0.78,
            finger_state.pinky_reach >= 0.72,
        )
        strong_flags = (
            finger_state.index_reach >= 0.95,
            finger_state.middle_reach >= 0.95,
            finger_state.ring_reach >= 0.9,
            finger_state.pinky_reach >= 0.85,
        )
        spread_flags = (
            finger_state.index_middle_spread >= 0.16,
            finger_state.middle_ring_spread >= 0.13,
            finger_state.ring_pinky_spread >= 0.1,
        )
        extended_fingers = sum(extended_flags)
        strong_fingers = sum(strong_flags)
        spread_count = sum(spread_flags)

        if not finger_state.is_complete:
            return "low_quality_hand", extended_fingers

        if finger_state.thumb_up and extended_fingers < 3:
            return "thumb_up_like", extended_fingers

        if finger_state.curled_fingers >= 3 and extended_fingers <= 1:
            return "closed_fist_like", extended_fingers

        if extended_fingers < 3:
            return "fingers_not_extended", extended_fingers

        if strong_fingers == 0:
            return "weak_extension", extended_fingers

        if extended_fingers == 3 and strong_fingers == 1 and spread_count == 0:
            return "insufficient_spread", extended_fingers

        return None, extended_fingers

    @staticmethod
    def _log_hand_open_result(extended_fingers: int, reason: Optional[str]) -> None:
        if not (TEST_GESTURES_MODE or VISION_CALIBRATION_VIEW):
            return

        print(f"HAND_OPEN_DEBUG fingers_extended={extended_fingers}/4")
        if reason is None:
            print("HAND_OPEN_ACCEPTED")
        else:
            print(f"HAND_OPEN_DEBUG reason={reason}")

    @staticmethod
    def _is_point(finger_state: FingerState) -> bool:
        reason, _index_extended, _other_fingers_extended = (
            GestureClassifier._point_rejection_reason(finger_state)
        )
        return reason is None

    @staticmethod
    def _point_rejection_reason(finger_state: FingerState) -> tuple[Optional[str], bool, int]:
        index_extended = finger_state.index_reach >= 0.88
        index_strong = finger_state.index_reach >= 0.98
        other_extended_flags = (
            finger_state.middle_reach >= 0.82,
            finger_state.ring_reach >= 0.78,
            finger_state.pinky_reach >= 0.72,
        )
        other_weak_flags = (
            finger_state.middle_reach >= 0.7,
            finger_state.ring_reach >= 0.68,
            finger_state.pinky_reach >= 0.64,
        )
        other_fingers_extended = sum(other_extended_flags)
        other_fingers_not_folded = sum(other_weak_flags)

        if not finger_state.is_complete:
            return "low_quality_hand", index_extended, other_fingers_extended

        if not index_extended:
            return "index_not_extended", index_extended, other_fingers_extended

        if not index_strong and other_fingers_not_folded > 0:
            return "weak_index_extension", index_extended, other_fingers_extended

        if other_fingers_extended >= 2:
            return "open_hand_like", index_extended, other_fingers_extended

        if finger_state.middle_reach >= 0.82:
            return "v_sign_like", index_extended, other_fingers_extended

        if other_fingers_not_folded >= 2:
            return "other_fingers_not_folded", index_extended, other_fingers_extended

        return None, index_extended, other_fingers_extended

    @staticmethod
    def _log_point_result(
        index_extended: bool,
        other_fingers_extended: int,
        reason: Optional[str],
    ) -> None:
        if not (TEST_GESTURES_MODE or VISION_CALIBRATION_VIEW):
            return

        print(f"POINT_DEBUG index_extended={str(index_extended).lower()}")
        print(f"POINT_DEBUG other_fingers_extended={other_fingers_extended}")
        if reason is None:
            print("POINT_ACCEPTED")
        else:
            print(f"POINT_REJECTED reason={reason}")

    @staticmethod
    def _is_v_sign(finger_state: FingerState) -> bool:
        return all(
            (
                finger_state.is_complete,
                finger_state.index_open,
                finger_state.middle_open,
                not finger_state.thumb_up,
                not finger_state.ring_open,
                not finger_state.pinky_open,
            )
        )

    @staticmethod
    def _is_thumb_up(finger_state: FingerState) -> bool:
        return all(
            (
                finger_state.is_complete,
                finger_state.thumb_up,
                not finger_state.index_open,
                not finger_state.middle_open,
                not finger_state.ring_open,
                not finger_state.pinky_open,
            )
        )

    @staticmethod
    def _is_closed_fist(finger_state: FingerState) -> bool:
        return GestureClassifier.closed_fist_rejection_reason(finger_state) is None

    @staticmethod
    def closed_fist_rejection_reason(finger_state: FingerState) -> Optional[str]:
        if not finger_state.is_complete:
            return "fingers_not_confidently_folded"

        if finger_state.index_open:
            return "index_open"

        if (
            finger_state.middle_open
            or finger_state.ring_open
            or finger_state.pinky_open
            or finger_state.curled_fingers < 4
            or finger_state.thumb_up
        ):
            return "fingers_not_confidently_folded"

        return None


class VisionSystem:
    def __init__(self) -> None:
        self._vision_init_started_at = time.monotonic() if PERF_DIAGNOSTICS else 0.0
        if PERF_DIAGNOSTICS:
            print(f"PERF_MEDIAPIPE_INIT_START t={self._vision_init_started_at:.6f}")
        self._camera = self._open_camera()
        self._camera.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_FRAME_WIDTH)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_FRAME_HEIGHT)
        if CAMERA_TARGET_FPS > 0:
            self._camera.set(cv2.CAP_PROP_FPS, CAMERA_TARGET_FPS)
        if CAMERA_USE_MJPG:
            self._camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        hands_api = _resolve_hands_api()
        pose_api = _resolve_pose_api()
        self._hand_connections = hands_api.HAND_CONNECTIONS
        self._hands_single = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._hands_double = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=4,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._pose = pose_api.Pose(
            static_image_mode=False,
            model_complexity=0,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._classifier = GestureClassifier()
        self._aruco_detector = self._build_aruco_detector()
        self._debug_frame_counter = 0
        self._last_debug_message = ""
        self._perf_frame_counter = 0
        self._ready_frames = 0
        self._is_ready = False
        self._last_rejection_reason: Optional[str] = None
        self._first_hands_process_logged = False
        self._last_camera_perf_log_at = 0.0
        self._rejection_stats: dict[str, dict[str, int]] = {}
        self._calibration_stats: dict[str, dict[str, int]] = {}
        self._latest_preview_frame = None
        self._double_closed_fist_stable_frames = 0
        self._last_rejection_stats_log_at = time.monotonic()
        self._warm_up_camera()

    def _open_camera(self):
        if platform.system() == "Linux":
            v4l2_backend = getattr(cv2, "CAP_V4L2", None)
            if v4l2_backend is not None:
                camera = cv2.VideoCapture(CAMERA_INDEX, v4l2_backend)
                if camera.isOpened():
                    return camera
                camera.release()

        return cv2.VideoCapture(CAMERA_INDEX)

    def read_inputs(
        self,
        expected_gesture: Optional[GestureName] = None,
        detect_marker: bool = False,
        prioritize_prayer_hands: bool = False,
        allow_double_closed_fist: bool = False,
    ) -> VisionInputs:
        if not self._camera.isOpened():
            return VisionInputs(gesture=None, marker_detected=False)

        started_at = time.monotonic()
        capture_started_at = started_at
        success, frame = self._camera.read()
        capture_finished_at = time.monotonic()
        if not success:
            return VisionInputs(gesture=None, marker_detected=False)
        capture_elapsed = capture_finished_at - capture_started_at

        rgb_frame = None
        processing_frame = frame
        hands_result = None
        pose_result = None
        hands_elapsed = 0.0
        pose_elapsed = 0.0
        marker_elapsed = 0.0

        should_run_pose = prioritize_prayer_hands or expected_gesture is GestureName.PRAYER_HANDS
        should_run_hands = (
            expected_gesture in {
                GestureName.HAND_OPEN,
                GestureName.POINT,
                GestureName.V_SIGN,
                GestureName.THUMB_UP,
                GestureName.CLOSED_FIST,
            }
            or allow_double_closed_fist
        )

        if should_run_hands or should_run_pose:
            if VISION_PROCESSING_SCALE != 1.0:
                processing_frame = cv2.resize(
                    frame,
                    None,
                    fx=VISION_PROCESSING_SCALE,
                    fy=VISION_PROCESSING_SCALE,
                    interpolation=cv2.INTER_LINEAR,
                )
            rgb_frame = cv2.cvtColor(processing_frame, cv2.COLOR_BGR2RGB)
            rgb_frame.flags.writeable = False

        if should_run_hands:
            hands_runner = self._hands_double
            frame_age_approx = time.monotonic() - capture_finished_at
            self._log_camera_perf(capture_elapsed, frame_age_approx)
            hands_result, hands_elapsed = self._process_hands(hands_runner, rgb_frame)

        if should_run_pose:
            if not should_run_hands:
                frame_age_approx = time.monotonic() - capture_finished_at
                self._log_camera_perf(capture_elapsed, frame_age_approx)
            pose_started_at = time.monotonic()
            pose_result = self._pose.process(rgb_frame)
            pose_elapsed = time.monotonic() - pose_started_at

        gesture = self._detect_gesture(
            hands_result,
            pose_result,
            processing_frame.shape[1],
            processing_frame.shape[0],
            prioritize_prayer_hands,
            expected_gesture,
            allow_double_closed_fist,
        )
        rejection_reason = self._last_rejection_reason
        self._record_rejection_stats(
            expected_gesture,
            allow_double_closed_fist,
            gesture,
            rejection_reason,
        )
        if detect_marker:
            marker_started_at = time.monotonic()
            marker_detected = self._detect_marker(frame)
            marker_elapsed = time.monotonic() - marker_started_at
        else:
            marker_detected = False
        self._show_calibration_view(
            processing_frame,
            hands_result,
            pose_result,
            expected_gesture,
            allow_double_closed_fist,
            gesture,
            rejection_reason,
        )
        self._debug_detection(
            hands_result,
            processing_frame.shape[1],
            processing_frame.shape[0],
            gesture,
            prioritize_prayer_hands,
            time.monotonic() - started_at,
            capture_elapsed,
            hands_elapsed,
            pose_elapsed,
            marker_elapsed,
        )
        return VisionInputs(
            gesture=gesture,
            marker_detected=marker_detected,
            rejection_reason=rejection_reason,
        )

    def consume_preview_frame(self):
        if not VISION_PREVIEW_OVERLAY:
            return None

        frame = self._latest_preview_frame
        self._latest_preview_frame = None
        return frame

    def poll_ready(self) -> bool:
        if self._is_ready:
            return True

        if not self._camera.isOpened():
            return False

        capture_started_at = time.monotonic()
        success, frame = self._camera.read()
        capture_finished_at = time.monotonic()
        if not success:
            return False

        processing_frame = frame
        if VISION_PROCESSING_SCALE != 1.0:
            processing_frame = cv2.resize(
                frame,
                None,
                fx=VISION_PROCESSING_SCALE,
                fy=VISION_PROCESSING_SCALE,
                interpolation=cv2.INTER_LINEAR,
            )

        rgb_frame = cv2.cvtColor(processing_frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False
        frame_age_approx = time.monotonic() - capture_finished_at
        self._log_camera_perf(capture_finished_at - capture_started_at, frame_age_approx)
        self._process_hands(self._hands_single, rgb_frame)
        self._ready_frames += 1
        if self._ready_frames >= VISION_READY_FRAMES:
            self._is_ready = True
            print("[Vision] ready")

        return self._is_ready

    def _record_rejection_stats(
        self,
        expected_gesture: Optional[GestureName],
        allow_double_closed_fist: bool,
        gesture: Optional[GestureName],
        rejection_reason: Optional[str],
    ) -> None:
        if not VISION_REJECTION_STATS:
            return

        expected_name = self._stats_expected_name(expected_gesture, allow_double_closed_fist)
        stats = self._rejection_stats.setdefault(expected_name, {})

        if gesture is not None:
            stats["accepted"] = stats.get("accepted", 0) + 1
            self._record_calibration_stat(expected_name, "accepted")
            self._log_rejection_stats(expected_name, force=True, accepted_gesture=gesture)
            self._rejection_stats[expected_name] = {}
            return

        reason = self._normalize_rejection_reason(rejection_reason)
        stats[reason] = stats.get(reason, 0) + 1
        self._record_calibration_stat(expected_name, reason)
        self._log_rejection_stats(expected_name)

    def _record_calibration_stat(self, expected_name: str, reason: str) -> None:
        if not (VISION_CALIBRATION_VIEW or VISION_PREVIEW_OVERLAY):
            return

        stats = self._calibration_stats.setdefault(expected_name, {})
        stats[reason] = stats.get(reason, 0) + 1

    @staticmethod
    def _stats_expected_name(
        expected_gesture: Optional[GestureName],
        allow_double_closed_fist: bool,
    ) -> str:
        if expected_gesture is not None:
            return expected_gesture.value
        if allow_double_closed_fist:
            return GestureName.DOUBLE_CLOSED_FIST.value
        return "NONE"

    @staticmethod
    def _normalize_rejection_reason(reason: Optional[str]) -> str:
        if reason is None:
            return "no_hand"

        aliases = {
            "wrong_expected_gesture": "not_expected_gesture",
            "no_candidate_matched_expected": "not_expected_gesture",
            "only_one_hand": "one_hand_only",
            "one_hand_not_closed": "not_closed_fist",
            "closed_fist_like": "not_expected_gesture",
            "thumb_up_like": "not_expected_gesture",
            "fingers_not_extended": "not_expected_gesture",
            "index_open": "not_closed_fist",
            "fingers_not_confidently_folded": "not_closed_fist",
        }
        return aliases.get(reason, reason)

    def _log_rejection_stats(
        self,
        expected_name: str,
        force: bool = False,
        accepted_gesture: Optional[GestureName] = None,
    ) -> None:
        now = time.monotonic()
        if not force and now - self._last_rejection_stats_log_at < 5.0:
            return

        stats = self._rejection_stats.get(expected_name, {})
        if not stats:
            return

        stats_text = " ".join(
            f"{reason}={count}"
            for reason, count in sorted(stats.items())
        )
        if force and accepted_gesture is not None:
            rejection_stats_text = " ".join(
                f"{reason}={count}"
                for reason, count in sorted(stats.items())
                if reason != "accepted"
            )
            print(
                "VISION_ACCEPTED "
                f"expected={expected_name} "
                f"raw={accepted_gesture.value} "
                f"accepted={stats.get('accepted', 0)} "
                f"after_rejections={{{rejection_stats_text}}}"
            )
        else:
            print(f"VISION_REJECTION_STATS expected={expected_name} {stats_text}")
            self._last_rejection_stats_log_at = now

    def _process_hands(self, hands_runner, rgb_frame):
        hands_started_at = time.monotonic()
        is_first_process = PERF_DIAGNOSTICS and not self._first_hands_process_logged
        if is_first_process:
            print(f"PERF_MEDIAPIPE_FIRST_PROCESS_START t={hands_started_at:.6f}")
        result = hands_runner.process(rgb_frame)
        hands_finished_at = time.monotonic()
        hands_elapsed = hands_finished_at - hands_started_at
        if is_first_process:
            self._first_hands_process_logged = True
            print(f"PERF_MEDIAPIPE_FIRST_PROCESS_END t={hands_finished_at:.6f}")
            print(f"PERF_MEDIAPIPE_COLD_START_MS={hands_elapsed * 1000:.1f}")
        return result, hands_elapsed

    def _log_camera_perf(self, read_elapsed: float, frame_age_approx: float) -> None:
        if not PERF_DIAGNOSTICS:
            return

        now = time.monotonic()
        if self._last_camera_perf_log_at and now - self._last_camera_perf_log_at < 2.0:
            return

        self._last_camera_perf_log_at = now
        print(f"PERF_CAMERA_READ_MS={read_elapsed * 1000:.1f}")
        print(f"PERF_FRAME_AGE_APPROX_MS={frame_age_approx * 1000:.1f}")

    def _show_calibration_view(
        self,
        frame,
        hands_result,
        pose_result,
        expected_gesture: Optional[GestureName],
        allow_double_closed_fist: bool,
        raw_gesture: Optional[GestureName],
        rejection_reason: Optional[str],
    ) -> None:
        if not VISION_CALIBRATION_VIEW:
            return

        overlay = frame.copy()
        height, width = overlay.shape[:2]
        self._draw_calibration_roi(overlay, width, height)

        hand_landmarks_list = (
            []
            if hands_result is None or not hands_result.multi_hand_landmarks
            else hands_result.multi_hand_landmarks
        )
        for index, hand_landmarks in enumerate(hand_landmarks_list):
            self._draw_calibration_hand(overlay, hand_landmarks, width, height, index)
        self._draw_calibration_pose(overlay, pose_result, width, height)

        expected_name = self._stats_expected_name(expected_gesture, allow_double_closed_fist)
        reason = self._normalize_rejection_reason(rejection_reason)
        status = "ACCEPTED" if raw_gesture is not None else "REJECTED"
        raw_name = raw_gesture.value if raw_gesture is not None else "NONE"
        stats_text = self._format_calibration_stats(expected_name)
        lines = [
            f"expected: {expected_name}",
            f"raw: {raw_name}",
            f"status: {status}",
            f"reason: {reason}",
            f"hands: {len(hand_landmarks_list)}",
            f"stats: {stats_text}",
        ]
        self._draw_calibration_text(overlay, lines)
        if VISION_PREVIEW_OVERLAY:
            self._latest_preview_frame = overlay
            return

        cv2.imshow("VanCoco Vision Calibration", overlay)
        cv2.waitKey(1)

    @staticmethod
    def _draw_calibration_roi(frame, width: int, height: int) -> None:
        if not VISION_ROI_ENABLED:
            return

        x_min = int(VISION_ROI_X_MIN_RATIO * width)
        x_max = int(VISION_ROI_X_MAX_RATIO * width)
        y_min = int(VISION_ROI_Y_MIN_RATIO * height)
        y_max = int(VISION_ROI_Y_MAX_RATIO * height)
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), (0, 255, 255), 2)
        cv2.putText(
            frame,
            "ROI",
            (x_min + 8, max(20, y_min + 24)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def _draw_calibration_hand(self, frame, hand_landmarks, width: int, height: int, index: int) -> None:
        landmarks = hand_landmarks.landmark
        points = [
            (int(point.x * width), int(point.y * height))
            for point in landmarks
        ]
        for start_index, end_index in self._hand_connections:
            cv2.line(frame, points[start_index], points[end_index], (0, 180, 255), 2)

        for point in points:
            cv2.circle(frame, point, 3, (0, 255, 0), -1)

        center_x = int(sum(point.x for point in landmarks) / len(landmarks) * width)
        center_y = int(sum(point.y for point in landmarks) / len(landmarks) * height)
        palm_size = max(
            hypot(landmarks[0].x - landmarks[9].x, landmarks[0].y - landmarks[9].y),
            hypot(landmarks[5].x - landmarks[17].x, landmarks[5].y - landmarks[17].y),
        )
        quality_reason = self._hand_quality_rejection_reason(hand_landmarks)
        label = f"hand{index + 1} palm={palm_size:.3f} quality={quality_reason or 'ok'}"
        cv2.circle(frame, (center_x, center_y), 6, (255, 0, 255), -1)
        cv2.putText(
            frame,
            label,
            (center_x + 8, max(20, center_y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    @staticmethod
    def _draw_calibration_pose(frame, pose_result, width: int, height: int) -> None:
        if pose_result is None or pose_result.pose_landmarks is None:
            return

        landmarks = pose_result.pose_landmarks.landmark
        pose_points = {
            "nose": landmarks[0],
            "left_shoulder": landmarks[11],
            "right_shoulder": landmarks[12],
            "left_wrist": landmarks[15],
            "right_wrist": landmarks[16],
        }
        pixel_points = {
            name: (int(point.x * width), int(point.y * height))
            for name, point in pose_points.items()
        }
        cv2.line(frame, pixel_points["left_shoulder"], pixel_points["right_shoulder"], (255, 180, 0), 2)
        cv2.line(frame, pixel_points["left_shoulder"], pixel_points["left_wrist"], (255, 180, 0), 2)
        cv2.line(frame, pixel_points["right_shoulder"], pixel_points["right_wrist"], (255, 180, 0), 2)
        for name, point in pixel_points.items():
            cv2.circle(frame, point, 5, (255, 180, 0), -1)
            cv2.putText(
                frame,
                name,
                (point[0] + 6, max(20, point[1] - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        wrist_center = (
            int((pixel_points["left_wrist"][0] + pixel_points["right_wrist"][0]) / 2),
            int((pixel_points["left_wrist"][1] + pixel_points["right_wrist"][1]) / 2),
        )
        cv2.circle(frame, wrist_center, 7, (0, 0, 255), -1)

    @staticmethod
    def _draw_calibration_text(frame, lines: list[str]) -> None:
        x = 12
        y = 24
        line_height = 24
        box_height = line_height * len(lines) + 12
        cv2.rectangle(frame, (0, 0), (frame.shape[1], box_height), (0, 0, 0), -1)
        for line in lines:
            cv2.putText(
                frame,
                line,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.58,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            y += line_height

    def _format_calibration_stats(self, expected_name: str) -> str:
        stats = self._calibration_stats.get(expected_name, {})
        if not stats:
            return "none"

        return " ".join(
            f"{reason}={count}"
            for reason, count in sorted(stats.items())
        )

    def _detect_gesture(
        self,
        hands_result,
        pose_result,
        image_width: int,
        image_height: int,
        prioritize_prayer_hands: bool,
        expected_gesture: Optional[GestureName],
        allow_double_closed_fist: bool,
    ) -> Optional[GestureName]:
        self._last_rejection_reason = None
        if prioritize_prayer_hands and self._detect_prayer_hands(pose_result):
            self._reset_double_closed_fist_stability()
            if self._pose_hands_center_in_roi(pose_result):
                return GestureName.PRAYER_HANDS
            self._last_rejection_reason = "outside_roi"

        if hands_result is not None and hands_result.multi_hand_landmarks:
            sorted_hands = self._hands_by_size(hands_result.multi_hand_landmarks)
            if allow_double_closed_fist and expected_gesture is None:
                if len(sorted_hands) < 2:
                    self._reset_double_closed_fist_stability()
                    self._log_double_closed_fist_debug(len(sorted_hands), 0, False)
                    self._last_rejection_reason = "only_one_hand"
                    return None

                valid_hands = [
                    hand_landmarks
                    for hand_landmarks in sorted_hands
                    if self._double_fist_hand_rejection_reason(hand_landmarks) is None
                ]
                if len(valid_hands) < 2:
                    self._reset_double_closed_fist_stability()
                    self._log_double_closed_fist_debug(len(sorted_hands), len(valid_hands), False)
                    self._last_rejection_reason = "hands_outside_roi"
                    return None

                first_hand = valid_hands[0]
                second_hand = valid_hands[1]
                if not self._double_fist_hands_are_separate(first_hand, second_hand):
                    self._reset_double_closed_fist_stability()
                    self._log_double_closed_fist_debug(len(sorted_hands), len(valid_hands), False)
                    self._last_rejection_reason = "ghost_hand"
                    return None

                first_state, first_candidates = self._classifier.describe_hand(
                    first_hand,
                    image_width,
                    image_height,
                )
                second_state, second_candidates = self._classifier.describe_hand(
                    second_hand,
                    image_width,
                    image_height,
                )
                if (
                    first_candidates[GestureName.CLOSED_FIST]
                    and second_candidates[GestureName.CLOSED_FIST]
                    and first_state.curled_fingers >= 4
                    and second_state.curled_fingers >= 4
                ):
                    self._double_closed_fist_stable_frames += 1
                    simultaneous = (
                        self._double_closed_fist_stable_frames
                        >= DOUBLE_CLOSED_FIST_STABLE_FRAMES
                    )
                    self._log_double_closed_fist_debug(len(sorted_hands), 2, simultaneous)
                    if simultaneous:
                        self._log_double_closed_fist_accepted()
                        return GestureName.DOUBLE_CLOSED_FIST

                    self._last_rejection_reason = "double_fist_stabilizing"
                    return None

                self._reset_double_closed_fist_stability()
                fists_detected = int(first_candidates[GestureName.CLOSED_FIST]) + int(
                    second_candidates[GestureName.CLOSED_FIST]
                )
                self._log_double_closed_fist_debug(len(sorted_hands), fists_detected, False)
                self._last_rejection_reason = "one_hand_not_closed"
                return None

            self._reset_double_closed_fist_stability()
            if expected_gesture in {
                GestureName.HAND_OPEN,
                GestureName.POINT,
                GestureName.V_SIGN,
                GestureName.THUMB_UP,
            }:
                return self._detect_expected_simple_gesture(
                    sorted_hands,
                    image_width,
                    image_height,
                    expected_gesture,
                )

            for hand_landmarks in sorted_hands[:1]:
                quality_reason = self._hand_quality_rejection_reason(hand_landmarks)
                if quality_reason is not None:
                    self._last_rejection_reason = quality_reason
                    return None

                if expected_gesture is GestureName.CLOSED_FIST:
                    finger_state, _ = self._classifier.describe_hand(
                        hand_landmarks,
                        image_width,
                        image_height,
                    )
                    closed_fist_reason = self._classifier.closed_fist_rejection_reason(
                        finger_state
                    )
                    if closed_fist_reason is not None:
                        self._last_rejection_reason = closed_fist_reason
                        return None

                    return GestureName.CLOSED_FIST

                gesture = self._classifier.classify(
                    hand_landmarks,
                    image_width,
                    image_height,
                    expected_gesture,
                )
                if gesture in {
                    GestureName.HAND_OPEN,
                    GestureName.V_SIGN,
                    GestureName.THUMB_UP,
                    GestureName.POINT,
                    GestureName.CLOSED_FIST,
                }:
                    return gesture

                self._last_rejection_reason = "wrong_expected_gesture"

        if self._detect_prayer_hands(pose_result):
            self._reset_double_closed_fist_stability()
            if self._pose_hands_center_in_roi(pose_result):
                return GestureName.PRAYER_HANDS
            self._last_rejection_reason = "outside_roi"

        self._reset_double_closed_fist_stability()
        return None

    def _detect_expected_simple_gesture(
        self,
        sorted_hands: list,
        image_width: int,
        image_height: int,
        expected_gesture: GestureName,
    ) -> Optional[GestureName]:
        for hand_landmarks in sorted_hands:
            hand_size = self._hand_size(hand_landmarks)
            quality_reason = self._hand_quality_rejection_reason(hand_landmarks)
            if quality_reason is not None:
                self._log_hand_selection_candidate(hand_size, None)
                continue

            gesture = self._classifier.classify(
                hand_landmarks,
                image_width,
                image_height,
                expected_gesture,
            )
            self._log_hand_selection_candidate(hand_size, gesture)
            if gesture is expected_gesture:
                self._log_hand_selection_accepted(gesture)
                return gesture

        self._last_rejection_reason = "no_candidate_matched_expected"
        if TEST_GESTURES_MODE:
            print("HAND_SELECTION_REJECTED reason=no_candidate_matched_expected")
        return None

    @staticmethod
    def _log_hand_selection_candidate(
        hand_size: float,
        gesture: Optional[GestureName],
    ) -> None:
        if not TEST_GESTURES_MODE:
            return

        result = gesture.value if gesture is not None else "NONE"
        print(f"HAND_SELECTION_CANDIDATE size={hand_size:.4f} result={result}")

    @staticmethod
    def _log_hand_selection_accepted(gesture: GestureName) -> None:
        if not TEST_GESTURES_MODE:
            return

        print(f"HAND_SELECTION_ACCEPTED gesture={gesture.value}")

    @staticmethod
    def _hands_by_size(hand_landmarks_list) -> list:
        return sorted(
            hand_landmarks_list,
            key=VisionSystem._hand_size,
            reverse=True,
        )

    @staticmethod
    def _hand_size(hand_landmarks) -> float:
        landmarks = hand_landmarks.landmark
        x_values = [point.x for point in landmarks]
        y_values = [point.y for point in landmarks]
        return (max(x_values) - min(x_values)) * (max(y_values) - min(y_values))

    def _double_fist_hand_rejection_reason(self, hand_landmarks) -> Optional[str]:
        quality_reason = self._hand_quality_rejection_reason(hand_landmarks)
        if quality_reason is not None:
            return "hands_outside_roi" if quality_reason == "outside_roi" else quality_reason

        if not VISION_ROI_ENABLED:
            return None

        landmarks = hand_landmarks.landmark
        center_y = sum(point.y for point in landmarks) / len(landmarks)
        if center_y > min(VISION_ROI_Y_MAX_RATIO, DOUBLE_CLOSED_FIST_ROI_Y_MAX_RATIO):
            return "hands_outside_roi"

        return None

    @staticmethod
    def _hand_center(hand_landmarks) -> tuple[float, float]:
        landmarks = hand_landmarks.landmark
        return (
            sum(point.x for point in landmarks) / len(landmarks),
            sum(point.y for point in landmarks) / len(landmarks),
        )

    def _double_fist_hands_are_separate(self, first_hand, second_hand) -> bool:
        first_x, first_y = self._hand_center(first_hand)
        second_x, second_y = self._hand_center(second_hand)
        return (
            hypot(first_x - second_x, first_y - second_y)
            >= DOUBLE_CLOSED_FIST_MIN_CENTER_DISTANCE
        )

    def _reset_double_closed_fist_stability(self) -> None:
        self._double_closed_fist_stable_frames = 0

    @staticmethod
    def _log_double_closed_fist_debug(
        hands_detected: int,
        fists_detected: int,
        simultaneous: bool,
    ) -> None:
        if not (TEST_GESTURES_MODE or VISION_CALIBRATION_VIEW):
            return

        print(f"DOUBLE_DEBUG hands_detected={hands_detected}")
        print(f"DOUBLE_DEBUG fists_detected={fists_detected}")
        print(f"DOUBLE_DEBUG simultaneous={str(simultaneous).lower()}")

    @staticmethod
    def _log_double_closed_fist_accepted() -> None:
        if not (TEST_GESTURES_MODE or VISION_CALIBRATION_VIEW):
            return

        print("DOUBLE_ACCEPTED")

    @staticmethod
    def _hand_quality_rejection_reason(hand_landmarks) -> Optional[str]:
        if not VISION_HAND_QUALITY_ENABLED:
            return None

        landmarks = hand_landmarks.landmark
        key_indices = (0, 4, 8, 12, 16, 20)
        if any(
            not (0.0 <= landmarks[index].x <= 1.0 and 0.0 <= landmarks[index].y <= 1.0)
            for index in key_indices
        ):
            return "insufficient_landmarks"

        x_values = [point.x for point in landmarks]
        y_values = [point.y for point in landmarks]
        if (
            min(x_values) < VISION_HAND_BORDER_MARGIN_RATIO
            or max(x_values) > 1.0 - VISION_HAND_BORDER_MARGIN_RATIO
            or min(y_values) < VISION_HAND_BORDER_MARGIN_RATIO
            or max(y_values) > 1.0 - VISION_HAND_BORDER_MARGIN_RATIO
        ):
            return "low_quality_hand"

        palm_size = max(
            hypot(landmarks[0].x - landmarks[9].x, landmarks[0].y - landmarks[9].y),
            hypot(landmarks[5].x - landmarks[17].x, landmarks[5].y - landmarks[17].y),
        )
        if palm_size < VISION_HAND_MIN_PALM_RATIO:
            return "palm_too_small"

        if not VISION_ROI_ENABLED:
            return None

        center_x = sum(x_values) / len(x_values)
        center_y = sum(y_values) / len(y_values)
        if not (
            VISION_ROI_X_MIN_RATIO <= center_x <= VISION_ROI_X_MAX_RATIO
            and VISION_ROI_Y_MIN_RATIO <= center_y <= VISION_ROI_Y_MAX_RATIO
        ):
            return "outside_roi"

        landmarks_inside_roi = sum(
            1
            for point in landmarks
            if (
                VISION_ROI_X_MIN_RATIO <= point.x <= VISION_ROI_X_MAX_RATIO
                and VISION_ROI_Y_MIN_RATIO <= point.y <= VISION_ROI_Y_MAX_RATIO
            )
        )
        if landmarks_inside_roi / len(landmarks) < VISION_HAND_MIN_LANDMARKS_IN_ROI_RATIO:
            return "outside_roi"

        return None

    def _detect_prayer_hands(self, pose_result) -> bool:
        if pose_result is None or pose_result.pose_landmarks is None:
            return False

        landmarks = pose_result.pose_landmarks.landmark
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        left_shoulder = landmarks[11]
        right_shoulder = landmarks[12]
        nose = landmarks[0]

        if min(
            left_wrist.visibility,
            right_wrist.visibility,
            left_shoulder.visibility,
            right_shoulder.visibility,
        ) < POSE_VISIBILITY_THRESHOLD:
            return False

        shoulder_width = hypot(
            left_shoulder.x - right_shoulder.x,
            left_shoulder.y - right_shoulder.y,
        )
        if shoulder_width <= 0.0:
            return False

        wrist_distance = hypot(
            left_wrist.x - right_wrist.x,
            left_wrist.y - right_wrist.y,
        )
        if wrist_distance > shoulder_width * PRAYER_WRIST_DISTANCE_RATIO:
            return False

        wrist_mid_x = (left_wrist.x + right_wrist.x) / 2.0
        wrist_mid_y = (left_wrist.y + right_wrist.y) / 2.0
        shoulder_mid_x = (left_shoulder.x + right_shoulder.x) / 2.0
        shoulder_mid_y = (left_shoulder.y + right_shoulder.y) / 2.0

        if abs(wrist_mid_x - shoulder_mid_x) > shoulder_width * PRAYER_CENTER_OFFSET_RATIO:
            return False

        chest_offset = wrist_mid_y - shoulder_mid_y
        if not (
            shoulder_width * PRAYER_CHEST_HEIGHT_MIN_RATIO
            <= chest_offset
            <= shoulder_width * PRAYER_CHEST_HEIGHT_MAX_RATIO
        ):
            return False

        if nose.visibility >= POSE_VISIBILITY_THRESHOLD and wrist_mid_y < nose.y:
            return False

        return True

    @staticmethod
    def _pose_hands_center_in_roi(pose_result) -> bool:
        if not VISION_ROI_ENABLED:
            return True

        if pose_result is None or pose_result.pose_landmarks is None:
            return False

        landmarks = pose_result.pose_landmarks.landmark
        left_wrist = landmarks[15]
        right_wrist = landmarks[16]
        center_x = (left_wrist.x + right_wrist.x) / 2.0
        center_y = (left_wrist.y + right_wrist.y) / 2.0
        return (
            VISION_ROI_X_MIN_RATIO <= center_x <= VISION_ROI_X_MAX_RATIO
            and VISION_ROI_Y_MIN_RATIO <= center_y <= VISION_ROI_Y_MAX_RATIO
        )

    def _debug_detection(
        self,
        hands_result,
        image_width: int,
        image_height: int,
        gesture: Optional[GestureName],
        prioritize_prayer_hands: bool,
        elapsed_seconds: float,
        capture_elapsed: float,
        hands_elapsed: float,
        pose_elapsed: float,
        marker_elapsed: float,
    ) -> None:
        if not VISION_PERF_LOG:
            return

        self._debug_frame_counter += 1
        if self._debug_frame_counter % VISION_PERF_LOG_EVERY != 0:
            return

        hand_landmarks_list = [] if hands_result is None or not hands_result.multi_hand_landmarks else hands_result.multi_hand_landmarks
        hand_count = len(hand_landmarks_list)
        if hand_landmarks_list:
            finger_state, candidates = self._classifier.describe_hand(
                hand_landmarks_list[0],
                image_width,
                image_height,
            )
            message = (
                "[Vision] "
                f"hands={hand_count} "
                f"prayer_priority={'ON' if prioritize_prayer_hands else 'OFF'} "
                f"dt_ms={elapsed_seconds * 1000:.1f} "
                f"capture_ms={capture_elapsed * 1000:.1f} "
                f"hands_ms={hands_elapsed * 1000:.1f} "
                f"pose_ms={pose_elapsed * 1000:.1f} "
                f"marker_ms={marker_elapsed * 1000:.1f} "
                f"gesture={gesture.value if gesture else 'NONE'} "
                f"fingers=("
                f"T:{int(finger_state.thumb_open)} "
                f"I:{int(finger_state.index_open)} "
                f"M:{int(finger_state.middle_open)} "
                f"R:{int(finger_state.ring_open)} "
                f"P:{int(finger_state.pinky_open)})"
            )
            if VISION_GESTURE_DEBUG:
                candidate_text = ",".join(
                    f"{gesture_name.value}:{int(is_match)}"
                    for gesture_name, is_match in candidates.items()
                )
                message += f" candidates=({candidate_text})"
        else:
            message = (
                "[Vision] "
                f"hands={hand_count} "
                f"prayer_priority={'ON' if prioritize_prayer_hands else 'OFF'} "
                f"dt_ms={elapsed_seconds * 1000:.1f} "
                f"capture_ms={capture_elapsed * 1000:.1f} "
                f"hands_ms={hands_elapsed * 1000:.1f} "
                f"pose_ms={pose_elapsed * 1000:.1f} "
                f"marker_ms={marker_elapsed * 1000:.1f} "
                f"gesture={gesture.value if gesture else 'NONE'}"
            )

        if message == self._last_debug_message:
            return

        self._last_debug_message = message
        print(message)

    def _detect_marker(self, frame) -> bool:
        if self._aruco_detector is None:
            return False

        corners, ids, _rejected = self._aruco_detector.detectMarkers(frame)
        if ids is None:
            return False

        return any(int(marker_id[0]) == ARUCO_MARKER_ID for marker_id in ids)

    def release(self) -> None:
        self._camera.release()
        self._hands_single.close()
        self._hands_double.close()
        self._pose.close()
        if VISION_CALIBRATION_VIEW and not VISION_PREVIEW_OVERLAY:
            try:
                cv2.destroyWindow("VanCoco Vision Calibration")
            except cv2.error:
                pass

    def _warm_up_camera(self) -> None:
        for _ in range(CAMERA_WARMUP_FRAMES):
            self._camera.read()

    @staticmethod
    def _build_aruco_detector():
        aruco = getattr(cv2, "aruco", None)
        if aruco is None:
            return None

        dictionary = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()
        return aruco.ArucoDetector(dictionary, parameters)
