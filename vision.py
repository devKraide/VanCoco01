from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from config import (
    ARUCO_MARKER_ID,
    CAMERA_INDEX,
    CAMERA_WARMUP_FRAMES,
    DETECTION_CONFIDENCE,
    GestureName,
    POSE_VISIBILITY_THRESHOLD,
    PRAYER_CENTER_OFFSET_RATIO,
    PRAYER_CHEST_HEIGHT_MAX_RATIO,
    PRAYER_CHEST_HEIGHT_MIN_RATIO,
    PRAYER_WRIST_DISTANCE_RATIO,
    TRACKING_CONFIDENCE,
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


@dataclass(frozen=True)
class VisionInputs:
    gesture: Optional[GestureName]
    marker_detected: bool


class GestureClassifier:
    def classify(self, hand_landmarks, image_width: int, image_height: int) -> Optional[GestureName]:
        finger_state = self._extract_finger_state(hand_landmarks, image_width, image_height)
        if not finger_state.is_complete:
            return None

        if self._is_hand_open(finger_state):
            return GestureName.HAND_OPEN

        if self._is_v_sign(finger_state):
            return GestureName.V_SIGN

        if self._is_thumb_up(finger_state):
            return GestureName.THUMB_UP

        if self._is_point(finger_state):
            return GestureName.POINT

        if self._is_closed_fist(finger_state):
            return GestureName.CLOSED_FIST

        return None

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
        return all(
            (
                finger_state.is_complete,
                finger_state.index_open,
                finger_state.middle_open,
                finger_state.ring_open,
                finger_state.thumb_open or finger_state.pinky_open,
            )
        )

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
            )
        )

    @staticmethod
    def _is_v_sign(finger_state: FingerState) -> bool:
        return all(
            (
                finger_state.is_complete,
                finger_state.index_open,
                finger_state.middle_open,
                not finger_state.thumb_open,
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
        return all(
            (
                finger_state.is_complete,
                not finger_state.thumb_open,
                not finger_state.index_open,
                not finger_state.middle_open,
                not finger_state.ring_open,
                not finger_state.pinky_open,
                not finger_state.thumb_up,
            )
        )


class VisionSystem:
    def __init__(self) -> None:
        self._camera = cv2.VideoCapture(CAMERA_INDEX)
        hands_api = _resolve_hands_api()
        pose_api = _resolve_pose_api()
        self._hands = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._pose = pose_api.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._classifier = GestureClassifier()
        self._aruco_detector = self._build_aruco_detector()
        self._debug_frame_counter = 0
        self._last_debug_message = ""
        self._warm_up_camera()

    def read_inputs(self, prioritize_prayer_hands: bool = False) -> VisionInputs:
        if not self._camera.isOpened():
            return VisionInputs(gesture=None, marker_detected=False)

        success, frame = self._camera.read()
        if not success:
            return VisionInputs(gesture=None, marker_detected=False)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hands_result = self._hands.process(rgb_frame)
        pose_result = self._pose.process(rgb_frame)
        gesture = self._detect_gesture(
            hands_result,
            pose_result,
            frame.shape[1],
            frame.shape[0],
            prioritize_prayer_hands,
        )
        marker_detected = self._detect_marker(frame)
        self._debug_detection(
            hands_result,
            frame.shape[1],
            frame.shape[0],
            gesture,
            prioritize_prayer_hands,
        )
        return VisionInputs(gesture=gesture, marker_detected=marker_detected)

    def detect_gesture(self, prioritize_prayer_hands: bool = False) -> Optional[GestureName]:
        return self.read_inputs(prioritize_prayer_hands=prioritize_prayer_hands).gesture

    def _detect_gesture(
        self,
        hands_result,
        pose_result,
        image_width: int,
        image_height: int,
        prioritize_prayer_hands: bool,
    ) -> Optional[GestureName]:
        if prioritize_prayer_hands and self._detect_prayer_hands(pose_result):
            return GestureName.PRAYER_HANDS

        if hands_result.multi_hand_landmarks:
            if len(hands_result.multi_hand_landmarks) >= 2:
                first_gesture = self._classifier.classify(
                    hands_result.multi_hand_landmarks[0],
                    image_width,
                    image_height,
                )
                second_gesture = self._classifier.classify(
                    hands_result.multi_hand_landmarks[1],
                    image_width,
                    image_height,
                )
                if (
                    first_gesture is GestureName.CLOSED_FIST
                    and second_gesture is GestureName.CLOSED_FIST
                ):
                    return GestureName.DOUBLE_CLOSED_FIST

            for hand_landmarks in hands_result.multi_hand_landmarks[:1]:
                gesture = self._classifier.classify(hand_landmarks, image_width, image_height)
                if gesture in {
                    GestureName.HAND_OPEN,
                    GestureName.V_SIGN,
                    GestureName.THUMB_UP,
                    GestureName.POINT,
                    GestureName.CLOSED_FIST,
                }:
                    return gesture

        if self._detect_prayer_hands(pose_result):
            return GestureName.PRAYER_HANDS

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

    def _debug_detection(
        self,
        hands_result,
        image_width: int,
        image_height: int,
        gesture: Optional[GestureName],
        prioritize_prayer_hands: bool,
    ) -> None:
        self._debug_frame_counter += 1
        if self._debug_frame_counter % 12 != 0:
            return

        hand_count = 0 if not hands_result.multi_hand_landmarks else len(hands_result.multi_hand_landmarks)
        if hands_result.multi_hand_landmarks:
            finger_state = self._classifier._extract_finger_state(
                hands_result.multi_hand_landmarks[0],
                image_width,
                image_height,
            )
            message = (
                "[Vision] "
                f"hands={hand_count} "
                f"prayer_priority={'ON' if prioritize_prayer_hands else 'OFF'} "
                f"gesture={gesture.value if gesture else 'NONE'} "
                f"fingers=("
                f"T:{int(finger_state.thumb_open)} "
                f"I:{int(finger_state.index_open)} "
                f"M:{int(finger_state.middle_open)} "
                f"R:{int(finger_state.ring_open)} "
                f"P:{int(finger_state.pinky_open)})"
            )
        else:
            message = (
                "[Vision] "
                f"hands={hand_count} "
                f"prayer_priority={'ON' if prioritize_prayer_hands else 'OFF'} "
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
        self._hands.close()
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
