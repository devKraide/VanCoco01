from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import AppState, DEBOUNCE_SECONDS, GestureName, VideoAction


@dataclass
class PlaybackRequest:
    video_path: Path
    gesture: Optional[GestureName] = None


class StateManager:
    def __init__(self) -> None:
        self._state = AppState.IDLE_BLACK_SCREEN
        self._active_request: Optional[PlaybackRequest] = None
        self._last_triggered_gesture: Optional[GestureName] = None
        self._last_triggered_at = 0.0
        self._played_videos: set[Path] = set()

    @property
    def state(self) -> AppState:
        return self._state

    @property
    def active_request(self) -> Optional[PlaybackRequest]:
        return self._active_request

    def can_accept_gesture(self) -> bool:
        return self._state is AppState.IDLE_BLACK_SCREEN

    def request_playback(self, gesture: GestureName, action: VideoAction) -> bool:
        if not self.can_accept_gesture():
            return False

        if self._was_already_played(action):
            return False

        if self._is_debounced(gesture):
            return False

        self._active_request = PlaybackRequest(
            video_path=action.video_path,
            gesture=gesture,
        )
        self._state = AppState.PLAYING_VIDEO
        self._last_triggered_gesture = gesture
        self._last_triggered_at = time.monotonic()
        self._played_videos.add(action.video_path)
        return True

    def start_system_playback(self, video_path: Path) -> None:
        self._active_request = PlaybackRequest(video_path=video_path)
        self._state = AppState.PLAYING_VIDEO

    def enter_waiting_presentation(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_PRESENTATION

    def enter_waiting_cocomag_action(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_COCOMAG_ACTION

    def enter_waiting_cocomag_action_completion(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_COCOMAG_ACTION_COMPLETION

    def enter_waiting_video5_trigger(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_VIDEO5_TRIGGER

    def enter_waiting_cocovision_action_completion(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_COCOVISION_ACTION_COMPLETION

    def enter_waiting_color(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_COLOR

    def enter_waiting_video7_trigger(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_VIDEO7_TRIGGER

    def enter_waiting_cocovision_return_completion(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_COCOVISION_RETURN_COMPLETION

    def enter_waiting_video8_trigger(self) -> None:
        self._active_request = None
        self._state = AppState.WAITING_VIDEO8_TRIGGER

    def finish_playback(self) -> None:
        self._active_request = None
        self._state = AppState.IDLE_BLACK_SCREEN

    def _is_debounced(self, gesture: GestureName) -> bool:
        is_same_gesture = gesture == self._last_triggered_gesture
        elapsed = time.monotonic() - self._last_triggered_at
        return is_same_gesture and elapsed < DEBOUNCE_SECONDS

    def _was_already_played(self, action: VideoAction) -> bool:
        return action.video_path in self._played_videos
