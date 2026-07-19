"""Frequency-domain measurement and reference-comparison algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .touchstone import NetworkData


class Metric(str, Enum):
    MAGNITUDE_DB = "Magnitude (dB)"
    LINEAR_MAGNITUDE = "Linear magnitude"
    PHASE_DEG = "Unwrapped phase (deg)"
    LINEAR_POWER = "Mean linear power"
    INTEGRATED_POWER = "Integrated linear power"
    GROUP_DELAY_NS = "Group delay (ns)"
    PEAK_DB = "Peak magnitude (dB)"
    NOTCH_DB = "Minimum magnitude (dB)"


class Comparison(str, Enum):
    ABSOLUTE = "Absolute measurement"
    DELTA_DB = "Reference delta (dB)"
    COMPLEX_RATIO_DB = "Complex ratio magnitude (dB)"
    PHASE_DELTA = "Reference phase delta (deg)"


@dataclass(frozen=True)
class AnalysisSettings:
    metric: Metric = Metric.MAGNITUDE_DB
    comparison: Comparison = Comparison.ABSOLUTE
    center_hz: float = 900e6
    bandwidth_hz: float = 0.0
    parameter: str = "S21"


def interpolate_complex(network: NetworkData, frequency_hz: np.ndarray, parameter: str) -> np.ndarray:
    source = network.parameter(parameter)
    real = np.interp(frequency_hz, network.frequency_hz, source.real)
    imag = np.interp(frequency_hz, network.frequency_hz, source.imag)
    return real + 1j * imag


def common_reference(reference_networks: list[NetworkData], target_frequency: np.ndarray, parameter: str) -> np.ndarray | None:
    if not reference_networks:
        return None
    arrays = [interpolate_complex(item, target_frequency, parameter) for item in reference_networks]
    return np.mean(np.stack(arrays), axis=0)


def analyze(network: NetworkData, settings: AnalysisSettings, reference_networks: list[NetworkData] | None = None) -> float:
    half = settings.bandwidth_hz / 2.0
    if settings.bandwidth_hz <= 0:
        frequency = np.asarray([settings.center_hz])
    else:
        mask = (network.frequency_hz >= settings.center_hz - half) & (network.frequency_hz <= settings.center_hz + half)
        frequency = network.frequency_hz[mask]
        if frequency.size == 0:
            frequency = np.asarray([settings.center_hz])
    if frequency.min() < network.frequency_hz.min() or frequency.max() > network.frequency_hz.max():
        return float("nan")
    values = interpolate_complex(network, frequency, settings.parameter)
    reference = common_reference(reference_networks or [], frequency, settings.parameter)
    if settings.comparison != Comparison.ABSOLUTE and reference is None:
        return float("nan")
    if settings.comparison in {Comparison.DELTA_DB, Comparison.COMPLEX_RATIO_DB}:
        values = values / np.where(np.abs(reference) > 1e-15, reference, np.nan)
    elif settings.comparison == Comparison.PHASE_DELTA:
        phase_delta = np.angle(values * np.conj(reference))
        return float(np.rad2deg(np.angle(np.mean(np.exp(1j * phase_delta)))))
    magnitude = np.abs(values)
    db = 20.0 * np.log10(np.maximum(magnitude, 1e-15))
    if settings.metric == Metric.MAGNITUDE_DB:
        return float(np.mean(db))
    if settings.metric == Metric.LINEAR_MAGNITUDE:
        return float(np.mean(magnitude))
    if settings.metric == Metric.PHASE_DEG:
        return float(np.mean(np.rad2deg(np.unwrap(np.angle(values)))))
    if settings.metric == Metric.LINEAR_POWER:
        return float(np.mean(np.square(magnitude)))
    if settings.metric == Metric.INTEGRATED_POWER:
        return float(np.trapezoid(np.square(magnitude), frequency)) if frequency.size > 1 else float(np.square(magnitude[0]))
    if settings.metric == Metric.GROUP_DELAY_NS:
        if frequency.size < 2:
            return float("nan")
        delay = -np.gradient(np.unwrap(np.angle(values)), 2.0 * np.pi * frequency)
        return float(np.mean(delay) * 1e9)
    if settings.metric == Metric.PEAK_DB:
        return float(np.max(db))
    if settings.metric == Metric.NOTCH_DB:
        return float(np.min(db))
    raise ValueError(settings.metric)

