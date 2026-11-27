
"""Interface de linha de comando para visualizar o fluxo RTSP."""

from __future__ import annotations

import argparse
import math
import sys
from collections import deque

import cv2

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
    return parser


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

    try:
        config = VideoConfig(url=args.url)
        capture = open_capture(config)

        print("Fluxo RTSP conectado. Pressione q ou Esc na janela para encerrar.")

        for timestamp, frame in iter_frames(capture):
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
                break

        print(f"Frames recebidos: {frames_seen}")

        if frames_seen == 0:
            print("Nenhum frame recebido. Verifique a rede e a URL RTSP.")
            return 2

        return 0

    except (
        ConnectionError,
        OSError,
        RuntimeError,
        ValueError,
        cv2.error,
    ) as exc:
        print(f"Erro: {exc}")
        return 1

    finally:
        for resource, description in (
            (writer, "gravador"),
            (capture, "captura"),
        ):
            if resource is not None:
                try:
                    resource.release()
                except Exception as exc:
                    print(
                        f"Aviso: falha ao liberar {description}: {exc}",
                        file=sys.stderr,
                    )

        try:
            cv2.destroyAllWindows()
        except cv2.error as exc:
            print(
                f"Aviso: falha ao fechar as janelas do OpenCV: {exc}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    raise SystemExit(main())
