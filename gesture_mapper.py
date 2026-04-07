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
        return GestureResult(gesture=gesture, action=action)
