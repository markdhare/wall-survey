"""NanoVNA-H/H4 ASCII-shell driver over USB CDC serial."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from time import sleep

import numpy as np
import serial
from serial.tools import list_ports

from wall_survey.touchstone import NetworkData
from .base import AcquisitionResult, ProgressCallback, SweepSettings, VnaDevice, VnaIdentity
from .quality import assess_capture


def discover_serial_ports() -> list[tuple[str, str]]:
    ports = []
    for item in sorted(list_ports.comports(), key=lambda value: value.device):
        description = item.description or "Serial port"
        likely = "NanoVNA" if item.vid == 0x0483 and item.pid == 0x5740 else description
        ports.append((item.device, f"{item.device} — {likely}"))
    return ports


class NanoVNAHDevice(VnaDevice):
    DRIVER_NAME = "nanovna_h_ascii"
    MAX_SEGMENT_POINTS = 101

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: serial.Serial | None = None
        self.identity: VnaIdentity | None = None
        self._lock = RLock()

    @property
    def connected(self) -> bool:
        return bool(self.serial and self.serial.is_open)

    def connect(self) -> VnaIdentity:
        with self._lock:
            if self.connected and self.identity: return self.identity
            self.serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout, write_timeout=2)
            try:
                self._drain(); self.serial.write(b"\r"); sleep(0.12)
                greeting = self.serial.read(256).decode("ascii", errors="replace")
                if "ch>" not in greeting:
                    raise ConnectionError(f"{self.port} did not respond like a NanoVNA-H")
                info = "\n".join(self._command("info"))
                firmware_lines = self._command("version")
                calibration = " ".join(self._command("cal")) or "unknown"
                model = "NanoVNA-H4" if "NanoVNA-H 4" in info else "NanoVNA-H"
                if "NanoVNA" not in info:
                    raise ConnectionError(f"Unsupported ASCII-shell device on {self.port}")
                self.identity = VnaIdentity(self.DRIVER_NAME, self.port, model, firmware_lines[0] if firmware_lines else "unknown", info, calibration)
                return self.identity
            except Exception:
                self.disconnect()
                raise

    def disconnect(self) -> None:
        with self._lock:
            if self.serial:
                if self.serial.is_open: self.serial.close()
                self.serial = None
            self.identity = None

    def _drain(self) -> None:
        assert self.serial is not None
        previous = self.serial.timeout; self.serial.timeout = 0.03
        try:
            while self.serial.read(256): pass
        finally:
            self.serial.timeout = previous

    def _command(self, command: str, timeout: float = 8.0) -> list[str]:
        if not self.connected: raise ConnectionError("NanoVNA is not connected")
        assert self.serial is not None
        self._drain(); self.serial.write((command + "\r").encode("ascii")); self.serial.flush()
        lines: list[str] = []; deadline = datetime.now().timestamp() + timeout
        while datetime.now().timestamp() < deadline:
            raw = self.serial.readline()
            if not raw: continue
            line = raw.decode("ascii", errors="replace").strip()
            if not line or line == command: continue
            if line.startswith("ch>"): return lines
            lines.append(line)
        raise TimeoutError(f"NanoVNA command timed out: {command}")

    @staticmethod
    def _segments(settings: SweepSettings) -> list[tuple[int, int, int]]:
        if settings.points % NanoVNAHDevice.MAX_SEGMENT_POINTS:
            raise ValueError("NanoVNA-H total points must be a multiple of 101")
        target = np.rint(np.linspace(settings.start_hz, settings.stop_hz, settings.points)).astype(np.int64)
        count = settings.points // NanoVNAHDevice.MAX_SEGMENT_POINTS
        chunks = np.array_split(target, count)
        return [(int(chunk[0]), int(chunk[-1]), len(chunk)) for chunk in chunks]

    def _read_complex(self, command: str, expected: int) -> np.ndarray:
        lines = self._command(command, timeout=max(8.0, expected * 0.12))
        try: values = np.asarray([complex(*map(float, line.split()[:2])) for line in lines], dtype=complex)
        except (TypeError, ValueError) as exc: raise IOError(f"Invalid response to {command}") from exc
        if values.size != expected: raise IOError(f"{command} returned {values.size} points; expected {expected}")
        return values

    def acquire(self, settings: SweepSettings, progress: ProgressCallback | None = None) -> AcquisitionResult:
        settings.validate()
        if not self.connected or not self.identity: raise ConnectionError("NanoVNA is not connected")
        segments = self._segments(settings); total = len(segments) * settings.averages; completed = 0
        all_frequency: list[np.ndarray] = []; all_s11: list[np.ndarray] = []; all_s21: list[np.ndarray] = []
        with self._lock:
            try:
                for segment_number, (start, stop, points) in enumerate(segments, 1):
                    s11_repeats, s21_repeats = [], []
                    segment_frequency = None
                    for average in range(settings.averages):
                        self._command(f"sweep {start} {stop} {points}")
                        self._command("resume")
                        sleep(max(1.6, points * 0.016))
                        self._command("pause")
                        frequency_lines = self._command("frequencies", timeout=max(8.0, points * 0.12))
                        try: current_frequency = np.asarray([float(line.split()[0]) for line in frequency_lines])
                        except (ValueError, IndexError) as exc: raise IOError("Invalid frequency response from NanoVNA") from exc
                        if current_frequency.size != points: raise IOError(f"NanoVNA returned {current_frequency.size} frequencies; expected {points}")
                        segment_frequency = current_frequency
                        s11_repeats.append(self._read_complex("data 0", points)); s21_repeats.append(self._read_complex("data 1", points))
                        completed += 1
                        if progress: progress(completed, total, f"Segment {segment_number}/{len(segments)}, average {average + 1}/{settings.averages}")
                    assert segment_frequency is not None
                    all_frequency.append(segment_frequency); all_s11.append(np.mean(s11_repeats, axis=0)); all_s21.append(np.mean(s21_repeats, axis=0))
            finally:
                try: self._command("resume")
                except Exception: pass
        frequency = np.concatenate(all_frequency); order = np.argsort(frequency)
        s11, s21 = np.concatenate(all_s11)[order], np.concatenate(all_s21)[order]; frequency = frequency[order]
        s = np.zeros((frequency.size, 2, 2), dtype=complex); s[:, 0, 0] = s11; s[:, 1, 0] = s21
        network = NetworkData(Path("direct_capture.s2p"), frequency, s)
        result = AcquisitionResult(network, self.identity, settings, datetime.now(timezone.utc))
        result.quality_flags = assess_capture(network)
        return result
