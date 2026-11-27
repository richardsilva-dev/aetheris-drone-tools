"""Interface de linha de comando para visualizar o fluxo RTSP."""

from __future__ import annotations

import argparse
import math
import sys
from collections import deque
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import urlsplit

import cv2

from .reporting import write_session_report
from .video import VideoConfig, ensure_parent, estimate_fps, iter_frames, open_capture


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aetheris-video",
        description="Recebe e exibe vídeo RTSP em modo somente leitura.",
    )
    parser.add_argument(
        "--url",
        default="rtsp://192.168.1.1:7070/webcam",
        help="URL RTSP da câmera do drone.",
    )
    parser.add_argument(
        "--record",
        metavar="ARQUIVO",
        help="Grava o fluxo em um arquivo de vídeo (ex.: recordings/teste.mp4).",
    )
    parser.add_argument(
        "--stats-json",
        metavar="ARQUIVO",
        help="Salva métricas e o resultado da sessão em um relatório JSON.",
    )
    return parser


def _redact_source_url(value: str) -> str:
    """Keep only the RTSP endpoint authority; never persist credentials or tokens."""
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return "[redacted]"

    if scheme not in {"rtsp", "rtsps"} or not hostname:
        return "[redacted]"

    safe_host = hostname.lower()
    if ":" in safe_host:
        safe_host = f"[{safe_host}]"
    authority = safe_host + (f":{port}" if port is not None else "")
    return f"{scheme}://{authority}/[redacted]"


def _get_frame_dimensions(frame: object) -> tuple[int, int]:
    """Obtém e valida as dimensões de um frame."""
    shape = getattr(frame, "shape", None)

    if shape is None or len(shape) < 2:
        raise RuntimeError("O frame recebido não possui dimensões válidas.")

    height, width = shape[:2]

    if height <= 0 or width <= 0:
        raise RuntimeError("O frame recebido possui dimensões inválidas.")

    return width, height


def _get_recording_fps(capture: cv2.VideoCapture) -> float:
    """Obtém um FPS válido para a gravação ou utiliza um valor padrão."""
    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    except (TypeError, ValueError, OverflowError):
        return 20.0

    if not math.isfinite(source_fps) or source_fps <= 0:
        return 20.0

    return source_fps


def main() -> int:
    args = build_parser().parse_args()

    capture = None
    writer = None
    recording_size = None

    timestamps: deque[float] = deque(maxlen=60)
    frames_seen = 0
    first_frame_timestamp = None
    last_frame_timestamp = None

    session_started_at = datetime.now(timezone.utc).isoformat()
    session_started = monotonic()

    status = "error"
    stop_reason = "error"
    exit_code = 1
    error_message = None
    cleanup_errors: list[str] = []

    try:
        config = VideoConfig(url=args.url)
        capture = open_capture(config)
        stop_reason = "read_ended"

        print("Fluxo RTSP conectado. Pressione q ou Esc na janela para encerrar.")

        for timestamp, frame in iter_frames(capture):
            if first_frame_timestamp is None:
                first_frame_timestamp = timestamp

            last_frame_timestamp = timestamp
            timestamps.append(timestamp)
            frames_seen += 1

            fps = estimate_fps(list(timestamps))
            display = frame.copy()

            cv2.putText(
                display,
                f"FPS local: {fps:.1f} | Frames: {frames_seen}",
                (12, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

            if args.record:
                frame_size = _get_frame_dimensions(frame)

                if writer is None:
                    output = ensure_parent(args.record)
                    record_fps = _get_recording_fps(capture)

                    writer = cv2.VideoWriter(
                        str(output),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        record_fps,
                        frame_size,
                    )

                    recording_size = frame_size

                    if not writer.isOpened():
                        raise RuntimeError(
                            f"Não foi possível criar o arquivo: {output}"
                        )

                elif frame_size != recording_size:
                    raise RuntimeError(
                        "A resolução do vídeo mudou durante a gravação. "
                        "A gravação foi interrompida para evitar inconsistências."
                    )

                writer.write(frame)

            cv2.imshow("Aetheris - Drone Video (somente leitura)", display)

            key = cv2.waitKey(1) & 0xFF

            if key in (ord("q"), 27):
                stop_reason = "user_requested"
                break

        print(f"Frames recebidos: {frames_seen}")

        if frames_seen == 0:
            print("Nenhum frame recebido. Verifique a rede e a URL RTSP.")
            status = "no_frames"
            exit_code = 2
        else:
            status = "completed"
            exit_code = 0

    # A CLI precisa registrar também exceções inesperadas da sessão.
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        status = "error"
        stop_reason = "error"
        exit_code = 1
        print(f"Erro: {exc}")

    finally:
        for resource, description in (
            (writer, "gravador"),
            (capture, "captura"),
        ):
            if resource is None:
                continue

            try:
                resource.release()
            # A falha de um recurso não deve impedir a liberação do próximo.
            except Exception as exc:  # noqa: BLE001
                cleanup_message = f"Falha ao liberar {description}: {exc}"
                cleanup_errors.append(cleanup_message)

                print(
                    f"Aviso: {cleanup_message}",
                    file=sys.stderr,
                )

                if description == "gravador" and status != "error":
                    status = "error"
                    stop_reason = "cleanup_error"
                    exit_code = 1
                    error_message = cleanup_message

        try:
            cv2.destroyAllWindows()
        # O fechamento das janelas não deve impedir a geração do relatório.
        except Exception as exc:  # noqa: BLE001
            cleanup_message = f"Falha ao fechar as janelas do OpenCV: {exc}"
            cleanup_errors.append(cleanup_message)

            print(
                f"Aviso: {cleanup_message}",
                file=sys.stderr,
            )

        if args.stats_json:
            elapsed = max(0.0, monotonic() - session_started)

            if (
                frames_seen >= 2
                and first_frame_timestamp is not None
                and last_frame_timestamp is not None
                and math.isfinite(first_frame_timestamp)
                and math.isfinite(last_frame_timestamp)
                and last_frame_timestamp > first_frame_timestamp
            ):
                average_fps = (frames_seen - 1) / (
                    last_frame_timestamp - first_frame_timestamp
                )
            else:
                average_fps = 0.0

            report = {
                "schema_version": 1,
                "started_at_utc": session_started_at,
                "duration_seconds": round(elapsed, 3),
                "source_url": _redact_source_url(args.url),
                "frames_received": frames_seen,
                "average_fps": round(average_fps, 3),
                "status": status,
                "stop_reason": stop_reason,
                "exit_code": exit_code,
                "recording_file": args.record,
                "error": error_message,
                "cleanup_errors": cleanup_errors,
            }

            try:
                output = write_session_report(args.stats_json, report)
                print(f"Relatório da sessão salvo em: {output}")
            # Uma falha no relatório não deve mascarar o resultado da sessão.
            except Exception as exc:  # noqa: BLE001
                print(
                    f"Aviso: não foi possível salvar o relatório: {exc}",
                    file=sys.stderr,
                )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
