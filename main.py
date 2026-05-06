from __future__ import annotations

from config import (
    AppState,
    CameraTriggerName,
    ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8,
    EXIT_KEYS,
    GestureName,
    ROBOT_COMMAND_COLOR_CONFIRMED,
    TEST_GESTURES_MODE,
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
        self._presentation_robot_resets_sent = False
        self._last_test_gesture_snapshot = None

    def run(self) -> None:
        try:
            self._send_robot_resets_before_idle()
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

                if self._state_manager.state is AppState.WAITING_VIDEO6_TRIGGER:
                    self._handle_waiting_video6_trigger_state(key_code, vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_COCOVISION_RETURN_COMPLETION:
                    self._handle_waiting_cocovision_return_completion_state()
                    continue

                if self._state_manager.state is AppState.WAITING_VIDEO8_TRIGGER:
                    self._handle_waiting_video8_trigger_state(vision_inputs)
                    continue

                if self._state_manager.state is AppState.WAITING_VIDEO9_TRIGGER:
                    self._handle_waiting_video9_trigger_state(key_code, vision_inputs)
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
            AppState.WAITING_VIDEO6_TRIGGER,
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
        color_transition = self._story_engine.consume_color_video_finished()
        if color_transition is not None:
            self._robot_comm.clear_color_events()
            if self._story_engine.is_waiting_cocovision_return_completion():
                self._robot_comm.set_color_events_enabled(False)
                for robot_name, command in color_transition.robot_commands:
                    if robot_name == "COCOVISION" and command == "RETURN":
                        print("SENDING_COCOVISION_RETURN")
                    self._robot_comm.send_command(robot_name, command)
                print("WAITING_COCOVISION_RETURN_DONE")
                self._state_manager.enter_waiting_cocovision_return_completion()
                return
            self._robot_comm.set_color_events_enabled(True)
            self._state_manager.enter_waiting_color()
            return

        transition = self._story_engine.complete_active_step()
        if self._story_engine.is_waiting_cocovision_action_completion():
            self._robot_comm.set_color_events_enabled(False)
            self._robot_comm.clear_color_events()
            for robot_name, command in transition.robot_commands:
                self._robot_comm.send_command(robot_name, command)
            self._state_manager.enter_waiting_cocovision_action_completion()
            return

        if transition.robot_commands:
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

        if self._story_engine.is_waiting_video6_trigger():
            self._state_manager.enter_waiting_video6_trigger()
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

    def _handle_waiting_video6_trigger_state(self, key_code: int, vision_inputs) -> None:
        gesture_result = self._story_engine.consume_trigger(
            self._read_trigger_source(key_code, vision_inputs)
        )
        if gesture_result is None or gesture_result.gesture is not GestureName.CLOSED_FIST:
            return

        if gesture_result.action is None:
            return

        self._state_manager.start_system_playback(gesture_result.action.video_path)
        if gesture_result.action.video_path.exists():
            self._media_controller.start_video(gesture_result.action.video_path)
            return

        self._media_controller.start_mock_video(2.0)

    def _handle_waiting_cocovision_return_completion_state(self) -> None:
        for event in self._robot_comm.poll_events():
            transition = self._story_engine.consume_cocovision_return_result(event)
            if not self._story_engine.is_waiting_video8_trigger():
                continue

            print("COCOVISION_RETURN_DONE_RECEIVED")
            self._state_manager.enter_waiting_video8_trigger()
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

    def _send_robot_resets_before_idle(self) -> None:
        if self._presentation_robot_resets_sent:
            return

        self._robot_comm.reset_presentation_robots()
        self._presentation_robot_resets_sent = True

    def _consume_central_fallback_trigger(self) -> None:
        state = self._state_manager.state
        state_name = state.value

        expected_gesture = self._story_engine.current_expected_gesture()
        if expected_gesture is not None and state in {
            AppState.IDLE_BLACK_SCREEN,
            AppState.WAITING_COCOMAG_ACTION,
            AppState.WAITING_VIDEO5_TRIGGER,
            AppState.WAITING_VIDEO6_TRIGGER,
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
            if self._state_manager.state is AppState.PLAYING_VIDEO:
                self._send_cocovision_color_confirmed()
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

    def _send_cocovision_color_confirmed(self) -> None:
        print("SENDING_COCOVISION_COLOR_CONFIRMED")
        self._robot_comm.send_command("COCOVISION", ROBOT_COMMAND_COLOR_CONFIRMED)

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

        if state is AppState.WAITING_VIDEO6_TRIGGER:
            if accepted_result.action is None:
                return False

            self._state_manager.start_system_playback(accepted_result.action.video_path)
            if accepted_result.action.video_path.exists():
                self._media_controller.start_video(accepted_result.action.video_path)
            else:
                self._media_controller.start_mock_video(2.0)
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
            self._story_engine.consume_cocovision_return_result(event)
            if not self._story_engine.is_waiting_video8_trigger():
                return

            print("COCOVISION_RETURN_DONE_RECEIVED")
            self._state_manager.enter_waiting_video8_trigger()
            return

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
        if not TEST_GESTURES_MODE:
            return self._gesture_mapper.map_gesture(vision_inputs.gesture)

        gesture_result = self._gesture_mapper.map_gesture(vision_inputs.gesture)
        self._log_test_gesture_result(
            raw_gesture=vision_inputs.gesture,
            gesture_result=gesture_result,
            vision_reason=vision_inputs.rejection_reason,
        )
        return gesture_result

    def _read_video8_trigger_source(self, vision_inputs):
        trigger_name = None
        gesture_result = None
        if vision_inputs.marker_detected:
            trigger_name = CameraTriggerName.MAGNIFIER_MARKER_DETECTED

        elif ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8:
            gesture_result = self._gesture_mapper.map_gesture(vision_inputs.gesture)
            if (
                gesture_result is not None
                and gesture_result.gesture is GestureName.DOUBLE_CLOSED_FIST
            ):
                trigger_name = CameraTriggerName.DOUBLE_CLOSED_FIST_DETECTED

        if TEST_GESTURES_MODE:
            self._log_test_video8_result(vision_inputs, trigger_name, gesture_result)
        return trigger_name

    def _log_test_gesture_result(
        self,
        raw_gesture: GestureName | None,
        gesture_result: GestureResult | None,
        vision_reason: str | None,
    ) -> None:
        state = self._state_manager.state
        expected_gesture = self._story_engine.current_expected_gesture()
        stable_gesture = self._gesture_mapper.stable_gesture
        result_text = "ACCEPTED" if gesture_result is not None else "REJECTED"
        reason = self._test_gesture_reason(
            raw_gesture=raw_gesture,
            gesture_result=gesture_result,
            vision_reason=vision_reason,
        )
        snapshot = (
            state,
            expected_gesture,
            raw_gesture,
            stable_gesture,
            result_text,
            reason,
        )
        if snapshot == self._last_test_gesture_snapshot:
            return

        self._last_test_gesture_snapshot = snapshot
        if trigger_name is CameraTriggerName.DOUBLE_CLOSED_FIST_DETECTED:
            print("DOUBLE_FIST_ACCEPTED")
        elif (
            not vision_inputs.marker_detected
            and reason in {"only_one_hand", "one_hand_not_closed", "hands_outside_roi"}
        ):
            print(f"DOUBLE_FIST_REJECTED reason={reason}")
        message = (
            "TEST_GESTURES "
            f"state={state.value} "
            f"expected={self._format_gesture(expected_gesture)} "
            f"raw={self._format_gesture(raw_gesture)} "
            f"stable={self._format_gesture(stable_gesture)} "
            f"result={result_text} "
            f"reason={reason}"
        )
        print(message)

    def _log_test_video8_result(
        self,
        vision_inputs: VisionInputs,
        trigger_name: CameraTriggerName | None,
        gesture_result: GestureResult | None,
    ) -> None:
        state = self._state_manager.state
        raw_trigger = "NONE"
        if vision_inputs.marker_detected:
            raw_trigger = CameraTriggerName.MAGNIFIER_MARKER_DETECTED.value
        elif vision_inputs.gesture is GestureName.DOUBLE_CLOSED_FIST:
            raw_trigger = GestureName.DOUBLE_CLOSED_FIST.value

        stable_trigger = trigger_name.value if trigger_name is not None else "NONE"
        result_text = "ACCEPTED" if trigger_name is not None else "REJECTED"
        if trigger_name is not None:
            reason = "accepted"
        elif vision_inputs.rejection_reason is not None:
            reason = vision_inputs.rejection_reason
        elif vision_inputs.gesture is GestureName.DOUBLE_CLOSED_FIST:
            reason = self._gesture_mapper.last_result_reason
        else:
            reason = "requires_two_closed_fists"
        snapshot = (
            state,
            "MAGNIFIER_MARKER_DETECTED_OR_DOUBLE_CLOSED_FIST",
            raw_trigger,
            stable_trigger,
            result_text,
            reason,
            gesture_result.gesture if gesture_result is not None else None,
        )
        if snapshot == self._last_test_gesture_snapshot:
            return

        self._last_test_gesture_snapshot = snapshot
        if expected_gesture is GestureName.CLOSED_FIST:
            if gesture_result is not None:
                print("CLOSED_FIST_ACCEPTED")
            elif reason in {"index_open", "fingers_not_confidently_folded"}:
                print(f"CLOSED_FIST_REJECTED reason={reason}")
        message = (
            "TEST_GESTURES "
            f"state={state.value} "
            "expected=MAGNIFIER_MARKER_DETECTED_OR_DOUBLE_CLOSED_FIST "
            f"raw={raw_trigger} "
            f"stable={stable_trigger} "
            f"result={result_text} "
            f"reason={reason}"
        )
        print(message)

    def _test_gesture_reason(
        self,
        raw_gesture: GestureName | None,
        gesture_result: GestureResult | None,
        vision_reason: str | None,
    ) -> str:
        if gesture_result is not None:
            return "accepted"

        if vision_reason is not None:
            return vision_reason

        if raw_gesture is None:
            return "no_raw_gesture"

        expected_gesture = self._story_engine.current_expected_gesture()
        if expected_gesture is not None and raw_gesture is not expected_gesture:
            return "wrong_expected_gesture"

        return self._gesture_mapper.last_result_reason

    @staticmethod
    def _format_gesture(gesture: GestureName | None) -> str:
        return gesture.value if gesture is not None else "NONE"

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

        if state is AppState.WAITING_VIDEO6_TRIGGER:
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
