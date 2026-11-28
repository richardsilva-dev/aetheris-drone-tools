import json
from pathlib import Path

import pytest

from aetheris_drone.reporting import write_session_report


def test_writes_utf8_json_and_creates_parent_directory(tmp_path):
    output = tmp_path / "diagnostics" / "session.json"
    report = {
        "status": "completed",
        "frames_received": 12,
        "message": "sessão concluída",
    }

    result = write_session_report(output, report)

    assert result == output
    assert json.loads(output.read_text(encoding="utf-8")) == report


def test_replaces_existing_report_atomically(tmp_path):
    output = tmp_path / "session.json"
    output.write_text('{"status": "old"}', encoding="utf-8")

    write_session_report(output, {"status": "new"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "new"}
    assert list(tmp_path.glob(".session.json.*.tmp")) == []


def test_rejects_non_finite_json_values(tmp_path):
    output = tmp_path / "session.json"

    with pytest.raises(ValueError):
        write_session_report(output, {"average_fps": float("nan")})

    assert not output.exists()


def test_preserves_original_error_when_temporary_cleanup_fails(
    tmp_path,
    monkeypatch,
):
    output = tmp_path / "session.json"
    original_error = OSError("Falha ao substituir relatório")

    def fail_replace(self, target):
        raise original_error

    def fail_unlink(self, *args, **kwargs):
        raise OSError("Falha na limpeza")

    monkeypatch.setattr(Path, "replace", fail_replace)
    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(OSError, match="Falha ao substituir relatório") as exc:
        write_session_report(output, {"status": "completed"})

    assert exc.value is original_error
