from __future__ import annotations

import argparse
import sys
import time

import serial
from serial.tools import list_ports


VALID_MESSAGES = {"COLOR_RED", "COLOR_GREEN", "COLOR_BLUE", "TCS34725_NOT_FOUND"}
DEFAULT_BAUDRATE = 115200


def resolve_port(preferred_port: str | None) -> str | None:
    if preferred_port:
        return preferred_port

    for port in list_ports.comports():
        description = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        if "usb" in description or "uart" in description or "wch" in manufacturer or "silicon labs" in manufacturer:
            return port.device

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Leitor serial isolado do CocoVision.")
    parser.add_argument("--port", help="Porta serial do ESP32.")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    args = parser.parse_args()

    port = resolve_port(args.port)
    if port is None:
        print("[CocoVision] Nenhuma porta serial encontrada.")
        return 1

    try:
        with serial.Serial(port, args.baudrate, timeout=0.2) as connection:
            print(f"[CocoVision] Escutando {port} em {args.baudrate} baud.")
            while True:
                raw_line = connection.readline()
                if not raw_line:
                    continue

                message = raw_line.decode("utf-8", errors="ignore").strip()
                if not message:
                    continue

                timestamp = time.strftime("%H:%M:%S")
                if message in VALID_MESSAGES:
                    print(f"[{timestamp}] {message}")
                    continue

                print(f"[{timestamp}] UNKNOWN: {message}")
    except serial.SerialException as exc:
        print(f"[CocoVision] Erro na serial: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[CocoVision] Encerrado pelo usuario.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
