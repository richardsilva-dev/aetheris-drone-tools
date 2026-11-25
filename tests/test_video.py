import pytest

from aetheris_drone.video import VideoConfig, estimate_fps


def test_default_url_is_the_verified_rtsp_endpoint():
    assert VideoConfig().url == "rtsp://192.168.1.1:7070/webcam"


def test_rejects_non_rtsp_url():
    with pytest.raises(ValueError):
        VideoConfig(url="http://192.168.1.1/video")


def test_rejects_non_positive_timeout():
    with pytest.raises(ValueError):
        VideoConfig(open_timeout_ms=0)


def test_estimates_fps_from_monotonic_timestamps():
    assert estimate_fps([1.0, 1.1, 1.2, 1.3]) == pytest.approx(10.0)


def test_fps_requires_two_timestamps():
    assert estimate_fps([1.0]) == 0.0


def test_fps_handles_non_positive_elapsed_time():
    assert estimate_fps([2.0, 2.0]) == 0.0
