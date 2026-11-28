
"""Persistência de relatórios de diagnóstico de sessões de vídeo."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def write_session_report(
    path: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """Grava um relatório JSON UTF-8 e substitui o destino atomicamente."""
    output = Path(path)
    serialized = (
        json.dumps(
            dict(report),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )

    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(serialized)

        temporary_path.replace(output)

    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise

    return output
