from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from config import GESTURE_STABLE_FRAMES, GestureName, VIDEO_ACTIONS, VideoAction


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

    def map_gesture(self, gesture: Optional[GestureName]) -> Optional[GestureResult]:
        if gesture is None:
            self._last_seen_gesture = None
            self._stable_frames = 0
            self._latched_gesture = None
            return None

        if gesture is self._last_seen_gesture:
            self._stable_frames += 1
        else:
            self._last_seen_gesture = gesture
            self._stable_frames = 1
            self._latched_gesture = None
            return None

        if self._stable_frames < GESTURE_STABLE_FRAMES:
            return None

        if self._latched_gesture is gesture:
            return None

        self._latched_gesture = gesture
        action = self._action_map.get(gesture)
        self._debug_emit(gesture, action is not None)
        return GestureResult(gesture=gesture, action=action)

    @property
    def stable_frames(self) -> int:
        return self._stable_frames

    @property
    def stable_gesture(self) -> Optional[GestureName]:
        if self._stable_frames < GESTURE_STABLE_FRAMES:
            return None
        return self._last_seen_gesture

    def diagnostic_rejection_reason(
        self,
        raw_gesture: Optional[GestureName],
        result: Optional[GestureResult],
        expected_gesture: Optional[GestureName],
    ) -> Optional[str]:
        if result is not None:
            return None

        if expected_gesture is None:
            return "no_expected_gesture"

        if raw_gesture is None:
            return "no_raw_gesture_or_unexpected"

        if raw_gesture is not expected_gesture:
            return "raw_gesture_mismatch"

        if self._stable_frames < GESTURE_STABLE_FRAMES:
            return "stabilizing"

        if self._latched_gesture is raw_gesture:
            return "already_latched"

        if raw_gesture not in self._action_map:
            return "no_action_for_gesture"

        return "not_accepted"

    def _debug_emit(self, gesture: GestureName, has_action: bool) -> None:
        message = f"[GestureMapper] accepted={gesture.value} action={'YES' if has_action else 'NO'}"
        if message == self._last_debug_message:
            return

        self._last_debug_message = message
        print(message)
