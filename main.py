from __future__ import annotations

from config import AppState, EXIT_KEYS, KEY_ACTIONS
from gesture_mapper import GestureMapper
from media_controller import MediaController
from robot_comm import RobotComm
from story_engine import StoryEngine
from state_manager import StateManager
from vision import VisionSystem


class VanCocoApp:
    def __init__(self) -> None:
        self._state_manager = StateManager()
        self._media_controller = MediaController()
        self._vision_system = VisionSystem()
        self._gesture_mapper = GestureMapper()
        self._story_engine = StoryEngine()
        self._robot_comm = RobotComm()

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

                if self._state_manager.state is AppState.PLAYING_VIDEO:
                    self._handle_playing_state()
                    continue

                self._handle_waiting_robots_state()
        finally:
            self._robot_comm.close()
            self._media_controller.close()
            self._vision_system.release()

    def _render_current_state(self) -> None:
        if self._state_manager.state is AppState.IDLE_BLACK_SCREEN:
            self._media_controller.show_black_screen()

    def _handle_idle_state(self, key_code: int) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code)
        )
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
        transition = self._story_engine.complete_active_step()
        if transition.robot_commands:
            for robot_name, command in transition.robot_commands:
                self._robot_comm.send_command(robot_name, command)
            self._state_manager.enter_waiting_robots_presentation()
            return

        self._state_manager.finish_playback()

    def _handle_waiting_robots_state(self) -> None:
        for event in self._robot_comm.poll_events():
            transition = self._story_engine.consume_robot_event(event)
            if transition.video_path is None:
                continue

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
                return

            self._media_controller.start_mock_video(transition.mock_video_duration)
            return

    def _read_trigger_source(self, key_code: int):
        keyboard_gesture = KEY_ACTIONS.get(key_code) if key_code is not None else None
        if keyboard_gesture is not None:
            return self._gesture_mapper.map_gesture(keyboard_gesture)

        detected_gesture = self._vision_system.detect_gesture()
        return self._gesture_mapper.map_gesture(detected_gesture)


if __name__ == "__main__":
    VanCocoApp().run()
