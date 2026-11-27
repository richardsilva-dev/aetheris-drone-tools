
import json
from unittest.mock import Mock

from aetheris_drone import cli

QUIT_KEY = ord("q")

class FakeFrame:
    def __init__(self, width: int = 640, height: int = 480):
        self.shape = (height, width, 3)

    def copy(self):
        return self


class FakeCapture:
    def __init__(self, fps: float = 30.0, release_error=None):
        self.fps = fps
        self.release_error = release_error
        self.released = False

    def get(self, property_id):
        return self.fps

    def release(self):
        self.released = True
        if self.release_error:
            raise self.release_error


class FakeWriter:
    def __init__(self, opened: bool = True, release_error=None):
        self.opened = opened
        self.release_error = release_error
        self.released = False
        self.frames = []

    def isOpened(self):
        return self.opened

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.released = True
        if self.release_error:
            raise self.release_error


def configure_display(monkeypatch, wait_key=QUIT_KEY):
    monkeypatch.setattr(cli.cv2, "putText", lambda image, *args: image)
    monkeypatch.setattr(cli.cv2, "imshow", lambda *args: None)
    monkeypatch.setattr(cli.cv2, "waitKey", lambda delay: wait_key)
    monkeypatch.setattr(cli.cv2, "destroyAllWindows", lambda: None)


def configure_capture(monkeypatch, capture, frames):
    monkeypatch.setattr(cli, "open_capture", lambda config: capture)
    monkeypatch.setattr(
        cli,
        "iter_frames",
        lambda current_capture: iter(
            (float(index) * 0.5, frame)
            for index, frame in enumerate(frames)
        ),
    )


def test_invalid_url_returns_error_without_opening_capture(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--url", "https://invalid.example"],
    )

    open_capture = Mock()
    monkeypatch.setattr(cli, "open_capture", open_capture)
    monkeypatch.setattr(cli.cv2, "destroyAllWindows", lambda: None)

    result = cli.main()

    assert result == 1
    assert "Erro:" in capsys.readouterr().out
    open_capture.assert_not_called()


def test_no_frames_returns_status_2(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aetheris-video"])

    capture = FakeCapture()

    configure_capture(monkeypatch, capture, [])
    configure_display(monkeypatch)

    result = cli.main()

    assert result == 2
    assert capture.released
    assert "Nenhum frame recebido" in capsys.readouterr().out


def test_successful_video_returns_status_0(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["aetheris-video"])

    capture = FakeCapture()
    frame = FakeFrame()

    configure_capture(monkeypatch, capture, [frame])
    configure_display(monkeypatch)

    result = cli.main()

    assert result == 0
    assert capture.released
    assert "Frames recebidos: 1" in capsys.readouterr().out


def test_successful_recording_writes_frames(monkeypatch, tmp_path):
    capture = FakeCapture(fps=25.0)
    frame = FakeFrame()
    writer = FakeWriter()

    output = tmp_path / "recordings" / "video.mp4"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--record", str(output)],
    )

    configure_capture(monkeypatch, capture, [frame])
    configure_display(monkeypatch)

    monkeypatch.setattr(cli, "ensure_parent", lambda path: output)
    monkeypatch.setattr(cli.cv2, "VideoWriter_fourcc", lambda *args: 0)
    monkeypatch.setattr(cli.cv2, "VideoWriter", lambda *args: writer)

    result = cli.main()

    assert result == 0
    assert len(writer.frames) == 1
    assert writer.released
    assert capture.released


def test_writer_failure_returns_error_and_releases_capture(
    monkeypatch, tmp_path, capsys
):
    capture = FakeCapture()
    frame = FakeFrame()
    writer = FakeWriter(opened=False)

    output = tmp_path / "video.mp4"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--record", str(output)],
    )

    configure_capture(monkeypatch, capture, [frame])
    configure_display(monkeypatch)

    monkeypatch.setattr(cli, "ensure_parent", lambda path: output)
    monkeypatch.setattr(cli.cv2, "VideoWriter_fourcc", lambda *args: 0)
    monkeypatch.setattr(cli.cv2, "VideoWriter", lambda *args: writer)

    result = cli.main()

    assert result == 1
    assert writer.released
    assert capture.released
    assert "Não foi possível criar o arquivo" in capsys.readouterr().out


def test_resolution_change_interrupts_recording(
    monkeypatch, tmp_path, capsys
):
    capture = FakeCapture()
    frames = [
        FakeFrame(width=640, height=480),
        FakeFrame(width=1280, height=720),
    ]
    writer = FakeWriter()
    output = tmp_path / "video.mp4"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--record", str(output)],
    )

    configure_capture(monkeypatch, capture, frames)
    configure_display(monkeypatch, wait_key=-1)

    monkeypatch.setattr(cli, "ensure_parent", lambda path: output)
    monkeypatch.setattr(cli.cv2, "VideoWriter_fourcc", lambda *args: 0)
    monkeypatch.setattr(cli.cv2, "VideoWriter", lambda *args: writer)

    result = cli.main()

    assert result == 1
    assert len(writer.frames) == 1
    assert writer.released
    assert capture.released
    assert "resolução do vídeo mudou" in capsys.readouterr().out


