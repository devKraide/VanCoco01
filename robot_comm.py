from __future__ import annotations

import os
import platform
import threading
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Timer
from typing import Optional

from config import (
    COCOMAG_BAUDRATE,
    COCOMAG_COMM_MODE,
    COCOMAG_PORT,
    COCOVISION_BAUDRATE,
    COCOVISION_COMM_MODE,
    COCOVISION_PORT,
)

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
        self._connections: dict[str, object] = {"COCOMAG": None, "COCOVISION": None}
        self._serial_threads: list[threading.Thread] = []
        self._serial_running = False
        self._accept_color_events = True
        self._connect_robot("COCOMAG")
        self._connect_robot("COCOVISION")

    def send_command(self, robot: str, command: str) -> None:
        if self._send_robot_command(robot, command):
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
        self._disconnect_robot("COCOMAG")
        self._disconnect_robot("COCOVISION")

    def _emit_event(self, event: RobotEvent) -> None:
        self._events.put(event)

    def _connect_robot(self, robot: str) -> None:
        if serial is None:
            print(f"[RobotComm] pyserial nao instalado. {robot} ficara em modo mock.")
            return

        if self._connections[robot] is not None:
            return

        mode = self._get_comm_mode(robot)
        port = self._resolve_robot_port(robot, mode)
        if port is None:
            print(
                f"[RobotComm] Porta de {robot} nao encontrada para modo {mode}. "
                "Usando fallback mock."
            )
            return

        try:
            connection = serial.Serial(port, self._get_baudrate(robot), timeout=0.1)
            if mode == "serial":
                connection.reset_input_buffer()
                connection.reset_output_buffer()
            self._reserved_ports.add(port)
            self._connections[robot] = connection
        except serial.SerialException as exc:
            print(f"[RobotComm] Falha ao abrir {mode} de {robot} em {port}: {exc}")
            self._connections[robot] = None
            return

        self._serial_running = True
        serial_thread = threading.Thread(
            target=self._serial_read_loop,
            args=(connection, robot),
            name=f"{robot.lower()}-{mode}-reader",
            daemon=True,
        )
        self._serial_threads.append(serial_thread)
        serial_thread.start()
        print(f"[RobotComm] {robot} conectado via {mode} em {port}")

    def _send_robot_command(self, robot: str, command: str) -> bool:
        connection = self._connections[robot]
        if connection is None:
            self._connect_robot(robot)
            connection = self._connections[robot]

        if connection is None:
            print(f"[RobotComm] {robot} indisponivel. Usando fallback mock.")
            return False

        try:
            with self._serial_lock:
                print(f"[RobotComm] Enviando para {robot}: {robot}:{command}")
                connection.write(f"{robot}:{command}\n".encode("utf-8"))
                connection.flush()
            return True
        except serial.SerialException as exc:
            print(f"[RobotComm] Erro ao enviar comando para {robot}: {exc}")
            self._disconnect_robot(robot)
            return False

    def _serial_read_loop(self, connection, source: str) -> None:
        while self._serial_running:
            try:
                raw_line = connection.readline()
            except serial.SerialException as exc:
                print(f"[RobotComm] Erro de leitura de {source}: {exc}")
                self._disconnect_robot(source)
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

    def _disconnect_robot(self, robot: str) -> None:
        connection = self._connections[robot]
        if connection is None:
            return

        self._reserved_ports.discard(connection.port)
        connection.close()
        self._connections[robot] = None

    def _resolve_robot_port(self, robot: str, mode: str) -> Optional[str]:
        env_port = os.environ.get(f"{robot}_PORT")
        if env_port:
            return env_port

        configured_port = COCOMAG_PORT if robot == "COCOMAG" else COCOVISION_PORT
        if configured_port:
            return configured_port

        if mode == "rfcomm":
            return None

        if list_ports is None:
            return None

        candidates = []
        for port in list_ports.comports():
            device = port.device or ""
            if device in self._reserved_ports:
                continue
            if platform.system() == "Windows" and device.upper().startswith("COM"):
                candidates.append(device)
                continue
            description = (port.description or "").lower()
            manufacturer = (port.manufacturer or "").lower()
            if (
                "usb" in description
                or "uart" in description
                or "serial" in description
                or "wch" in manufacturer
                or "silicon labs" in manufacturer
            ):
                candidates.append(device)

        return candidates[0] if candidates else None

    def _get_comm_mode(self, robot: str) -> str:
        return COCOMAG_COMM_MODE if robot == "COCOMAG" else COCOVISION_COMM_MODE

    def _get_baudrate(self, robot: str) -> int:
        return COCOMAG_BAUDRATE if robot == "COCOMAG" else COCOVISION_BAUDRATE
