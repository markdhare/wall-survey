"""Domain model for references, survey locations, and repeated runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


def new_id() -> str:
    return uuid4().hex[:12]


@dataclass
class Run:
    id: str = field(default_factory=new_id)
    label: str = ""
    source: str = ""
    notes: str = ""


@dataclass
class Reference:
    id: str = field(default_factory=new_id)
    name: str = "Reference"
    material: str = ""
    runs: list[Run] = field(default_factory=list)


@dataclass
class Location:
    id: str = field(default_factory=new_id)
    label: str = ""
    x_m: float = 0.0
    y_m: float = 0.0
    row: int | None = None
    column: int | None = None
    runs: list[Run] = field(default_factory=list)


@dataclass
class SurveyProject:
    name: str = "Untitled wall survey"
    description: str = ""
    parameter: str = "S21"
    view: str = "front"
    references: list[Reference] = field(default_factory=list)
    locations: list[Location] = field(default_factory=list)
    loose_runs: list[Run] = field(default_factory=list)
    active_reference_id: str | None = None
    project_path: Path | None = field(default=None, repr=False, compare=False)

    def reference(self, reference_id: str | None) -> Reference | None:
        return next((item for item in self.references if item.id == reference_id), None)
