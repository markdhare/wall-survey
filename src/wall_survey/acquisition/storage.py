"""Crash-resistant raw Touchstone and consolidated YAML capture logging."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import re

import yaml

from .base import AcquisitionResult


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    return cleaned or "capture"


def write_touchstone(result: AcquisitionResult, path: Path) -> None:
    network = result.network
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="ascii", newline="\n") as handle:
        handle.write("! Wall Survey direct NanoVNA acquisition\n")
        handle.write(f"! acquired_at: {result.acquired_at.isoformat()}\n")
        handle.write(f"! device: {result.identity.model} {result.identity.firmware}\n")
        handle.write("# HZ S RI R 50\n")
        for index, frequency in enumerate(network.frequency_hz):
            terms = []
            # Touchstone order: S11, S21, S12, S22.
            for output, input_ in ((0, 0), (1, 0), (0, 1), (1, 1)):
                value = network.s[index, output, input_]
                terms.extend((value.real, value.imag))
            handle.write(f"{frequency:.0f} " + " ".join(f"{value:.12g}" for value in terms) + "\n")
    temporary.replace(path)


def save_capture(result: AcquisitionResult, directory: str | Path, label: str, destination: str) -> Path:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    stamp = result.acquired_at.strftime("%Y%m%dT%H%M%S_%f")[:-3]
    path = root / f"{stamp}_{_safe_name(label)}.s2p"
    counter = 2
    while path.exists():
        path = root / f"{stamp}_{_safe_name(label)}_{counter}.s2p"
        counter += 1
    write_touchstone(result, path)
    log_path = root / "capture_log.yaml"
    payload = {"format_version": 1, "captures": []}
    if log_path.exists():
        loaded = yaml.safe_load(log_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("captures"), list): payload = loaded
    payload["captures"].append({
        "file": path.name,
        "label": label,
        "destination": destination,
        "acquired_at": result.acquired_at.isoformat(),
        "device": asdict(result.identity),
        "sweep": asdict(result.settings),
        "quality_flags": list(result.quality_flags),
    })
    temporary = log_path.with_suffix(".yaml.tmp")
    temporary.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    temporary.replace(log_path)
    return path
