from pathlib import Path
import numpy as np
from wall_survey.touchstone import read_touchstone

EXAMPLES = Path(__file__).parents[1] / "example_s2p_files"


def test_reads_nanovna_saver_ri_file():
    network = read_touchstone(EXAMPLES / "example_baseline.s2p")
    assert network.ports == 2
    assert network.frequency_hz[0] == 500e6
    assert network.frequency_hz[-1] > 1e9
    assert len(network.frequency_hz) == 1010
    assert np.isclose(network.parameter("S21")[0], -0.11162424033333332 + 0.04850741066666667j)


def test_obstacle_is_measurably_different():
    baseline = read_touchstone(EXAMPLES / "example_baseline.s2p")
    obstacle = read_touchstone(EXAMPLES / "example_with_obstacle.s2p")
    difference = np.mean(np.abs(baseline.parameter("S21") - obstacle.parameter("S21")))
    assert difference > 0.01
