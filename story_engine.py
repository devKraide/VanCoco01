from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from config import (
    COLOR_VIDEO_PATHS,
    GestureName,
    MOCK_VIDEO_DURATION_SECONDS,
    ROBOT_COMMAND_ACTION,
    ROBOT_COMMAND_PRESENT,
    ROBOT_COMMAND_SCAN,
    ROBOT_NAMES,
    VIDEO3_PATH,
    VIDEO4_PATH,
    VIDEO5_PATH,
)
from gesture_mapper import GestureResult
from robot_comm import RobotEvent


class StoryStage(Enum):
    WAIT_HAND_OPEN = "wait_hand_open"
    WAIT_POINT = "wait_point"
    WAITING_PRESENTATION = "waiting_presentation"
    WAITING_COCOMAG_ACTION = "waiting_cocomag_action"
    WAITING_COCOMAG_ACTION_COMPLETION = "waiting_cocomag_action_completion"
    WAITING_VIDEO5_TRIGGER = "waiting_video5_trigger"
    WAITING_COCOVISION_ACTION_COMPLETION = "waiting_cocovision_action_completion"
    WAITING_COLOR = "waiting_color"
    PLAYING_COLOR_VIDEO = "playing_color_video"
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
        self._consumed_colors: set[str] = set()

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
        if self._stage is StoryStage.WAITING_PRESENTATION:
            self._pending_robots = set(ROBOT_NAMES)
            return StoryTransition(
                robot_commands=tuple(
                    (robot_name, ROBOT_COMMAND_PRESENT) for robot_name in ROBOT_NAMES
                )
            )

        if self._stage is StoryStage.WAITING_COCOMAG_ACTION_COMPLETION:
            return StoryTransition(
                robot_commands=(("COCOMAG", ROBOT_COMMAND_ACTION),),
            )

        if self._stage is StoryStage.WAITING_COCOVISION_ACTION_COMPLETION:
            return StoryTransition(
                robot_commands=(("COCOVISION", ROBOT_COMMAND_ACTION),),
            )

        return StoryTransition()

    def consume_robot_event(self, event: RobotEvent) -> StoryTransition:
        if self._stage is not StoryStage.WAITING_PRESENTATION:
            return StoryTransition()

        if event.status != "DONE" or event.robot not in self._pending_robots:
            return StoryTransition()

        self._pending_robots.remove(event.robot)
        if self._pending_robots:
            return StoryTransition()

        self._stage = StoryStage.WAITING_COCOMAG_ACTION
        return StoryTransition(video_path=VIDEO3_PATH)

    def consume_cocomag_action_result(self, event: RobotEvent) -> StoryTransition:
        if self._stage is not StoryStage.WAITING_COCOMAG_ACTION_COMPLETION:
            return StoryTransition()

        if event.robot != "COCOMAG" or event.status != "DONE":
            return StoryTransition()

        self._stage = StoryStage.WAITING_VIDEO5_TRIGGER
        return StoryTransition(
            video_path=VIDEO4_PATH,
            mock_video_duration=MOCK_VIDEO_DURATION_SECONDS,
        )

    def consume_cocovision_action_result(self, event: RobotEvent) -> StoryTransition:
        if self._stage is not StoryStage.WAITING_COCOVISION_ACTION_COMPLETION:
            return StoryTransition()

        if event.robot != "COCOVISION" or event.status != "DONE":
            return StoryTransition()

        self._stage = StoryStage.WAITING_COLOR
        return StoryTransition()

    def consume_color_event(self, event: RobotEvent) -> StoryTransition:
        if self._stage is not StoryStage.WAITING_COLOR:
            return StoryTransition()

        if event.robot != "COCOVISION":
            return StoryTransition()

        if event.status in self._consumed_colors:
            return StoryTransition()

        video_path = COLOR_VIDEO_PATHS.get(event.status)
        if video_path is None:
            return StoryTransition()

        self._consumed_colors.add(event.status)
        self._stage = StoryStage.PLAYING_COLOR_VIDEO
        return StoryTransition(
            video_path=video_path,
            mock_video_duration=MOCK_VIDEO_DURATION_SECONDS,
        )

    def consume_color_video_finished(self) -> bool:
        if self._stage is not StoryStage.PLAYING_COLOR_VIDEO:
            return False

        self._stage = StoryStage.WAITING_COLOR
        return True

    def is_waiting_cocomag_action(self) -> bool:
        return self._stage is StoryStage.WAITING_COCOMAG_ACTION

    def is_waiting_video5_trigger(self) -> bool:
        return self._stage is StoryStage.WAITING_VIDEO5_TRIGGER

    def is_waiting_cocovision_action_completion(self) -> bool:
        return self._stage is StoryStage.WAITING_COCOVISION_ACTION_COMPLETION

    def is_waiting_color(self) -> bool:
        return self._stage is StoryStage.WAITING_COLOR

    def _build_current_step(self) -> Optional[StoryStep]:
        if self._stage is StoryStage.WAIT_HAND_OPEN:
            return StoryStep(
                expected_gesture=GestureName.HAND_OPEN,
                next_stage=StoryStage.WAIT_POINT,
            )

        if self._stage is StoryStage.WAIT_POINT:
            return StoryStep(
                expected_gesture=GestureName.POINT,
                next_stage=StoryStage.WAITING_PRESENTATION,
            )

        if self._stage is StoryStage.WAITING_COCOMAG_ACTION:
            return StoryStep(
                expected_gesture=GestureName.V_SIGN,
                next_stage=StoryStage.WAITING_COCOMAG_ACTION_COMPLETION,
            )

        if self._stage is StoryStage.WAITING_VIDEO5_TRIGGER:
            return StoryStep(
                expected_gesture=GestureName.THUMB_UP,
                next_stage=StoryStage.WAITING_COCOVISION_ACTION_COMPLETION,
            )

        return None
