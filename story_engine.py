from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from config import (
    GestureName,
    MOCK_VIDEO_DURATION_SECONDS,
    ROBOT_COMMAND_PRESENT,
    ROBOT_NAMES,
    VIDEO3_PATH,
)
from gesture_mapper import GestureResult
from robot_comm import RobotEvent


class StoryStage(Enum):
    WAIT_HAND_OPEN = "wait_hand_open"
    WAIT_POINT = "wait_point"
    WAITING_ROBOTS_PRESENTATION = "waiting_robots_presentation"
    LOCKED_END = "locked_end"


@dataclass(frozen=True)
class StoryStep:
    expected_gesture: GestureName
    next_stage: StoryStage


@dataclass(frozen=True)
class StoryTransition:
    robot_commands: tuple[tuple[str, str], ...] = ()
    video_path: Optional[Path] = None
    mock_video_duration: float = 0.0


class StoryEngine:
    def __init__(self) -> None:
        self._stage = StoryStage.WAIT_HAND_OPEN
        self._active_step: Optional[StoryStep] = None
        self._pending_robots: set[str] = set()

    def consume_trigger(self, gesture_result: Optional[GestureResult]) -> Optional[GestureResult]:
        if gesture_result is None or self._active_step is not None:
            return None

        step = self._build_current_step()
        if step is None or gesture_result.gesture is not step.expected_gesture:
            return None

        self._active_step = step
        return gesture_result

    def complete_active_step(self) -> StoryTransition:
        if self._active_step is None:
            return StoryTransition()

        self._stage = self._active_step.next_stage
        self._active_step = None
        if self._stage is StoryStage.WAITING_ROBOTS_PRESENTATION:
            self._pending_robots = set(ROBOT_NAMES)
            return StoryTransition(
                robot_commands=tuple(
                    (robot_name, ROBOT_COMMAND_PRESENT) for robot_name in ROBOT_NAMES
                )
            )

        return StoryTransition()

    def consume_robot_event(self, event: RobotEvent) -> StoryTransition:
        if self._stage is not StoryStage.WAITING_ROBOTS_PRESENTATION:
            return StoryTransition()

        if event.status != "DONE" or event.robot not in self._pending_robots:
            return StoryTransition()

        self._pending_robots.remove(event.robot)
        if self._pending_robots:
            return StoryTransition()

        self._stage = StoryStage.LOCKED_END
        return StoryTransition(
            video_path=VIDEO3_PATH,
            mock_video_duration=MOCK_VIDEO_DURATION_SECONDS,
        )

    def _build_current_step(self) -> Optional[StoryStep]:
        if self._stage is StoryStage.WAIT_HAND_OPEN:
            return StoryStep(
                expected_gesture=GestureName.HAND_OPEN,
                next_stage=StoryStage.WAIT_POINT,
            )

        if self._stage is StoryStage.WAIT_POINT:
            return StoryStep(
                expected_gesture=GestureName.POINT,
                next_stage=StoryStage.WAITING_ROBOTS_PRESENTATION,
            )

        return None
