
from unittest.mock import Mock

import pytest

import aetheris_drone.video as video_module
from aetheris_drone.video import VideoConfig, estimate_fps


def test_default_url_is_the_verified_rtsp_endpoint():
    assert VideoConfig().url == "rtsp://192.168.1.1:7070/webcam"


def test_rejects_non_rtsp_url():
    with pytest.raises(ValueError):
        VideoConfig(url="http://192.168.1.1/video")


@pytest.mark.parametrize("field", ["open_timeout_ms", "read_timeout_ms"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "1000", None])
def test_rejects_invalid_timeout_values(field, value):
    with pytest.raises(ValueError):
        VideoConfig(**{field: value})


def test_accepts_positive_integer_timeouts():
    config = VideoConfig(
        open_timeout_ms=10_000,
        read_timeout_ms=5_000,
    )

    assert config.open_timeout_ms == 10_000
    assert config.read_timeout_ms == 5_000


def test_estimates_fps_from_monotonic_timestamps():
    assert estimate_fps([1.0, 1.1, 1.2, 1.3]) == pytest.approx(10.0)


def test_fps_requires_two_timestamps():
    assert estimate_fps([1.0]) == 0.0


def test_fps_handles_non_positive_elapsed_time():
    assert estimate_fps([2.0, 2.0]) == 0.0


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://192.168.1.1/video",
        "rtsp://",
        "rtsp://:7070/webcam",
        "rtsp://camera:invalid/webcam",
        "rtsp://camera:0/webcam",
        "rtsp://camera:65536/webcam",
        "rtsp://user:password@192.168.1.1/webcam",
        "rtsp://camera/webcam#fragment",
        "rtsp://camera/webcam#",
        "rtsp://camera name/webcam",
        "rtsp://camera/\nwebcam",
    ],
)
def test_rejects_invalid_rtsp_urls(url):
    with pytest.raises(ValueError):
        VideoConfig(url=url)


@pytest.mark.parametrize(
    "url",
    [
        "rtsp://192.168.1.1:7070/webcam",
        "rtsps://camera.example.com:322/stream",
        "rtsp://camera.example.com/stream",
    ],
)
def test_accepts_valid_rtsp_urls(url):
    assert VideoConfig(url=url).url == url


def test_rejects_non_string_url():
    with pytest.raises(ValueError):
        VideoConfig(url=None)


def test_open_capture_returns_capture_when_connection_succeeds(monkeypatch):
    capture = Mock()
    capture.isOpened.return_value = True
    video_capture = Mock(return_value=capture)

    monkeypatch.setattr(video_module.cv2, "VideoCapture", video_capture)

    config = VideoConfig()
    result = video_module.open_capture(config)

    expected_params = [
        video_module.cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
        config.open_timeout_ms,
        video_module.cv2.CAP_PROP_READ_TIMEOUT_MSEC,
        config.read_timeout_ms,
    ]

    video_capture.assert_called_once_with(
        config.url,
        video_module.cv2.CAP_FFMPEG,
        expected_params,
    )
    assert result is capture
    capture.release.assert_not_called()


def test_open_capture_releases_capture_when_connection_fails(monkeypatch):
    capture = Mock()
    capture.isOpened.return_value = False
    video_capture = Mock(return_value=capture)

    monkeypatch.setattr(video_module.cv2, "VideoCapture", video_capture)

    with pytest.raises(ConnectionError):
        video_module.open_capture(VideoConfig())

    capture.release.assert_called_once_with()


def test_iter_frames_returns_frames_with_monotonic_timestamps(monkeypatch):
    frame_one = object()
    frame_two = object()

    capture = Mock()
    capture.read.side_effect = [
        (True, frame_one),
        (True, frame_two),
        (False, None),
    ]

    timestamps = iter([10.0, 10.5])
    monkeypatch.setattr(video_module, "monotonic", lambda: next(timestamps))

    result = list(video_module.iter_frames(capture))

    assert len(result) == 2
    assert result[0] == (10.0, frame_one)
    assert result[1] == (10.5, frame_two)
    assert capture.read.call_count == 3


def test_ensure_parent_creates_output_directory(tmp_path):
    output = tmp_path / "recordings" / "capture.mp4"

    result = video_module.ensure_parent(str(output))

    assert result == output
    assert output.parent.exists()
    assert output.parent.is_dir()
