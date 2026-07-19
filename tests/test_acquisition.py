from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

from wall_survey.acquisition.base import AcquisitionResult, SweepSettings, VnaIdentity
from wall_survey.acquisition.nanovna_h import NanoVNAHDevice
from wall_survey.acquisition.quality import assess_capture
from wall_survey.acquisition.storage import save_capture
from wall_survey.touchstone import NetworkData, read_touchstone


def network(values: np.ndarray) -> NetworkData:
    frequency = np.linspace(500e6, 1.5e9, values.size)
    s = np.zeros((values.size, 2, 2), dtype=complex)
    s[:, 1, 0] = values
    return NetworkData(Path("capture.s2p"), frequency, s)


def test_segment_plan_preserves_requested_total_and_span():
    segments = NanoVNAHDevice._segments(SweepSettings(points=303))
    assert sum(points for _, _, points in segments) == 303
    assert all(points == 101 for _, _, points in segments)
    assert segments[0][0] == 500_000_000
    assert segments[-1][1] == 1_500_000_000


def test_segment_plan_rejects_total_device_cannot_honor():
    try:
        NanoVNAHDevice._segments(SweepSettings(points=201))
    except ValueError as exc:
        assert "multiple of 101" in str(exc)
    else:
        raise AssertionError("Expected invalid NanoVNA-H point total to be rejected")


def test_quality_flags_constant_zero_capture():
    flags = assess_capture(network(np.zeros(101, dtype=complex)))
    assert any("zero" in flag for flag in flags)
    assert any("identical" in flag for flag in flags)


def test_capture_is_written_before_yaml_log_and_round_trips(tmp_path):
    values = np.linspace(0.01, 0.2, 101) * np.exp(1j * np.linspace(0, 2, 101))
    result = AcquisitionResult(
        network(values),
        VnaIdentity("test", "COM10", "NanoVNA-H", "test-fw", "test"),
        SweepSettings(points=101, averages=2),
        datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
    )
    path = save_capture(result, tmp_path, "Known wall / repeat 1", "Run Lab")
    restored = read_touchstone(path)
    log = yaml.safe_load((tmp_path / "capture_log.yaml").read_text(encoding="utf-8"))
    assert np.allclose(restored.parameter("S21"), values)
    assert log["captures"][0]["file"] == path.name
    assert log["captures"][0]["sweep"]["averages"] == 2
    second = save_capture(result, tmp_path, "Known wall / repeat 1", "Run Lab")
    assert second != path
    assert path.exists() and second.exists()
