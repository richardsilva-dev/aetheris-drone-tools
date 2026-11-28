"""Interface de linha de comando para visualizar ou gravar um fluxo RTSP."""

from __future__ import annotations

import argparse
import os
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
        default=os.environ.get("AETHERIS_RTSP_URL", "rtsp://192.168.1.1:7070/webcam"),
        help="URL RTSP da câmera (ou variável AETHERIS_RTSP_URL).",
    )
    parser.add_argument(
        "--record",
        metavar="ARQUIVO",
        help="Grava o fluxo em um arquivo de vídeo (ex.: recordings/teste.mp4).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Não abre janela; útil para gravação em sessões remotas ou sem monitor.",
    )
    parser.add_argument(
        "--open-timeout",
        type=int,
        default=8_000,
        metavar="MS",
        help="Tempo máximo para conectar ao fluxo (padrão: 8000 ms).",
    )
    parser.add_argument(
        "--read-timeout",
        type=int,
        default=5_000,
        metavar="MS",
        help="Tempo máximo para aguardar cada frame (padrão: 5000 ms).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    capture = None
    writer = None
    timestamps: deque[float] = deque(maxlen=60)
    frames_seen = 0

    try:
        config = VideoConfig(
            url=args.url,
            open_timeout_ms=args.open_timeout,
            read_timeout_ms=args.read_timeout,
        )
        capture = open_capture(config)
        if args.headless:
            print("Fluxo RTSP conectado. Capturando sem janela; use Ctrl+C para encerrar.")
        else:
            print("Fluxo RTSP conectado. Pressione q ou Esc na janela para encerrar.")

        for timestamp, frame in iter_frames(capture):
            timestamps.append(timestamp)
            frames_seen += 1
            fps = estimate_fps(list(timestamps))

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

            if not args.headless:
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
                cv2.imshow("Aetheris - Drone Video (somente leitura)", display)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break

        print(f"Frames recebidos: {frames_seen}")
        if frames_seen == 0:
            print("Nenhum frame recebido. Verifique a rede e a URL RTSP.")
            return 2
        return 0
    except KeyboardInterrupt:
        print(f"Captura interrompida. Frames recebidos: {frames_seen}")
        return 130
    except (ConnectionError, RuntimeError, ValueError, cv2.error) as exc:
        print(f"Erro: {exc}")
        return 1
    finally:
        if writer is not None:
            writer.release()
        if capture is not None:
            capture.release()
        if not args.headless:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
