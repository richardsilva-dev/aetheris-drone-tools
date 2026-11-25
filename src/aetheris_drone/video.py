"""Recepção de vídeo RTSP em modo somente leitura."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Iterator

import cv2


@dataclass(frozen=True)
class VideoConfig:
    """Configuração de uma fonte de vídeo RTSP."""

    url: str = "rtsp://192.168.1.1:7070/webcam"
    open_timeout_ms: int = 8_000
    read_timeout_ms: int = 5_000

    def __post_init__(self) -> None:
        if not self.url.lower().startswith(("rtsp://", "rtsps://")):
            raise ValueError("A URL precisa usar o esquema rtsp:// ou rtsps://")
        if self.open_timeout_ms <= 0 or self.read_timeout_ms <= 0:
            raise ValueError("Os timeouts precisam ser positivos")


def open_capture(config: VideoConfig) -> cv2.VideoCapture:
    """Abre o fluxo RTSP. Não transmite dados de controle ao drone."""
    params = [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
        config.open_timeout_ms,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
        config.read_timeout_ms,
    ]
    capture = cv2.VideoCapture(config.url, cv2.CAP_FFMPEG, params)
    if not capture.isOpened():
        capture.release()
        raise ConnectionError(
            "Não foi possível abrir o fluxo RTSP. Verifique a conexão Wi-Fi, "
            "o endereço do fluxo e se o serviço da câmera está ativo."
        )
    return capture


def iter_frames(capture: cv2.VideoCapture) -> Iterator[tuple[float, object]]:
    """Produz pares (tempo_monotônico, frame) até a leitura falhar."""
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        yield monotonic(), frame


def estimate_fps(timestamps: list[float]) -> float:
    """Estima FPS pela diferença entre timestamps monotônicos consecutivos."""
    if len(timestamps) < 2:
        return 0.0
    elapsed = timestamps[-1] - timestamps[0]
    if elapsed <= 0:
        return 0.0
    return (len(timestamps) - 1) / elapsed


def ensure_parent(path: str) -> Path:
    """Cria a pasta de destino e retorna o caminho do arquivo."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output
