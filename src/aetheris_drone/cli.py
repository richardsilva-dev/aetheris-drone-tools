"""Interface de linha de comando para visualizar o fluxo RTSP."""

from __future__ import annotations

import argparse
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


def main() -> int:
    args = build_parser().parse_args()
    config = VideoConfig(url=args.url)
    capture = None
    writer = None
    timestamps: deque[float] = deque(maxlen=60)
    frames_seen = 0

    try:
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
                if writer is None:
                    output = ensure_parent(args.record)
                    height, width = frame.shape[:2]
                    source_fps = capture.get(cv2.CAP_PROP_FPS)
                    record_fps = source_fps if source_fps and source_fps > 0 else 20.0
                    writer = cv2.VideoWriter(
                        str(output),
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        record_fps,
                        (width, height),
                    )
                    if not writer.isOpened():
                        raise RuntimeError(f"Não foi possível criar o arquivo: {output}")
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
    except (ConnectionError, RuntimeError, ValueError) as exc:
        print(f"Erro: {exc}")
        return 1
    finally:
        if writer is not None:
            writer.release()
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    raise SystemExit(main())
