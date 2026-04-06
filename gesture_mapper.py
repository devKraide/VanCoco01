from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from config import GestureName, VIDEO_ACTIONS, VideoAction


@dataclass(frozen=True)
class GestureResult:
    gesture: GestureName
    action: Optional[VideoAction]


class GestureMapper:
    def __init__(self, action_map: Dict[GestureName, VideoAction] | None = None) -> None:
        self._action_map = action_map or VIDEO_ACTIONS

    def map_gesture(self, gesture: Optional[GestureName]) -> Optional[GestureResult]:
        if gesture is None:
            return None

        action = self._action_map.get(gesture)
        return GestureResult(gesture=gesture, action=action)
