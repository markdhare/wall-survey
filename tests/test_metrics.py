from pathlib import Path
import numpy as np
from wall_survey.metrics import AnalysisSettings, Comparison, Metric, analyze, trace_series
from wall_survey.touchstone import read_touchstone

EXAMPLES = Path(__file__).parents[1] / "example_s2p_files"


def test_reference_delta_of_itself_is_zero():
    network = read_touchstone(EXAMPLES / "example_baseline.s2p")
    settings = AnalysisSettings(Metric.MAGNITUDE_DB, Comparison.DELTA_DB, 900e6, 10e6)
    assert abs(analyze(network, settings, [network])) < 1e-10


def test_integrated_power_is_positive():
    network = read_touchstone(EXAMPLES / "example_baseline.s2p")
    settings = AnalysisSettings(Metric.INTEGRATED_POWER, center_hz=900e6, bandwidth_hz=100e6)
    assert np.isfinite(analyze(network, settings)) and analyze(network, settings) > 0


def test_trace_series_reflects_reference_delta():
    baseline = read_touchstone(EXAMPLES / "example_baseline.s2p")
    obstacle = read_touchstone(EXAMPLES / "example_with_obstacle.s2p")
    settings = AnalysisSettings(Metric.MAGNITUDE_DB, Comparison.DELTA_DB, 900e6, 10e6)
    series = trace_series(obstacle, settings, [baseline])
    point = np.argmin(np.abs(series.frequency_hz - 900e6))
    expected = 20 * np.log10(abs(obstacle.parameter("S21")[point] / baseline.parameter("S21")[point]))
    assert np.isclose(series.values[point], expected)
    assert series.axis_label == "Magnitude delta from baseline"
