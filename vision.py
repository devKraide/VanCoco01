from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np

from config import (
    CAMERA_INDEX,
    CAMERA_WARMUP_FRAMES,
    DETECTION_CONFIDENCE,
    GestureName,
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


@dataclass(frozen=True)
class FingerState:
    thumb_open: bool
    index_open: bool
    middle_open: bool
    ring_open: bool
    pinky_open: bool


class GestureClassifier:
    def classify(self, hand_landmarks, image_width: int, image_height: int) -> Optional[GestureName]:
        finger_state = self._extract_finger_state(hand_landmarks, image_width, image_height)

        if self._is_hand_open(finger_state):
            return GestureName.HAND_OPEN

        if self._is_point(finger_state):
            return GestureName.POINT

        return None

    def _extract_finger_state(self, hand_landmarks, image_width: int, image_height: int) -> FingerState:
        landmark = hand_landmarks.landmark

        def to_pixel(index: int) -> tuple[float, float]:
            point = landmark[index]
            return point.x * image_width, point.y * image_height

        wrist_x, _ = to_pixel(0)
        thumb_tip_x, _ = to_pixel(4)
        thumb_ip_x, _ = to_pixel(3)

        index_tip_y = to_pixel(8)[1]
        index_pip_y = to_pixel(6)[1]
        middle_tip_y = to_pixel(12)[1]
        middle_pip_y = to_pixel(10)[1]
        ring_tip_y = to_pixel(16)[1]
        ring_pip_y = to_pixel(14)[1]
        pinky_tip_y = to_pixel(20)[1]
        pinky_pip_y = to_pixel(18)[1]

        thumb_open = self._is_thumb_extended(thumb_tip_x, thumb_ip_x, wrist_x)
        return FingerState(
            thumb_open=thumb_open,
            index_open=index_tip_y < index_pip_y,
            middle_open=middle_tip_y < middle_pip_y,
            ring_open=ring_tip_y < ring_pip_y,
            pinky_open=pinky_tip_y < pinky_pip_y,
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
                finger_state.thumb_open,
                finger_state.index_open,
                finger_state.middle_open,
                finger_state.ring_open,
                finger_state.pinky_open,
            )
        )

    @staticmethod
    def _is_point(finger_state: FingerState) -> bool:
        return all(
            (
                finger_state.index_open,
                not finger_state.middle_open,
                not finger_state.ring_open,
                not finger_state.pinky_open,
            )
        )


class VisionSystem:
    def __init__(self) -> None:
        self._camera = cv2.VideoCapture(CAMERA_INDEX)
        hands_api = _resolve_hands_api()
        self._hands = hands_api.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
        )
        self._classifier = GestureClassifier()
        self._warm_up_camera()

    def detect_gesture(self) -> Optional[GestureName]:
        if not self._camera.isOpened():
            return None

        success, frame = self._camera.read()
        if not success:
            return None

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._hands.process(rgb_frame)
        if not result.multi_hand_landmarks:
            return None

        image_height, image_width = frame.shape[:2]
        first_hand = result.multi_hand_landmarks[0]
        return self._classifier.classify(first_hand, image_width, image_height)

    def release(self) -> None:
        self._camera.release()
        self._hands.close()

    def _warm_up_camera(self) -> None:
        for _ in range(CAMERA_WARMUP_FRAMES):
            self._camera.read()
