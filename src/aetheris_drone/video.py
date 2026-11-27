
"""Recepção de vídeo RTSP em modo somente leitura."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Iterator
from urllib.parse import urlsplit

import cv2


@dataclass(frozen=True)
class VideoConfig:
    """Configuração de uma fonte de vídeo RTSP."""

    url: str = "rtsp://192.168.1.1:7070/webcam"
    open_timeout_ms: int = 8_000
    read_timeout_ms: int = 5_000

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url:
            raise ValueError("A URL RTSP precisa ser uma string não vazia")

        if any(ord(char) < 32 or ord(char) == 127 for char in self.url):
            raise ValueError("A URL não pode conter caracteres de controle")

        if any(char.isspace() for char in self.url):
            raise ValueError("A URL não pode conter espaços")

        try:
            parsed = urlsplit(self.url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"URL RTSP inválida: {exc}") from exc

        if parsed.scheme.lower() not in {"rtsp", "rtsps"}:
            raise ValueError("A URL precisa usar rtsp:// ou rtsps://")

        if not parsed.netloc or not parsed.hostname:
            raise ValueError("A URL precisa informar um hostname")

        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Credenciais embutidas na URL não são permitidas")

        if port is not None and not 1 <= port <= 65535:
            raise ValueError("A porta RTSP precisa estar entre 1 e 65535")

        if "#" in self.url:
            raise ValueError("Fragmentos não são permitidos na URL RTSP")

        valid_open_timeout = (
            isinstance(self.open_timeout_ms, int)
            and not isinstance(self.open_timeout_ms, bool)
            and self.open_timeout_ms > 0
        )

        valid_read_timeout = (
            isinstance(self.read_timeout_ms, int)
            and not isinstance(self.read_timeout_ms, bool)
            and self.read_timeout_ms > 0
        )

        if not valid_open_timeout or not valid_read_timeout:
            raise ValueError("Os timeouts precisam ser inteiros positivos")


def open_capture(config: VideoConfig) -> cv2.VideoCapture:
    """Abre o fluxo RTSP sem transmitir comandos ao drone."""
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
