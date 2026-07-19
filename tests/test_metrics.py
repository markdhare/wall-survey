from pathlib import Path
import numpy as np
from wall_survey.metrics import AnalysisSettings, Comparison, Metric, analyze
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

