from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Lock, Timer
from typing import Optional

from config import COCOMAG_BAUDRATE

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
        self._cocomag_serial: Optional[serial.Serial] = None if serial else None
        self._serial_thread: Optional[threading.Thread] = None
        self._serial_running = False
        self._connect_cocomag_serial()

    def send_command(self, robot: str, command: str) -> None:
        if robot == "COCOMAG" and self._send_cocomag_command(command):
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

    def close(self) -> None:
        self._serial_running = False
        if self._serial_thread is not None:
            self._serial_thread.join(timeout=1.0)
            self._serial_thread = None

        if self._cocomag_serial is not None:
            self._cocomag_serial.close()
            self._cocomag_serial = None

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
        except serial.SerialException as exc:
            print(f"[RobotComm] Falha ao abrir serial do CocoMag em {serial_port}: {exc}")
            self._cocomag_serial = None
            return

        self._serial_running = True
        self._serial_thread = threading.Thread(
            target=self._serial_read_loop,
            name="cocomag-serial-reader",
            daemon=True,
        )
        self._serial_thread.start()
        print(f"[RobotComm] CocoMag serial conectado em {serial_port}")

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

    def _serial_read_loop(self) -> None:
        assert self._cocomag_serial is not None
        while self._serial_running:
            try:
                raw_line = self._cocomag_serial.readline()
            except serial.SerialException as exc:
                print(f"[RobotComm] Erro de leitura serial do CocoMag: {exc}")
                self._disconnect_cocomag_serial()
                break

            if not raw_line:
                continue

            message = raw_line.decode("utf-8", errors="ignore").strip()
            if message == "COCOMAG_DONE":
                self._emit_event(RobotEvent(robot="COCOMAG", status="DONE"))
            elif message:
                print(f"[RobotComm] CocoMag respondeu: {message}")

        self._serial_running = False

    def _resolve_cocomag_port(self) -> Optional[str]:
        env_port = os.environ.get("COCOMAG_SERIAL_PORT")
        if env_port:
            return env_port

        if list_ports is None:
            return None

        candidates = []
        for port in list_ports.comports():
            device = port.device or ""
            description = (port.description or "").lower()
            manufacturer = (port.manufacturer or "").lower()
            if "usb" in description or "uart" in description or "wch" in manufacturer or "silicon labs" in manufacturer:
                candidates.append(device)

        return candidates[0] if candidates else None

    def _disconnect_cocomag_serial(self) -> None:
        self._serial_running = False
        if self._cocomag_serial is not None:
            self._cocomag_serial.close()
            self._cocomag_serial = None
