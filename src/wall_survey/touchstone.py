"""Small, strict Touchstone 1.x reader with S1P/S2P support."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np


_UNITS = {"hz": 1.0, "khz": 1e3, "mhz": 1e6, "ghz": 1e9}


@dataclass(frozen=True)
class NetworkData:
    path: Path
    frequency_hz: np.ndarray
    s: np.ndarray  # shape: (frequency, ports, ports)
    reference_ohms: float = 50.0

    @property
    def ports(self) -> int:
        return self.s.shape[1]

    def parameter(self, name: str = "S21") -> np.ndarray:
        match = re.fullmatch(r"S([1-9])([1-9])", name.upper())
        if not match:
            raise ValueError(f"Invalid scattering parameter: {name}")
        output_port, input_port = (int(x) - 1 for x in match.groups())
        if max(output_port, input_port) >= self.ports:
            raise ValueError(f"{name} is unavailable in a {self.ports}-port file")
        return self.s[:, output_port, input_port]


def read_touchstone(path: str | Path) -> NetworkData:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in {".s1p", ".s2p"}:
        raise ValueError(f"Only .s1p and .s2p files are supported, not {suffix or 'no extension'}")
    ports = int(suffix[2])
    option = None
    values: list[float] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.split("!", 1)[0].strip()
            if not line:
                continue
            if line.startswith("["):
                raise ValueError(f"Touchstone 2.0 sections are not yet supported ({path}:{line_number})")
            if line.startswith("#"):
                fields = line[1:].lower().split()
                if len(fields) < 3 or fields[1] != "s":
                    raise ValueError(f"Unsupported Touchstone option line: {line}")
                unit, data_format = fields[0], fields[2]
                if unit not in _UNITS or data_format not in {"ri", "ma", "db"}:
                    raise ValueError(f"Unsupported unit or data format: {line}")
                reference = 50.0
                if "r" in fields:
                    reference = float(fields[fields.index("r") + 1])
                option = (unit, data_format, reference)
                continue
            try:
                values.extend(float(token) for token in line.split())
            except ValueError as exc:
                raise ValueError(f"Non-numeric data at {path}:{line_number}") from exc
    if option is None:
        option = ("ghz", "ma", 50.0)  # Touchstone defaults
    width = 1 + 2 * ports * ports
    if len(values) % width:
        raise ValueError(f"Incomplete record in {path}; expected groups of {width} values")
    raw = np.asarray(values, dtype=float).reshape(-1, width)
    frequency = raw[:, 0] * _UNITS[option[0]]
    pairs = raw[:, 1:].reshape(-1, ports * ports, 2)
    a, b = pairs[..., 0], pairs[..., 1]
    if option[1] == "ri":
        complex_values = a + 1j * b
    else:
        magnitude = a if option[1] == "ma" else np.power(10.0, a / 20.0)
        complex_values = magnitude * np.exp(1j * np.deg2rad(b))
    # Touchstone stores S11, S21, S12, S22 (columns by input port).
    s = complex_values.reshape(-1, ports, ports, order="F")
    order = np.argsort(frequency)
    return NetworkData(path, frequency[order], s[order], option[2])

