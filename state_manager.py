from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import AppState, DEBOUNCE_SECONDS, GestureName, VideoAction


@dataclass
class PlaybackRequest:
    gesture: GestureName
    action: VideoAction


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

        self._active_request = PlaybackRequest(gesture=gesture, action=action)
        self._state = AppState.PLAYING_VIDEO
        self._last_triggered_gesture = gesture
        self._last_triggered_at = time.monotonic()
        self._played_videos.add(action.video_path)
        return True

    def finish_playback(self) -> None:
        self._active_request = None
        self._state = AppState.IDLE_BLACK_SCREEN

    def _is_debounced(self, gesture: GestureName) -> bool:
        is_same_gesture = gesture == self._last_triggered_gesture
        elapsed = time.monotonic() - self._last_triggered_at
        return is_same_gesture and elapsed < DEBOUNCE_SECONDS

    def _was_already_played(self, action: VideoAction) -> bool:
        return action.video_path in self._played_videos