def test_writer_release_failure_changes_session_status(
    monkeypatch, tmp_path, capsys
):
    capture = FakeCapture()
    frame = FakeFrame()
    writer = FakeWriter(release_error=RuntimeError("release failure"))
    output = tmp_path / "session.json"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output), "--record", "video.mp4"],
    )

    configure_capture(monkeypatch, capture, [frame])
    configure_display(monkeypatch)

    monkeypatch.setattr(cli, "ensure_parent", lambda path: tmp_path / "video.mp4")
    monkeypatch.setattr(cli.cv2, "VideoWriter_fourcc", lambda *args: 0)
    monkeypatch.setattr(cli.cv2, "VideoWriter", lambda *args: writer)

    result = cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))

    assert result == 1
    assert writer.released
    assert capture.released
    assert report["status"] == "error"
    assert report["stop_reason"] == "cleanup_error"
    assert report["exit_code"] == 1
    assert "release failure" in report["error"]
    assert len(report["cleanup_errors"]) == 1
    assert "Falha ao liberar gravador" in capsys.readouterr().err


def test_capture_release_failure_is_recorded_without_changing_session_status(
    monkeypatch, tmp_path, capsys
):
    capture = FakeCapture(release_error=RuntimeError("capture release failure"))
    output = tmp_path / "session.json"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output)],
    )

    configure_capture(monkeypatch, capture, [FakeFrame()])
    configure_display(monkeypatch)

    result = cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert capture.released
    assert report["status"] == "completed"
    assert report["exit_code"] == 0
    assert len(report["cleanup_errors"]) == 1
    assert "capture release failure" in report["cleanup_errors"][0]
    assert "Falha ao liberar captura" in capsys.readouterr().err


def test_stats_json_records_successful_session(monkeypatch, tmp_path, capsys):
    capture = FakeCapture()
    frames = [FakeFrame(), FakeFrame(), FakeFrame()]
    output = tmp_path / "reports" / "session.json"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output)],
    )
    configure_capture(monkeypatch, capture, frames)
    configure_display(monkeypatch, wait_key=-1)

    result = cli.main()

    report = json.loads(output.read_text(encoding="utf-8"))

    assert result == 0
    assert report["schema_version"] == 1
    assert report["status"] == "completed"
    assert report["stop_reason"] == "read_ended"
    assert report["frames_received"] == 3
    assert report["average_fps"] == 2.0
    assert report["exit_code"] == 0
    assert report["error"] is None
    assert report["cleanup_errors"] == []
    assert capture.released
    assert "Relatório da sessão salvo" in capsys.readouterr().out


def test_stats_json_records_user_stop(monkeypatch, tmp_path):
    capture = FakeCapture()
    output = tmp_path / "session.json"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output)],
    )
    configure_capture(monkeypatch, capture, [FakeFrame()])
    configure_display(monkeypatch, wait_key=ord("q"))

    assert cli.main() == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["stop_reason"] == "user_requested"
    assert report["frames_received"] == 1
    assert report["average_fps"] == 0.0


def test_stats_json_records_connection_error(monkeypatch, tmp_path):
    output = tmp_path / "session.json"

    def fail_connection(config):
        raise ConnectionError("RTSP unavailable")

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output)],
    )
    monkeypatch.setattr(cli, "open_capture", fail_connection)
    monkeypatch.setattr(cli.cv2, "destroyAllWindows", lambda: None)

    assert cli.main() == 1

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["stop_reason"] == "error"
    assert report["error"] == "RTSP unavailable"
    assert report["exit_code"] == 1


def test_stats_json_records_unexpected_exception(monkeypatch, tmp_path):
    output = tmp_path / "session.json"

    def fail_connection(config):
        raise LookupError("unexpected failure")

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output)],
    )
    monkeypatch.setattr(cli, "open_capture", fail_connection)
    monkeypatch.setattr(cli.cv2, "destroyAllWindows", lambda: None)

    assert cli.main() == 1

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "error"
    assert report["stop_reason"] == "error"
    assert report["error"] == "unexpected failure"
    assert report["exit_code"] == 1


def test_stats_json_records_empty_stream(monkeypatch, tmp_path):
    capture = FakeCapture()
    output = tmp_path / "session.json"

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(output)],
    )
    configure_capture(monkeypatch, capture, [])
    configure_display(monkeypatch)

    assert cli.main() == 2

    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "no_frames"
    assert report["stop_reason"] == "read_ended"
    assert report["frames_received"] == 0
    assert report["average_fps"] == 0.0
    assert report["exit_code"] == 2


def test_report_write_failure_does_not_mask_session_result(
    monkeypatch, tmp_path, capsys
):
    capture = FakeCapture()

    monkeypatch.setattr(
        "sys.argv",
        ["aetheris-video", "--stats-json", str(tmp_path / "session.json")],
    )
    configure_capture(monkeypatch, capture, [FakeFrame()])
    configure_display(monkeypatch)

    def fail_report(path, report):
        raise OSError("disk unavailable")

    monkeypatch.setattr(cli, "write_session_report", fail_report)

    result = cli.main()

    assert result == 0
    assert capture.released
    assert "não foi possível salvar o relatório" in capsys.readouterr().err

def test_stats_json_redacts_credentials_and_query_from_rejected_url(
    monkeypatch, tmp_path
):
    secret = "do-not-store-this-token"
    source_url = (
        f"rtsp://operator:{secret}@camera.example/live?token={secret}"
    )
    output = tmp_path / "session.json"

    monkeypatch.setattr(
        "sys.argv",
        [
            "aetheris-video",
            "--url",
            source_url,
            "--stats-json",
            str(output),
        ],
    )
    open_capture = Mock()
    monkeypatch.setattr(cli, "open_capture", open_capture)
    monkeypatch.setattr(cli.cv2, "destroyAllWindows", lambda: None)

    assert cli.main() == 1

    serialized = output.read_text(encoding="utf-8")
    report = json.loads(serialized)
    assert report["source_url"] == "rtsp://camera.example/[redacted]"
    assert secret not in serialized
    open_capture.assert_not_called()
