"""Protocol-neutral contracts for present and future VNA drivers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from wall_survey.touchstone import NetworkData


@dataclass(frozen=True)
class SweepSettings:
    start_hz: int = 500_000_000
    stop_hz: int = 1_500_000_000
    points: int = 101
    averages: int = 1

    def validate(self) -> None:
        if self.start_hz <= 0 or self.stop_hz <= self.start_hz:
            raise ValueError("Sweep stop must be greater than a positive start frequency")
        if self.points < 11:
            raise ValueError("A sweep requires at least 11 points")
        if self.averages < 1:
            raise ValueError("Averages must be at least 1")


@dataclass(frozen=True)
class VnaIdentity:
    driver: str
    port: str
    model: str
    firmware: str
    info: str
    calibration: str = "unknown"


@dataclass
class AcquisitionResult:
    network: NetworkData
    identity: VnaIdentity
    settings: SweepSettings
    acquired_at: datetime
    quality_flags: list[str] = field(default_factory=list)


ProgressCallback = Callable[[int, int, str], None]


class VnaDevice(ABC):
    """Stable boundary implemented separately for each hardware protocol."""

    @abstractmethod
    def connect(self) -> VnaIdentity: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @property
    @abstractmethod
    def connected(self) -> bool: ...

    @abstractmethod
    def acquire(self, settings: SweepSettings, progress: ProgressCallback | None = None) -> AcquisitionResult: ...

