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
    GestureName,
    POSE_VISIBILITY_THRESHOLD,
    PRAYER_CENTER_OFFSET_RATIO,
    PRAYER_CHEST_HEIGHT_MAX_RATIO,
    PRAYER_CHEST_HEIGHT_MIN_RATIO,
    PRAYER_WRIST_DISTANCE_RATIO,
    TEST_GESTURES_MODE,
    TRACKING_CONFIDENCE,
    VISION_GESTURE_DEBUG,
    VISION_HAND_BORDER_MARGIN_RATIO,
    VISION_HAND_QUALITY_ENABLED,
    VISION_HAND_MIN_LANDMARKS_IN_ROI_RATIO,
    VISION_HAND_MIN_PALM_RATIO,
    VISION_READY_FRAMES,
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
            return GestureName.POINT if candidates[GestureName.POINT] else None

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
        extended_fingers = sum(
            (
                finger_state.index_reach >= 0.95,
                finger_state.middle_reach >= 0.95,
                finger_state.ring_reach >= 0.9,
                finger_state.pinky_reach >= 0.85,
            )
        )

        if not finger_state.is_complete:
            return "low_quality_hand", extended_fingers

        if finger_state.thumb_up:
            return "thumb_up_like", extended_fingers

        if finger_state.curled_fingers >= 3:
            return "closed_fist_like", extended_fingers

        if extended_fingers < 3:
            return "fingers_not_extended", extended_fingers

        return None, extended_fingers

    @staticmethod
    def _log_hand_open_result(extended_fingers: int, reason: Optional[str]) -> None:
        if not TEST_GESTURES_MODE:
            return

        print(f"HAND_OPEN_REACH fingers={extended_fingers}/4")
        if reason is None:
            print("HAND_OPEN_ACCEPTED")
        else:
            print(f"HAND_OPEN_REJECTED reason={reason}")

    @staticmethod
    def _is_point(finger_state: FingerState) -> bool:
        return all(
            (
                finger_state.is_complete,
                finger_state.index_open,
                not finger_state.middle_open,
                not finger_state.ring_open,
                not finger_state.pinky_open,
                not finger_state.thumb_up,
                finger_state.curled_fingers >= 3,
            )
        )

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
        self._hands_single = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._hands_double = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=2,
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
        if not success:
            return VisionInputs(gesture=None, marker_detected=False)
        capture_elapsed = time.monotonic() - capture_started_at

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
            hands_started_at = time.monotonic()
            hands_result = hands_runner.process(rgb_frame)
            hands_elapsed = time.monotonic() - hands_started_at

        if should_run_pose:
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
        if detect_marker:
            marker_started_at = time.monotonic()
            marker_detected = self._detect_marker(frame)
            marker_elapsed = time.monotonic() - marker_started_at
        else:
            marker_detected = False
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

    def detect_gesture(
        self,
        expected_gesture: Optional[GestureName] = None,
        prioritize_prayer_hands: bool = False,
    ) -> Optional[GestureName]:
        return self.read_inputs(
            expected_gesture=expected_gesture,
            prioritize_prayer_hands=prioritize_prayer_hands,
        ).gesture

    def poll_ready(self) -> bool:
        if self._is_ready:
            return True

        if not self._camera.isOpened():
            return False

        success, frame = self._camera.read()
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
        self._hands_single.process(rgb_frame)
        self._ready_frames += 1
        if self._ready_frames >= VISION_READY_FRAMES:
            self._is_ready = True
            print("[Vision] ready")

        return self._is_ready

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
            if self._pose_hands_center_in_roi(pose_result):
                return GestureName.PRAYER_HANDS
            self._last_rejection_reason = "outside_roi"

        if hands_result is not None and hands_result.multi_hand_landmarks:
            sorted_hands = self._hands_by_size(hands_result.multi_hand_landmarks)
            if allow_double_closed_fist and expected_gesture is None:
                if len(sorted_hands) < 2:
                    self._last_rejection_reason = "only_one_hand"
                    return None

                valid_hands = [
                    hand_landmarks
                    for hand_landmarks in sorted_hands
                    if self._double_fist_hand_rejection_reason(hand_landmarks) is None
                ]
                if len(valid_hands) < 2:
                    self._last_rejection_reason = "hands_outside_roi"
                    return None

                first_hand = valid_hands[0]
                second_hand = valid_hands[1]
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
                    return GestureName.DOUBLE_CLOSED_FIST

                self._last_rejection_reason = "one_hand_not_closed"
                return None

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
            if self._pose_hands_center_in_roi(pose_result):
                return GestureName.PRAYER_HANDS
            self._last_rejection_reason = "outside_roi"

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
    def _hand_quality_rejection_reason(hand_landmarks) -> Optional[str]:
        if not VISION_HAND_QUALITY_ENABLED:
            return None

        landmarks = hand_landmarks.landmark
        key_indices = (0, 4, 8, 12, 16, 20)
        if any(
            not (0.0 <= landmarks[index].x <= 1.0 and 0.0 <= landmarks[index].y <= 1.0)
            for index in key_indices
        ):
            return "low_quality_hand"

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
            return "low_quality_hand"

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
