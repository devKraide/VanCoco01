from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from config import (
    GESTURE_MISSING_FRAME_TOLERANCE,
    GESTURE_STABLE_FRAMES,
    GestureName,
    VIDEO_ACTIONS,
    VideoAction,
)


@dataclass(frozen=True)
class GestureResult:
    gesture: GestureName
    action: Optional[VideoAction]


class GestureMapper:
    def __init__(self, action_map: Dict[GestureName, VideoAction] | None = None) -> None:
        self._action_map = action_map or VIDEO_ACTIONS
        self._last_seen_gesture: Optional[GestureName] = None
        self._stable_frames = 0
        self._latched_gesture: Optional[GestureName] = None
        self._last_debug_message = ""
        self._missing_frames = 0
        self._last_result_reason = "no_raw_gesture"

    def map_gesture(self, gesture: Optional[GestureName]) -> Optional[GestureResult]:
        if gesture is None:
            if (
                self._last_seen_gesture is not None
                and self._missing_frames < GESTURE_MISSING_FRAME_TOLERANCE
            ):
                self._missing_frames += 1
                self._last_result_reason = "missing_frames_tolerated"
                return None

            self._last_seen_gesture = None
            self._stable_frames = 0
            self._latched_gesture = None
            self._missing_frames = 0
            self._last_result_reason = "no_raw_gesture"
            return None

        self._missing_frames = 0
        if gesture is self._last_seen_gesture:
            self._stable_frames += 1
        else:
            self._last_seen_gesture = gesture
            self._stable_frames = 1
            self._latched_gesture = None
            self._last_result_reason = "stabilizing"
            return None

        if self._stable_frames < GESTURE_STABLE_FRAMES:
            self._last_result_reason = "stabilizing"
            return None

        if self._latched_gesture is gesture:
            self._last_result_reason = "already_latched"
            return None

        self._latched_gesture = gesture
        action = self._action_map.get(gesture)
        self._debug_emit(gesture, action is not None)
        self._last_result_reason = "accepted"
        return GestureResult(gesture=gesture, action=action)

    @property
    def stable_gesture(self) -> Optional[GestureName]:
        if self._stable_frames < GESTURE_STABLE_FRAMES:
            return None
        return self._last_seen_gesture

    @property
    def last_result_reason(self) -> str:
        return self._last_result_reason

    def _debug_emit(self, gesture: GestureName, has_action: bool) -> None:
        message = f"[GestureMapper] accepted={gesture.value} action={'YES' if has_action else 'NO'}"
        if message == self._last_debug_message:
            return

        self._last_debug_message = message
        print(message)
