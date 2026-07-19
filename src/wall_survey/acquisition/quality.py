"""Conservative capture sanity checks; warnings are not data rejection."""

from __future__ import annotations

import numpy as np

from wall_survey.touchstone import NetworkData


def assess_capture(network: NetworkData, parameter: str = "S21") -> list[str]:
    flags: list[str] = []
    frequency = network.frequency_hz
    values = network.parameter(parameter)
    if frequency.size < 11:
        flags.append("Very few frequency points were captured.")
    if not np.all(np.isfinite(frequency)) or not np.all(np.isfinite(values)):
        flags.append("Capture contains non-finite values.")
        return flags
    if np.any(np.diff(frequency) <= 0):
        flags.append("Frequencies are duplicated or not increasing.")
    magnitude = np.abs(values)
    if np.max(magnitude) < 1e-12:
        flags.append("S21 is effectively zero at every point.")
    if np.ptp(values.real) < 1e-10 and np.ptp(values.imag) < 1e-10:
        flags.append("S21 is nearly identical at every frequency.")
    if np.count_nonzero(magnitude > 2.0) > max(3, magnitude.size // 20):
        flags.append("Many |S21| values exceed 2; check calibration and connections.")
    if np.count_nonzero(magnitude <= 1e-15) > magnitude.size // 2:
        flags.append("More than half of S21 values are at the numerical floor.")
    return flags

