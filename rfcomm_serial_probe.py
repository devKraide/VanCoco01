from __future__ import annotations

import argparse
import time

import serial


DEFAULT_BAUDRATE = 115200
DEFAULT_LISTEN_SECONDS = 5.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Teste isolado de transporte serial/RFCOMM para robos ESP32."
    )
    parser.add_argument("--port", required=True, help="Ex.: /dev/rfcomm0 ou /dev/ttyUSB0")
    parser.add_argument("--command", required=True, help="Ex.: COCOMAG:PRESENT")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--listen-seconds", type=float, default=DEFAULT_LISTEN_SECONDS)
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=0.5,
        help="Espera curta apos abrir a porta antes de enviar o comando.",
    )
    args = parser.parse_args()

    try:
        with serial.Serial(args.port, args.baudrate, timeout=0.2) as connection:
            print(f"[Probe] Porta aberta: {args.port} @ {args.baudrate}")
            time.sleep(args.startup_delay)

            payload = f"{args.command}\n".encode("utf-8")
            print(f"[Probe] Enviando: {args.command!r}")
            connection.write(payload)
            connection.flush()

            deadline = time.monotonic() + args.listen_seconds
            received_anything = False
            while time.monotonic() < deadline:
                raw_line = connection.readline()
                if not raw_line:
                    continue

                message = raw_line.decode("utf-8", errors="ignore").strip()
                if not message:
                    continue

                received_anything = True
                timestamp = time.strftime("%H:%M:%S")
                print(f"[{timestamp}] {message}")

            if not received_anything:
                print("[Probe] Nenhuma resposta recebida dentro da janela de escuta.")
            return 0
    except serial.SerialException as exc:
        print(f"[Probe] Erro serial: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[Probe] Encerrado pelo usuario.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
