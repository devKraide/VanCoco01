from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from config import GestureName
from gesture_mapper import GestureResult


class StoryStage(Enum):
    WAIT_HAND_OPEN = "wait_hand_open"
    WAIT_POINT = "wait_point"
    LOCKED_END = "locked_end"


@dataclass(frozen=True)
class StoryStep:
    expected_gesture: GestureName
    next_stage: StoryStage


class StoryEngine:
    def __init__(self) -> None:
        self._stage = StoryStage.WAIT_HAND_OPEN
        self._active_step: Optional[StoryStep] = None

    def consume_trigger(self, gesture_result: Optional[GestureResult]) -> Optional[GestureResult]:
        if gesture_result is None or self._active_step is not None:
            return None

        step = self._build_current_step()
        if step is None or gesture_result.gesture is not step.expected_gesture:
            return None

        self._active_step = step
        return gesture_result

    def complete_active_step(self) -> None:
        if self._active_step is None:
            return

        self._stage = self._active_step.next_stage
        self._active_step = None

    def _build_current_step(self) -> Optional[StoryStep]:
        if self._stage is StoryStage.WAIT_HAND_OPEN:
            return StoryStep(
                expected_gesture=GestureName.HAND_OPEN,
                next_stage=StoryStage.WAIT_POINT,
            )

        if self._stage is StoryStage.WAIT_POINT:
            return StoryStep(
                expected_gesture=GestureName.POINT,
                next_stage=StoryStage.LOCKED_END,
            )

        return None
