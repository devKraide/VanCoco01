from __future__ import annotations

from config import (
    AppState,
    CameraTriggerName,
    ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8,
    EXIT_KEYS,
    GestureName,
    VIDEO_ACTIONS,
)
from gesture_mapper import GestureMapper, GestureResult
from media_controller import MediaController
from robot_comm import RobotComm, RobotEvent
from story_engine import StoryEngine
from state_manager import StateManager
from vision import VisionInputs, VisionSystem


class VanCocoApp:
    def __init__(self) -> None:
        self._state_manager = StateManager()
        self._media_controller = MediaController()
        self._vision_system = VisionSystem()
        self._gesture_mapper = GestureMapper()
        self._story_engine = StoryEngine()
        self._robot_comm = RobotComm()
        self._cocomag_reset_sent_for_presentation = False

    def run(self) -> None:
        try:
            self._media_controller.show_black_screen()
            while not self._media_controller.should_close():
                # Main orchestration loop: refresh UI, sample inputs, then dispatch by AppState.
                self._media_controller.update_ui()
                self._render_current_state()
                key_code = self._media_controller.consume_key()

                if key_code in EXIT_KEYS:
                    break

                if self._state_manager.state is AppState.WARMING_UP:
                    self._handle_warming_up_state()
                    continue

                vision_request = self._build_vision_request()
                if vision_request["enabled"]:
                    vision_inputs = self._vision_system.read_inputs(
                        expected_gesture=vision_request["expected_gesture"],
                        detect_marker=vision_request["detect_marker"],
                        prioritize_prayer_hands=vision_request["prioritize_prayer_hands"],
                        allow_double_closed_fist=vision_request["allow_double_closed_fist"],
                    )
                else:
                    vision_inputs = VisionInputs(gesture=None, marker_detected=False)

                self._handle_central_fallback_triggers()

                if self._state_manager.state is AppState.IDLE_BLACK_SCREEN:
                    self._handle_idle_state(key_code, vision_inputs)
                    continue

                if self._state_manager.state is AppState.PLAYING_VIDEO:
                    self._handle_playing_state()
                    continue

                if self._state_manager.state is AppState.WAITING_PRESENTATION:
                    self._handle_waiting_presentation_state()
                    continue

                if self._state_manager.state is AppState.WAITING_COCOMAG_ACTION:
                    self._handle_waiting_cocomag_action_state(key_code, vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_VIDEO5_TRIGGER:
                    self._handle_waiting_video5_trigger_state(key_code, vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_COCOVISION_ACTION_COMPLETION:
                    self._handle_waiting_cocovision_action_completion_state()
                    continue

                if self._state_manager.state is AppState.WAITING_COLOR:
                    self._handle_waiting_color_state()
                    continue

                if self._state_manager.state is AppState.WAITING_VIDEO7_TRIGGER:
                    self._handle_waiting_video7_trigger_state(key_code, vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_VIDEO8_TRIGGER:
                    self._handle_waiting_video8_trigger_state(vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_VIDEO9_TRIGGER:
                    self._handle_waiting_video9_trigger_state(key_code, vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_COCOVISION_RETURN_COMPLETION:
                    self._handle_waiting_cocovision_return_completion_state()
                    continue

                self._handle_waiting_cocomag_action_completion_state()
        finally:
            self._robot_comm.close()
            self._media_controller.close()
            self._vision_system.release()

    def _render_current_state(self) -> None:
        if self._state_manager.state in {
            AppState.WARMING_UP,
            AppState.IDLE_BLACK_SCREEN,
            AppState.WAITING_COCOMAG_ACTION,
            AppState.WAITING_COCOMAG_ACTION_COMPLETION,
            AppState.WAITING_VIDEO5_TRIGGER,
            AppState.WAITING_COCOVISION_ACTION_COMPLETION,
            AppState.WAITING_COLOR,
            AppState.WAITING_VIDEO7_TRIGGER,
            AppState.WAITING_COCOVISION_RETURN_COMPLETION,
            AppState.WAITING_VIDEO8_TRIGGER,
            AppState.WAITING_VIDEO9_TRIGGER,
        }:
            self._media_controller.show_black_screen()

    def _handle_warming_up_state(self) -> None:
        if not self._vision_system.poll_ready():
            return

        print("[Main] entering idle")
        self._state_manager.finish_warmup()

    def _handle_idle_state(self, key_code: int, vision_inputs) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code, vision_inputs)
        )
        if gesture_result is None:
            return

        if gesture_result.action is None:
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
        # Color videos are a loopable branch: after each one finishes, the app may return to WAITING_COLOR.
        if self._story_engine.consume_color_video_finished():
            self._robot_comm.clear_color_events()
            self._robot_comm.set_color_events_enabled(True)
            if self._story_engine.is_waiting_video7_trigger():
                self._state_manager.enter_waiting_video7_trigger()
                return
            self._state_manager.enter_waiting_color()
            return

        transition = self._story_engine.complete_active_step()
        if self._story_engine.is_waiting_cocovision_action_completion():
            for robot_name, command in transition.robot_commands:
                self._robot_comm.send_command(robot_name, command)
            self._state_manager.enter_waiting_cocovision_action_completion()
            return

        if transition.robot_commands:
            self._send_cocomag_reset_before_presentation(transition.robot_commands)
            for robot_name, command in transition.robot_commands:
                self._robot_comm.send_command(robot_name, command)
            self._state_manager.enter_waiting_presentation()
            return

        if self._story_engine.is_waiting_cocomag_action():
            self._state_manager.enter_waiting_cocomag_action()
            return

        if self._story_engine.is_waiting_video5_trigger():
            self._state_manager.enter_waiting_video5_trigger()
            return

        if self._story_engine.is_waiting_color():
            self._state_manager.enter_waiting_color()
            return

        if self._story_engine.is_waiting_video7_trigger():
            self._state_manager.enter_waiting_video7_trigger()
            return

        if self._story_engine.is_waiting_video8_trigger():
            self._state_manager.enter_waiting_video8_trigger()
            return

        if self._story_engine.is_waiting_video9_trigger():
            self._state_manager.enter_waiting_video9_trigger()
            return

        self._state_manager.finish_playback()

    def _handle_waiting_presentation_state(self) -> None:
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

    def _handle_waiting_cocomag_action_state(self, key_code: int, vision_inputs) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code, vision_inputs)
        )
        if gesture_result is None or gesture_result.gesture is not GestureName.V_SIGN:
            return

        transition = self._story_engine.complete_active_step()
        for robot_name, command in transition.robot_commands:
            self._robot_comm.send_command(robot_name, command)
        self._state_manager.enter_waiting_cocomag_action_completion()

    def _handle_waiting_cocomag_action_completion_state(self) -> None:
        for event in self._robot_comm.poll_events():
            transition = self._story_engine.consume_cocomag_action_result(event)
            if transition.video_path is None:
                continue

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
                return

            self._media_controller.start_mock_video(transition.mock_video_duration)
            return

    def _handle_waiting_video5_trigger_state(self, key_code: int, vision_inputs) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code, vision_inputs)
        )
        if gesture_result is None or gesture_result.gesture is not GestureName.THUMB_UP:
            return

        if gesture_result.action is None:
            return

        self._state_manager.start_system_playback(gesture_result.action.video_path)
        if gesture_result.action.video_path.exists():
            self._media_controller.start_video(gesture_result.action.video_path)
            return

        self._media_controller.start_mock_video(2.0)

    def _handle_waiting_cocovision_action_completion_state(self) -> None:
        for event in self._robot_comm.poll_events():
            transition = self._story_engine.consume_cocovision_action_result(event)
            if not self._story_engine.is_waiting_color():
                continue

            self._robot_comm.clear_color_events()
            self._robot_comm.set_color_events_enabled(True)
            self._state_manager.enter_waiting_color()
            return

    def _handle_waiting_color_state(self) -> None:
        for event in self._robot_comm.poll_events():
            transition = self._story_engine.consume_color_event(event)
            if transition.video_path is None:
                continue

            self._robot_comm.set_color_events_enabled(False)
            self._robot_comm.clear_color_events()
            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
                return

            self._media_controller.start_mock_video(transition.mock_video_duration)
            return

    def _handle_waiting_video7_trigger_state(self, key_code: int, vision_inputs) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code, vision_inputs)
        )
        if gesture_result is None or gesture_result.gesture is not GestureName.CLOSED_FIST:
            return

        transition = self._story_engine.complete_active_step()
        for robot_name, command in transition.robot_commands:
            self._robot_comm.send_command(robot_name, command)
        self._state_manager.enter_waiting_cocovision_return_completion()

    def _handle_waiting_cocovision_return_completion_state(self) -> None:
        for event in self._robot_comm.poll_events():
            transition = self._story_engine.consume_cocovision_return_result(event)
            if transition.video_path is None:
                continue

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
                return

            self._media_controller.start_mock_video(transition.mock_video_duration)
            return

    def _handle_waiting_video8_trigger_state(self, vision_inputs) -> None:
        trigger_name = self._read_video8_trigger_source(vision_inputs)
        transition = self._story_engine.consume_video8_trigger(trigger_name)
        if transition.video_path is None:
            return

        self._state_manager.start_system_playback(transition.video_path)
        if transition.video_path.exists():
            self._media_controller.start_video(transition.video_path)
            return

        self._media_controller.start_mock_video(transition.mock_video_duration)

    def _handle_waiting_video9_trigger_state(self, key_code: int, vision_inputs) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code, vision_inputs)
        )
        if gesture_result is None or gesture_result.gesture is not GestureName.PRAYER_HANDS:
            return

        transition = self._story_engine.complete_active_step()
        if transition.video_path is None:
            return

        self._state_manager.start_system_playback(transition.video_path)
        if transition.video_path.exists():
            self._media_controller.start_video(transition.video_path)
            return

        self._media_controller.start_mock_video(transition.mock_video_duration)

    def _handle_central_fallback_triggers(self) -> None:
        trigger_count = self._robot_comm.poll_central_fallback_triggers()
        for _ in range(trigger_count):
            self._consume_central_fallback_trigger()

    def _send_cocomag_reset_before_presentation(
        self,
        robot_commands: tuple[tuple[str, str], ...],
    ) -> None:
        if self._cocomag_reset_sent_for_presentation:
            return

        if ("COCOMAG", "PRESENT") not in robot_commands:
            return

        self._robot_comm.reset_cocomag()
        self._cocomag_reset_sent_for_presentation = True

    def _consume_central_fallback_trigger(self) -> None:
        state = self._state_manager.state
        state_name = state.value

        expected_gesture = self._story_engine.current_expected_gesture()
        if expected_gesture is not None and state in {
            AppState.IDLE_BLACK_SCREEN,
            AppState.WAITING_COCOMAG_ACTION,
            AppState.WAITING_VIDEO5_TRIGGER,
            AppState.WAITING_VIDEO7_TRIGGER,
            AppState.WAITING_VIDEO9_TRIGGER,
        }:
            if self._apply_fallback_gesture(expected_gesture):
                print(
                    f"CENTRAL_FALLBACK_ACCEPTED: {expected_gesture.value} in {state_name}"
                )
                return

        if state is AppState.WAITING_PRESENTATION:
            robot_name = self._story_engine.current_pending_presentation_robot()
            if robot_name is not None:
                self._apply_fallback_robot_event(RobotEvent(robot=robot_name, status="DONE"))
                print(f"CENTRAL_FALLBACK_ACCEPTED: {robot_name}_DONE in {state_name}")
                return

        if state is AppState.WAITING_COCOMAG_ACTION_COMPLETION:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOMAG", status="DONE"))
            print("CENTRAL_FALLBACK_ACCEPTED: COCOMAG_DONE in waiting_cocomag_action_completion")
            return

        if state is AppState.WAITING_COCOVISION_ACTION_COMPLETION:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOVISION", status="DONE"))
            print(
                "CENTRAL_FALLBACK_ACCEPTED: COCOVISION_DONE in waiting_cocovision_action_completion"
            )
            return

        if state is AppState.WAITING_COLOR:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOVISION", status="COLOR_BLUE"))
            print("CENTRAL_FALLBACK_ACCEPTED: COLOR_BLUE in waiting_color")
            return

        if state is AppState.WAITING_COCOVISION_RETURN_COMPLETION:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOVISION", status="DONE"))
            print(
                "CENTRAL_FALLBACK_ACCEPTED: COCOVISION_DONE in waiting_cocovision_return_completion"
            )
            return

        if state is AppState.WAITING_VIDEO8_TRIGGER:
            self._apply_fallback_video8_trigger(CameraTriggerName.MAGNIFIER_MARKER_DETECTED)
            print("CENTRAL_FALLBACK_ACCEPTED: VIDEO8_TRIGGER in waiting_video8_trigger")
            return

        print(f"CENTRAL_FALLBACK_REJECTED in {state_name}")

    def _apply_fallback_gesture(self, gesture: GestureName) -> bool:
        gesture_result = GestureResult(gesture=gesture, action=VIDEO_ACTIONS.get(gesture))
        accepted_result = self._story_engine.consume_trigger(gesture_result)
        if accepted_result is None:
            return False

        state = self._state_manager.state
        if state is AppState.IDLE_BLACK_SCREEN:
            if accepted_result.action is None:
                return False

            playback_started = self._state_manager.request_playback(
                gesture=accepted_result.gesture,
                action=accepted_result.action,
            )
            if not playback_started:
                return False

            self._media_controller.start_video(accepted_result.action.video_path)
            return True

        if state is AppState.WAITING_COCOMAG_ACTION:
            transition = self._story_engine.complete_active_step()
            for robot_name, command in transition.robot_commands:
                self._robot_comm.send_command(robot_name, command)
            self._state_manager.enter_waiting_cocomag_action_completion()
            return True

        if state is AppState.WAITING_VIDEO5_TRIGGER:
            if accepted_result.action is None:
                return False

            self._state_manager.start_system_playback(accepted_result.action.video_path)
            if accepted_result.action.video_path.exists():
                self._media_controller.start_video(accepted_result.action.video_path)
            else:
                self._media_controller.start_mock_video(2.0)
            return True

        if state is AppState.WAITING_VIDEO7_TRIGGER:
            transition = self._story_engine.complete_active_step()
            for robot_name, command in transition.robot_commands:
                self._robot_comm.send_command(robot_name, command)
            self._state_manager.enter_waiting_cocovision_return_completion()
            return True

        if state is AppState.WAITING_VIDEO9_TRIGGER:
            transition = self._story_engine.complete_active_step()
            if transition.video_path is None:
                return False

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
            else:
                self._media_controller.start_mock_video(transition.mock_video_duration)
            return True

        return False

    def _apply_fallback_robot_event(self, event: RobotEvent) -> None:
        state = self._state_manager.state
        if state is AppState.WAITING_PRESENTATION:
            transition = self._story_engine.consume_robot_event(event)
            if transition.video_path is None:
                return

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
            else:
                self._media_controller.start_mock_video(transition.mock_video_duration)
            return

        if state is AppState.WAITING_COCOMAG_ACTION_COMPLETION:
            transition = self._story_engine.consume_cocomag_action_result(event)
            if transition.video_path is None:
                return

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
            else:
                self._media_controller.start_mock_video(transition.mock_video_duration)
            return

        if state is AppState.WAITING_COCOVISION_ACTION_COMPLETION:
            self._story_engine.consume_cocovision_action_result(event)
            if not self._story_engine.is_waiting_color():
                return

            self._robot_comm.clear_color_events()
            self._robot_comm.set_color_events_enabled(True)
            self._state_manager.enter_waiting_color()
            return

        if state is AppState.WAITING_COLOR:
            transition = self._story_engine.consume_color_event(event)
            if transition.video_path is None:
                return

            self._robot_comm.set_color_events_enabled(False)
            self._robot_comm.clear_color_events()
            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
            else:
                self._media_controller.start_mock_video(transition.mock_video_duration)
            return

        if state is AppState.WAITING_COCOVISION_RETURN_COMPLETION:
            transition = self._story_engine.consume_cocovision_return_result(event)
            if transition.video_path is None:
                return

            self._state_manager.start_system_playback(transition.video_path)
            if transition.video_path.exists():
                self._media_controller.start_video(transition.video_path)
            else:
                self._media_controller.start_mock_video(transition.mock_video_duration)

    def _apply_fallback_video8_trigger(self, trigger_name: CameraTriggerName) -> None:
        transition = self._story_engine.consume_video8_trigger(trigger_name)
        if transition.video_path is None:
            return

        self._state_manager.start_system_playback(transition.video_path)
        if transition.video_path.exists():
            self._media_controller.start_video(transition.video_path)
        else:
            self._media_controller.start_mock_video(transition.mock_video_duration)

    def _read_trigger_source(self, key_code: int, vision_inputs):
        return self._gesture_mapper.map_gesture(vision_inputs.gesture)

    def _read_video8_trigger_source(self, vision_inputs):
        if vision_inputs.marker_detected:
            return CameraTriggerName.MAGNIFIER_MARKER_DETECTED

        if (
            ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8
            and vision_inputs.gesture is GestureName.DOUBLE_CLOSED_FIST
        ):
            return CameraTriggerName.DOUBLE_CLOSED_FIST_DETECTED

        return None

    def _build_vision_request(self) -> dict[str, object]:
        state = self._state_manager.state
        if state is AppState.IDLE_BLACK_SCREEN:
            return {
                "enabled": True,
                "expected_gesture": self._story_engine.current_expected_gesture(),
                "detect_marker": False,
                "prioritize_prayer_hands": False,
                "allow_double_closed_fist": False,
            }

        if state is AppState.WAITING_COCOMAG_ACTION:
            return {"enabled": True, "expected_gesture": GestureName.V_SIGN, "detect_marker": False, "prioritize_prayer_hands": False, "allow_double_closed_fist": False}

        if state is AppState.WAITING_VIDEO5_TRIGGER:
            return {"enabled": True, "expected_gesture": GestureName.THUMB_UP, "detect_marker": False, "prioritize_prayer_hands": False, "allow_double_closed_fist": False}

        if state is AppState.WAITING_VIDEO7_TRIGGER:
            return {"enabled": True, "expected_gesture": GestureName.CLOSED_FIST, "detect_marker": False, "prioritize_prayer_hands": False, "allow_double_closed_fist": False}

        if state is AppState.WAITING_VIDEO8_TRIGGER:
            return {
                "enabled": True,
                "expected_gesture": None,
                "detect_marker": True,
                "prioritize_prayer_hands": False,
                "allow_double_closed_fist": ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8,
            }

        if state is AppState.WAITING_VIDEO9_TRIGGER:
            return {"enabled": True, "expected_gesture": GestureName.PRAYER_HANDS, "detect_marker": False, "prioritize_prayer_hands": True, "allow_double_closed_fist": False}

        return {"enabled": False, "expected_gesture": None, "detect_marker": False, "prioritize_prayer_hands": False, "allow_double_closed_fist": False}


if __name__ == "__main__":
    VanCocoApp().run()
