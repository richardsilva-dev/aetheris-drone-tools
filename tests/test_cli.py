
from unittest.mock import Mock

from aetheris_drone import cli


class FakeFrame:
    def __init__(self, width: int = 640, height: int = 480):
        self.shape = (height, width, 3)

    def copy(self):
        return self


class FakeCapture:
    def __init__(self, fps: float = 30.0):
        self.fps = fps
        self.released = False

    def get(self, property_id):
        return self.fps

    def release(self):
        self.released = True


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


def configure_display(monkeypatch, wait_key=ord("q")):
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
            (float(index), frame) for index, frame in enumerate(frames)
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


def test_writer_release_failure_does_not_prevent_capture_release(
    monkeypatch, tmp_path, capsys
):
    capture = FakeCapture()
    frame = FakeFrame()
    writer = FakeWriter(release_error=RuntimeError("release failure"))
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

    assert result == 0
    assert writer.released
    assert capture.released
    assert "falha ao liberar gravador" in capsys.readouterr().err
