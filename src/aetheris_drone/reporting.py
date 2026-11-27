"""Persistência de relatórios de diagnóstico de sessões de vídeo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


def write_session_report(
    path: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """Grava um relatório JSON UTF-8, substituindo o destino atomicamente."""
    output = Path(path)
    serialized = json.dumps(
        dict(report),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")

    try:
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(output)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise

    return output
