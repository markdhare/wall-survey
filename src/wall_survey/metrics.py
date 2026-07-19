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


@dataclass(frozen=True)
class TraceSeries:
    """A graph-ready series using the same semantics as scalar analysis."""

    frequency_hz: np.ndarray
    values: np.ndarray
    axis_label: str
    units: str = ""


def interpolate_complex(network: NetworkData, frequency_hz: np.ndarray, parameter: str) -> np.ndarray:
    source = network.parameter(parameter)
    real = np.interp(frequency_hz, network.frequency_hz, source.real)
    imag = np.interp(frequency_hz, network.frequency_hz, source.imag)
    return real + 1j * imag


def common_reference(reference_networks: list[NetworkData], target_frequency: np.ndarray, parameter: str) -> np.ndarray | None:
    if not reference_networks:
        return None
    arrays = []
    for item in reference_networks:
        values = interpolate_complex(item, target_frequency, parameter)
        outside = (target_frequency < item.frequency_hz.min()) | (target_frequency > item.frequency_hz.max())
        values[outside] = np.nan + 1j * np.nan
        arrays.append(values)
    return np.mean(np.stack(arrays), axis=0)


def _compared_values(
    network: NetworkData,
    settings: AnalysisSettings,
    frequency: np.ndarray,
    reference_networks: list[NetworkData] | None,
) -> tuple[np.ndarray, np.ndarray | None]:
    values = interpolate_complex(network, frequency, settings.parameter)
    reference = common_reference(reference_networks or [], frequency, settings.parameter)
    if settings.comparison == Comparison.ABSOLUTE:
        return values, reference
    if reference is None:
        return np.full(values.shape, np.nan + 1j * np.nan), None
    if settings.comparison in {Comparison.DELTA_DB, Comparison.COMPLEX_RATIO_DB}:
        return values / np.where(np.abs(reference) > 1e-15, reference, np.nan), reference
    return values * np.conj(reference), reference


def trace_series(
    network: NetworkData,
    settings: AnalysisSettings,
    reference_networks: list[NetworkData] | None = None,
) -> TraceSeries:
    """Return a full-sweep curve matching the active metric/comparison controls."""

    frequency = network.frequency_hz.copy()
    values, reference = _compared_values(network, settings, frequency, reference_networks)
    finite = np.isfinite(values.real) & np.isfinite(values.imag)
    frequency, values = frequency[finite], values[finite]
    magnitude = np.abs(values)
    db = 20.0 * np.log10(np.maximum(magnitude, 1e-15))
    if settings.comparison == Comparison.DELTA_DB:
        return TraceSeries(frequency, db, "Magnitude delta from baseline", "dB")
    if settings.comparison == Comparison.PHASE_DELTA:
        phase = np.rad2deg(np.angle(values))
        return TraceSeries(frequency, phase, "Phase delta from baseline", "deg")
    if settings.metric == Metric.MAGNITUDE_DB:
        return TraceSeries(frequency, db, "Magnitude" if reference is None else "Normalized magnitude", "dB")
    if settings.metric == Metric.LINEAR_MAGNITUDE:
        return TraceSeries(frequency, magnitude, "Linear magnitude" if reference is None else "Normalized linear magnitude")
    if settings.metric == Metric.PHASE_DEG:
        return TraceSeries(frequency, np.rad2deg(np.unwrap(np.angle(values))), "Unwrapped phase", "deg")
    if settings.metric in {Metric.LINEAR_POWER, Metric.INTEGRATED_POWER}:
        label = "Linear power" if settings.metric == Metric.LINEAR_POWER else "Linear power (integrand)"
        return TraceSeries(frequency, np.square(magnitude), label)
    if settings.metric == Metric.GROUP_DELAY_NS:
        if frequency.size < 2:
            return TraceSeries(frequency, np.full(frequency.shape, np.nan), "Group delay", "ns")
        phase = np.unwrap(np.angle(values))
        delay = -np.gradient(phase, 2.0 * np.pi * frequency) * 1e9
        return TraceSeries(frequency, delay, "Group delay", "ns")
    if settings.metric in {Metric.PEAK_DB, Metric.NOTCH_DB}:
        return TraceSeries(frequency, db, "Magnitude", "dB")
    raise ValueError(settings.metric)


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
    values, reference = _compared_values(network, settings, frequency, reference_networks)
    if settings.comparison != Comparison.ABSOLUTE and reference is None:
        return float("nan")
    finite = np.isfinite(values.real) & np.isfinite(values.imag)
    frequency, values = frequency[finite], values[finite]
    if not frequency.size:
        return float("nan")
    if settings.comparison == Comparison.PHASE_DELTA:
        phase_delta = np.angle(values)
        return float(np.rad2deg(np.angle(np.mean(np.exp(1j * phase_delta)))))
    magnitude = np.abs(values)
    db = 20.0 * np.log10(np.maximum(magnitude, 1e-15))
    if settings.comparison == Comparison.DELTA_DB:
        return float(np.mean(db))
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
