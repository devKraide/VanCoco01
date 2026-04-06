from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Timer
from typing import Optional

from config import COCOMAG_BAUDRATE, COCOVISION_BAUDRATE

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    serial = None
    list_ports = None


@dataclass(frozen=True)
class RobotEvent:
    robot: str
    status: str

    @property
    def code(self) -> str:
        return f"{self.robot}_{self.status}"


class RobotComm:
    def __init__(self) -> None:
        self._events: Queue[RobotEvent] = Queue()
        self._timers: list[Timer] = []
        self._lock = Lock()
        self._serial_lock = Lock()
        self._reserved_ports: set[str] = set()
        self._cocomag_serial: Optional[serial.Serial] = None if serial else None
        self._cocovision_serial: Optional[serial.Serial] = None if serial else None
        self._serial_threads: list[threading.Thread] = []
        self._serial_running = False
        self._accept_color_events = True
        self._connect_cocomag_serial()
        self._connect_cocovision_serial()

    def send_command(self, robot: str, command: str) -> None:
        if robot == "COCOMAG" and self._send_cocomag_command(command):
            return
        if robot == "COCOVISION" and self._send_cocovision_command(command):
            return

        delay_seconds = 2.0 if robot == "COCOMAG" else 2.8
        timer = Timer(
            delay_seconds,
            self._emit_event,
            args=(RobotEvent(robot=robot, status="DONE"),),
        )
        timer.daemon = True
        with self._lock:
            self._timers.append(timer)
        timer.start()

    def poll_events(self) -> list[RobotEvent]:
        events: list[RobotEvent] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except Empty:
                return events

    def set_color_events_enabled(self, enabled: bool) -> None:
        self._accept_color_events = enabled

    def clear_color_events(self) -> None:
        retained_events: list[RobotEvent] = []
        while True:
            try:
                event = self._events.get_nowait()
            except Empty:
                break

            if event.robot == "COCOVISION" and event.status.startswith("COLOR_"):
                continue
            retained_events.append(event)

        for event in retained_events:
            self._events.put(event)

    def close(self) -> None:
        self._serial_running = False
        for thread in self._serial_threads:
            thread.join(timeout=1.0)
        self._serial_threads.clear()

        if self._cocomag_serial is not None:
            self._cocomag_serial.close()
            self._cocomag_serial = None
        if self._cocovision_serial is not None:
            self._cocovision_serial.close()
            self._cocovision_serial = None

    def _emit_event(self, event: RobotEvent) -> None:
        self._events.put(event)

    def _connect_cocomag_serial(self) -> None:
        if serial is None:
            print("[RobotComm] pyserial nao instalado. CocoMag ficara em modo mock.")
            return

        if self._cocomag_serial is not None:
            return

        serial_port = self._resolve_cocomag_port()
        if serial_port is None:
            print("[RobotComm] Porta serial do CocoMag nao encontrada. Usando fallback mock.")
            return

        try:
            self._cocomag_serial = serial.Serial(serial_port, COCOMAG_BAUDRATE, timeout=0.1)
            self._cocomag_serial.reset_input_buffer()
            self._cocomag_serial.reset_output_buffer()
            self._reserved_ports.add(serial_port)
        except serial.SerialException as exc:
            print(f"[RobotComm] Falha ao abrir serial do CocoMag em {serial_port}: {exc}")
            self._cocomag_serial = None
            return

        self._serial_running = True
        serial_thread = threading.Thread(
            target=self._serial_read_loop,
            args=(self._cocomag_serial, "COCOMAG"),
            name="cocomag-serial-reader",
            daemon=True,
        )
        self._serial_threads.append(serial_thread)
        serial_thread.start()
        print(f"[RobotComm] CocoMag serial conectado em {serial_port}")

    def _connect_cocovision_serial(self) -> None:
        if serial is None:
            print("[RobotComm] pyserial nao instalado. CocoVision serial indisponivel.")
            return

        if self._cocovision_serial is not None:
            return

        serial_port = self._resolve_port("COCOVISION_SERIAL_PORT")
        if serial_port is None:
            print("[RobotComm] Porta serial do CocoVision nao encontrada.")
            return

        try:
            self._cocovision_serial = serial.Serial(serial_port, COCOVISION_BAUDRATE, timeout=0.1)
            self._cocovision_serial.reset_input_buffer()
            self._cocovision_serial.reset_output_buffer()
            self._reserved_ports.add(serial_port)
        except serial.SerialException as exc:
            print(f"[RobotComm] Falha ao abrir serial do CocoVision em {serial_port}: {exc}")
            self._cocovision_serial = None
            return

        self._serial_running = True
        serial_thread = threading.Thread(
            target=self._serial_read_loop,
            args=(self._cocovision_serial, "COCOVISION"),
            name="cocovision-serial-reader",
            daemon=True,
        )
        self._serial_threads.append(serial_thread)
        serial_thread.start()
        print(f"[RobotComm] CocoVision serial conectado em {serial_port}")

    def _send_cocomag_command(self, command: str) -> bool:
        if self._cocomag_serial is None:
            self._connect_cocomag_serial()

        if self._cocomag_serial is None:
            print("[RobotComm] CocoMag serial indisponivel. Usando fallback mock.")
            return False

        try:
            with self._serial_lock:
                self._cocomag_serial.write(f"COCOMAG:{command}\n".encode("utf-8"))
                self._cocomag_serial.flush()
            return True
        except serial.SerialException as exc:
            print(f"[RobotComm] Erro ao enviar comando para CocoMag: {exc}")
            self._disconnect_cocomag_serial()
            return False

    def _serial_read_loop(self, connection, source: str) -> None:
        while self._serial_running:
            try:
                raw_line = connection.readline()
            except serial.SerialException as exc:
                print(f"[RobotComm] Erro de leitura serial de {source}: {exc}")
                if source == "COCOMAG":
                    self._disconnect_cocomag_serial()
                else:
                    self._disconnect_cocovision_serial()
                break

            if not raw_line:
                continue

            message = raw_line.decode("utf-8", errors="ignore").strip()
            if message.startswith("COCOVISION_COLOR="):
                message = message.split("=", maxsplit=1)[1]

            if message == "COCOMAG_DONE":
                self._emit_event(RobotEvent(robot="COCOMAG", status="DONE"))
            elif message == "COCOVISION_DONE":
                self._emit_event(RobotEvent(robot="COCOVISION", status="DONE"))
            elif message in {"COLOR_RED", "COLOR_GREEN", "COLOR_BLUE"}:
                if not self._accept_color_events:
                    continue
                self._emit_event(RobotEvent(robot="COCOVISION", status=message))
            elif message:
                print(f"[RobotComm] {source} respondeu: {message}")

    def _resolve_cocomag_port(self) -> Optional[str]:
        return self._resolve_port("COCOMAG_SERIAL_PORT")

    def _resolve_port(self, env_var_name: str) -> Optional[str]:
        env_port = os.environ.get(env_var_name)
        if env_port:
            return env_port

        if list_ports is None:
            return None

        candidates = []
        for port in list_ports.comports():
            device = port.device or ""
            if device in self._reserved_ports:
                continue
            description = (port.description or "").lower()
            manufacturer = (port.manufacturer or "").lower()
            if "usb" in description or "uart" in description or "wch" in manufacturer or "silicon labs" in manufacturer:
                candidates.append(device)

        return candidates[0] if candidates else None

    def _disconnect_cocomag_serial(self) -> None:
        if self._cocomag_serial is not None:
            self._reserved_ports.discard(self._cocomag_serial.port)
            self._cocomag_serial.close()
            self._cocomag_serial = None

    def _send_cocovision_command(self, command: str) -> bool:
        if self._cocovision_serial is None:
            self._connect_cocovision_serial()

        if self._cocovision_serial is None:
            print("[RobotComm] CocoVision serial indisponivel. Usando fallback mock.")
            return False

        try:
            with self._serial_lock:
                self._cocovision_serial.write(f"COCOVISION:{command}\n".encode("utf-8"))
                self._cocovision_serial.flush()
            return True
        except serial.SerialException as exc:
            print(f"[RobotComm] Erro ao enviar comando para CocoVision: {exc}")
            self._disconnect_cocovision_serial()
            return False

    def _disconnect_cocovision_serial(self) -> None:
        if self._cocovision_serial is not None:
            self._reserved_ports.discard(self._cocovision_serial.port)
            self._cocovision_serial.close()
            self._cocovision_serial = None
