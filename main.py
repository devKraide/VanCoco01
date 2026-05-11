from __future__ import annotations

import time

from config import (
    AppState,
    CameraTriggerName,
    ENABLE_DOUBLE_CLOSED_FIST_FOR_VIDEO8,
    EXIT_KEYS,
    GestureName,
    OPERATIONAL_OVERLAY_ENABLED,
    PERF_DIAGNOSTICS,
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


IDLE_LOOP_SLEEP_SECONDS = 0.005


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
        self._last_black_screen_state: AppState | None = None
        self._loop_iteration_started_at: float | None = None
        self._loop_perf_window_started_at = time.monotonic()
        self._loop_perf_samples: list[float] = []
        self._gesture_first_raw_at: dict[GestureName, float] = {}
        self._last_operational_event = "nenhum"

    def run(self) -> None:
        try:
            self._send_robot_resets_before_idle()
            self._media_controller.show_black_screen()
            self._last_black_screen_state = self._state_manager.state
            while not self._media_controller.should_close():
                self._begin_loop_iteration()
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
                    self._media_controller.show_preview_frame(
                        self._vision_system.consume_preview_frame()
                    )
                else:
                    self._media_controller.hide_preview_overlay()
                    vision_inputs = VisionInputs(gesture=None, marker_detected=False)
                    time.sleep(IDLE_LOOP_SLEEP_SECONDS)
                self._update_operational_overlay(vision_request, vision_inputs)

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
        state = self._state_manager.state
        if self._is_playing_video():
            self._media_controller.hide_operational_overlay()
            self._media_controller.hide_preview_overlay()
        if state in {
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
            if self._last_black_screen_state is state:
                return

            self._media_controller.show_black_screen()
            self._last_black_screen_state = state
            return

        self._last_black_screen_state = None

    def _update_operational_overlay(
        self,
        vision_request: dict[str, object],
        vision_inputs: VisionInputs,
    ) -> None:
        if not OPERATIONAL_OVERLAY_ENABLED:
            return

        if self._is_playing_video():
            self._media_controller.hide_operational_overlay()
            return

        state_name = self._state_manager.state.value
        narrative_text = self._operational_state_text()

        lines = [
            f"Estado: {narrative_text}",
            f"Sistema: {state_name}",
        ]
        if self._is_waiting_visual_input():
            lines.extend(self._operational_visual_lines(vision_request, vision_inputs))
        elif self._is_waiting_robot_or_system():
            self._media_controller.hide_preview_overlay()
            lines.extend(self._operational_system_lines())
        else:
            self._media_controller.hide_preview_overlay()
            lines.append("Status: aguardando")

        lines.extend(
            [
                f"Ultimo evento: {self._last_operational_event}",
                f"Ultimo comando: {self._robot_comm.last_command()}",
                f"Ultimo retorno: {self._robot_comm.last_return()}",
            ]
        )
        self._media_controller.show_operational_overlay(lines)

    def _is_waiting_visual_input(self) -> bool:
        return self._state_manager.state in {
            AppState.IDLE_BLACK_SCREEN,
            AppState.WAITING_COCOMAG_ACTION,
            AppState.WAITING_VIDEO5_TRIGGER,
            AppState.WAITING_VIDEO6_TRIGGER,
            AppState.WAITING_VIDEO8_TRIGGER,
            AppState.WAITING_VIDEO9_TRIGGER,
        }

    def _is_waiting_robot_or_system(self) -> bool:
        return self._state_manager.state in {
            AppState.WAITING_PRESENTATION,
            AppState.WAITING_COCOMAG_ACTION_COMPLETION,
            AppState.WAITING_COCOVISION_ACTION_COMPLETION,
            AppState.WAITING_COLOR,
            AppState.WAITING_COCOVISION_RETURN_COMPLETION,
        }

    def _is_playing_video(self) -> bool:
        return self._state_manager.state is AppState.PLAYING_VIDEO

    def _operational_visual_lines(
        self,
        vision_request: dict[str, object],
        vision_inputs: VisionInputs,
    ) -> list[str]:
        raw_name = self._operational_raw_text(vision_inputs)
        reason = self._operational_reason_text(vision_inputs.rejection_reason)
        if raw_name != "NONE":
            status = "gesto reconhecido"
            reason = "aceito"
        elif vision_request["enabled"]:
            status = self._operational_vision_status(vision_inputs.rejection_reason)
        else:
            status = "aguardando"
            reason = "visao inativa"

        return [
            f"Gesto esperado: {self._operational_expected_text(vision_request)}",
            f"Visao: {status}",
            f"Raw: {raw_name}",
            f"Motivo: {reason}",
        ]

    def _operational_system_lines(self) -> list[str]:
        return (
            [f"Aguardando: {self._operational_expected_text(self._build_vision_request())}"]
            + self._operational_robot_lines()
        )

    def _operational_state_text(self) -> str:
        state = self._state_manager.state
        if state is AppState.WARMING_UP:
            return "Preparando sistema"
        if state is AppState.IDLE_BLACK_SCREEN:
            return "Aguardando gesto inicial"
        if state is AppState.WAITING_COCOMAG_ACTION:
            return "Aguardando sinal de vitoria"
        if state is AppState.WAITING_VIDEO5_TRIGGER:
            return "Aguardando polegar"
        if state is AppState.WAITING_VIDEO6_TRIGGER:
            return "Aguardando punho fechado"
        if state is AppState.WAITING_VIDEO8_TRIGGER:
            return "Aguardando punhos fechados"
        if state is AppState.WAITING_VIDEO9_TRIGGER:
            return "Aguardando oracao"
        if state is AppState.WAITING_PRESENTATION:
            return "Aguardando CocoMag e CocoVision"
        if state is AppState.WAITING_COCOMAG_ACTION_COMPLETION:
            return "Aguardando CocoMag"
        if state is AppState.WAITING_COCOVISION_ACTION_COMPLETION:
            return "Aguardando CocoVision"
        if state is AppState.WAITING_COLOR:
            return "Aguardando cor azul"
        if state is AppState.WAITING_COCOVISION_RETURN_COMPLETION:
            return "Aguardando retorno"
        return "Aguardando"

    def _operational_expected_text(self, vision_request: dict[str, object]) -> str:
        expected_gesture = vision_request["expected_gesture"]
        if expected_gesture is not None:
            return self._friendly_gesture_name(expected_gesture)

        if vision_request["detect_marker"] and vision_request["allow_double_closed_fist"]:
            return "marcador ou dois punhos"

        if vision_request["detect_marker"]:
            return "marcador"

        state = self._state_manager.state
        if state in {
            AppState.WAITING_PRESENTATION,
            AppState.WAITING_COCOMAG_ACTION_COMPLETION,
            AppState.WAITING_COCOVISION_ACTION_COMPLETION,
            AppState.WAITING_COCOVISION_RETURN_COMPLETION,
        }:
            return "retorno do robo ou fallback"

        if state is AppState.WAITING_COLOR:
            return "cor azul ou fallback"

        return "nenhum"

    def _operational_robot_lines(self) -> list[str]:
        statuses = self._robot_comm.connection_statuses()
        lines = [
            "Robos:",
            f"  CocoMag: {statuses['COCOMAG']}",
            f"  CocoVision: {statuses['COCOVISION']}",
            f"  Fallback central: {statuses['CENTRAL_FALLBACK']}",
        ]

        waiting_lines = self._operational_waiting_robot_lines()
        if waiting_lines:
            lines.extend(["Aguardando robos:", *waiting_lines])

        return lines

    def _operational_waiting_robot_lines(self) -> list[str]:
        state = self._state_manager.state
        if state is AppState.WAITING_PRESENTATION:
            pending = self._story_engine.current_pending_presentation_robots()
            return [
                f"  CocoMag: {'aguardando' if 'COCOMAG' in pending else 'OK'}",
                f"  CocoVision: {'aguardando' if 'COCOVISION' in pending else 'OK'}",
            ]

        if state is AppState.WAITING_COCOMAG_ACTION_COMPLETION:
            return ["  CocoMag: aguardando"]

        if state in {
            AppState.WAITING_COCOVISION_ACTION_COMPLETION,
            AppState.WAITING_COCOVISION_RETURN_COMPLETION,
        }:
            return ["  CocoVision: aguardando"]

        return []

    @staticmethod
    def _operational_vision_status(reason: str | None) -> str:
        if reason is None or reason == "no_hand":
            return "aguardando"

        if reason in {"outside_roi", "hands_outside_roi"}:
            return "fora da area"

        if reason in {"low_quality_hand", "palm_too_small", "insufficient_landmarks"}:
            return "ajuste a mao"

        return "ajuste a mao"

    @staticmethod
    def _operational_reason_text(reason: str | None) -> str:
        if reason is None:
            return "nenhum"

        reasons = {
            "no_hand": "sem mao detectada",
            "outside_roi": "fora da area",
            "hands_outside_roi": "maos fora da area",
            "low_quality_hand": "mao parcial/baixa qualidade",
            "palm_too_small": "mao muito distante",
            "not_expected_gesture": "gesto diferente",
            "wrong_expected_gesture": "gesto diferente",
            "index_not_extended": "indicador nao estendido",
            "fingers_not_extended": "dedos pouco estendidos",
            "requires_two_closed_fists": "precisa de dois punhos",
            "only_one_hand": "apenas uma mao",
            "one_hand_not_closed": "uma mao nao fechada",
        }
        return reasons.get(reason, reason)

    @staticmethod
    def _friendly_gesture_name(gesture: GestureName) -> str:
        names = {
            GestureName.HAND_OPEN: "mao aberta",
            GestureName.POINT: "1 dedo",
            GestureName.V_SIGN: "V",
            GestureName.THUMB_UP: "polegar",
            GestureName.CLOSED_FIST: "punho fechado",
            GestureName.DOUBLE_CLOSED_FIST: "dois punhos",
            GestureName.PRAYER_HANDS: "maos em oracao",
        }
        return names[gesture]

    @staticmethod
    def _operational_raw_text(vision_inputs: VisionInputs) -> str:
        if vision_inputs.marker_detected:
            return "MARKER"

        if vision_inputs.gesture is not None:
            return vision_inputs.gesture.value

        return "NONE"

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
        if PERF_DIAGNOSTICS:
            trigger_times = self._robot_comm.poll_central_fallback_trigger_times()
            for received_at in trigger_times:
                self._consume_central_fallback_trigger(received_at)
            return

        trigger_count = self._robot_comm.poll_central_fallback_triggers()
        for _ in range(trigger_count):
            self._consume_central_fallback_trigger(None)

    def _send_robot_resets_before_idle(self) -> None:
        if self._presentation_robot_resets_sent:
            return

        self._robot_comm.reset_presentation_robots()
        self._presentation_robot_resets_sent = True

    def _consume_central_fallback_trigger(self, received_at: float | None = None) -> None:
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
                self._log_ultra_action_dispatched(received_at)
                print(
                    f"CENTRAL_FALLBACK_ACCEPTED: {expected_gesture.value} in {state_name}"
                )
                return

        if state is AppState.WAITING_PRESENTATION:
            robot_name = self._story_engine.current_pending_presentation_robot()
            if robot_name is not None:
                self._apply_fallback_robot_event(RobotEvent(robot=robot_name, status="DONE"))
                self._log_ultra_action_dispatched(received_at)
                print(f"CENTRAL_FALLBACK_ACCEPTED: {robot_name}_DONE in {state_name}")
                return

        if state is AppState.WAITING_COCOMAG_ACTION_COMPLETION:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOMAG", status="DONE"))
            self._log_ultra_action_dispatched(received_at)
            print("CENTRAL_FALLBACK_ACCEPTED: COCOMAG_DONE in waiting_cocomag_action_completion")
            return

        if state is AppState.WAITING_COCOVISION_ACTION_COMPLETION:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOVISION", status="DONE"))
            self._log_ultra_action_dispatched(received_at)
            print(
                "CENTRAL_FALLBACK_ACCEPTED: COCOVISION_DONE in waiting_cocovision_action_completion"
            )
            return

        if state is AppState.WAITING_COLOR:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOVISION", status="COLOR_BLUE"))
            if self._state_manager.state is AppState.PLAYING_VIDEO:
                self._send_cocovision_color_confirmed()
            self._log_ultra_action_dispatched(received_at)
            print("CENTRAL_FALLBACK_ACCEPTED: COLOR_BLUE in waiting_color")
            return

        if state is AppState.WAITING_COCOVISION_RETURN_COMPLETION:
            self._apply_fallback_robot_event(RobotEvent(robot="COCOVISION", status="DONE"))
            self._log_ultra_action_dispatched(received_at)
            print(
                "CENTRAL_FALLBACK_ACCEPTED: COCOVISION_DONE in waiting_cocovision_return_completion"
            )
            return

        if state is AppState.WAITING_VIDEO8_TRIGGER:
            self._apply_fallback_video8_trigger(CameraTriggerName.MAGNIFIER_MARKER_DETECTED)
            self._log_ultra_action_dispatched(received_at)
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

        self._last_operational_event = f"fallback:{gesture.value}"
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
        self._last_operational_event = f"fallback:{event.code}"
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
        self._last_operational_event = f"fallback:{trigger_name.value}"
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
            gesture_result = self._gesture_mapper.map_gesture(vision_inputs.gesture)
            self._record_gesture_perf(vision_inputs.gesture, gesture_result)
            if gesture_result is not None:
                self._last_operational_event = gesture_result.gesture.value
            return gesture_result

        gesture_result = self._gesture_mapper.map_gesture(vision_inputs.gesture)
        self._record_gesture_perf(vision_inputs.gesture, gesture_result)
        if gesture_result is not None:
            self._last_operational_event = gesture_result.gesture.value
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
            self._record_gesture_perf(vision_inputs.gesture, gesture_result)
            if (
                gesture_result is not None
                and gesture_result.gesture is GestureName.DOUBLE_CLOSED_FIST
            ):
                trigger_name = CameraTriggerName.DOUBLE_CLOSED_FIST_DETECTED

        if TEST_GESTURES_MODE:
            self._log_test_video8_result(vision_inputs, trigger_name, gesture_result)
        if trigger_name is not None:
            self._last_operational_event = trigger_name.value
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
        if expected_gesture is GestureName.CLOSED_FIST:
            if gesture_result is not None:
                print("CLOSED_FIST_ACCEPTED")
            elif reason in {"index_open", "fingers_not_confidently_folded"}:
                print(f"CLOSED_FIST_REJECTED reason={reason}")
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

    def _begin_loop_iteration(self) -> None:
        if not PERF_DIAGNOSTICS:
            return

        now = time.monotonic()
        previous_started_at = self._loop_iteration_started_at
        self._loop_iteration_started_at = now
        if previous_started_at is None:
            self._loop_perf_window_started_at = now
            return

        elapsed_ms = (now - previous_started_at) * 1000
        if elapsed_ms > 100.0:
            print(f"PERF_LOOP_SLOW_MS={elapsed_ms:.1f}")

        self._loop_perf_samples.append(elapsed_ms)
        if now - self._loop_perf_window_started_at < 2.0:
            return

        samples = self._loop_perf_samples
        if samples:
            sorted_samples = sorted(samples)
            p95_index = int((len(sorted_samples) - 1) * 0.95)
            avg_ms = sum(samples) / len(samples)
            print(f"PERF_LOOP_AVG_MS={avg_ms:.1f} p95_ms={sorted_samples[p95_index]:.1f}")

        self._loop_perf_samples = []
        self._loop_perf_window_started_at = now

    def _record_gesture_perf(
        self,
        raw_gesture: GestureName | None,
        gesture_result: GestureResult | None,
    ) -> None:
        if not PERF_DIAGNOSTICS:
            return

        now = time.monotonic()
        if raw_gesture is not None and raw_gesture not in self._gesture_first_raw_at:
            self._gesture_first_raw_at[raw_gesture] = now
            print(f"PERF_GESTURE_RAW_DETECTED gesture={raw_gesture.value} t={now:.6f}")

        if gesture_result is None:
            return

        raw_detected_at = self._gesture_first_raw_at.pop(gesture_result.gesture, now)
        latency_ms = (now - raw_detected_at) * 1000
        print(
            "PERF_GESTURE_ACCEPTED "
            f"gesture={gesture_result.gesture.value} "
            f"latency_ms={latency_ms:.1f}"
        )

    @staticmethod
    def _log_ultra_action_dispatched(received_at: float | None) -> None:
        if not PERF_DIAGNOSTICS or received_at is None or received_at <= 0.0:
            return

        print(
            "PERF_ULTRA_ACTION_DISPATCHED "
            f"delay_ms={(time.monotonic() - received_at) * 1000:.1f}"
        )

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
