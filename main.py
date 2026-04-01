from __future__ import annotations

from config import AppState, EXIT_KEYS, KEY_ACTIONS
from gesture_mapper import GestureMapper
from media_controller import MediaController
from state_manager import StateManager
from vision import VisionSystem


class VanCocoApp:
    def __init__(self) -> None:
        self._state_manager = StateManager()
        self._media_controller = MediaController()
        self._vision_system = VisionSystem()
        self._gesture_mapper = GestureMapper()

    def run(self) -> None:
        try:
            self._media_controller.show_black_screen()
            while not self._media_controller.should_close():
                self._media_controller.update_ui()
                self._render_current_state()
                key_code = self._media_controller.consume_key()

                if key_code in EXIT_KEYS:
                    break

                if self._state_manager.state is AppState.IDLE_BLACK_SCREEN:
                    self._handle_idle_state(key_code)
                    continue

                self._handle_playing_state()
        finally:
            self._media_controller.close()
            self._vision_system.release()

    def _render_current_state(self) -> None:
        if self._state_manager.state is AppState.IDLE_BLACK_SCREEN:
            self._media_controller.show_black_screen()

    def _handle_idle_state(self, key_code: int) -> None:
        gesture_result = self._read_trigger_source(key_code)
        if gesture_result is None:
            return

        playback_started = self._state_manager.request_playback(
            gesture=gesture_result.gesture,
            action=gesture_result.action,
        )
        if not playback_started:
            return

        self._media_controller.start_video(gesture_result.action.video_path)

    def _handle_playing_state(self) -> None:
        if not self._media_controller.consume_video_finished():
            return

        self._media_controller.stop_video()
        self._state_manager.finish_playback()

    def _read_trigger_source(self, key_code: int):
        keyboard_gesture = KEY_ACTIONS.get(key_code) if key_code is not None else None
        if keyboard_gesture is not None:
            return self._gesture_mapper.map_gesture(keyboard_gesture)

        detected_gesture = self._vision_system.detect_gesture()
        return self._gesture_mapper.map_gesture(detected_gesture)


if __name__ == "__main__":
    VanCocoApp().run()
