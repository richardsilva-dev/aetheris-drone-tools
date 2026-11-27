import json

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
    assert not output.with_name(".session.json.tmp").exists()


def test_rejects_non_finite_json_values(tmp_path):
    output = tmp_path / "session.json"

    with pytest.raises(ValueError):
        write_session_report(output, {"average_fps": float("nan")})

    assert not output.exists()
