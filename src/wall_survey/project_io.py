"""Portable ZIP/YAML project persistence."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import shutil
import tempfile
import zipfile

import yaml

from .model import Location, Reference, Run, SurveyProject


FORMAT_VERSION = 1


def _run_dict(run: Run, archive_name: str) -> dict:
    return {"id": run.id, "label": run.label, "source": archive_name, "notes": run.notes}


def save_project(project: SurveyProject, destination: str | Path) -> Path:
    destination = Path(destination).with_suffix(".wallscan")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_name:
        root = Path(temp_name)
        data_dir = root / "data"
        data_dir.mkdir()
        used: set[str] = set()

        def archive_run(run: Run) -> dict:
            source = Path(run.source)
            stem = f"{run.id}_{source.name}"
            name = stem
            counter = 2
            while name.lower() in used:
                name = f"{run.id}_{counter}_{source.name}"
                counter += 1
            used.add(name.lower())
            shutil.copy2(source, data_dir / name)
            return _run_dict(run, f"data/{name}")

        payload = {
            "format_version": FORMAT_VERSION,
            "project": {"name": project.name, "description": project.description, "parameter": project.parameter, "view": project.view, "active_reference_id": project.active_reference_id},
            "references": [{"id": ref.id, "name": ref.name, "material": ref.material, "runs": [archive_run(run) for run in ref.runs]} for ref in project.references],
            "locations": [{"id": loc.id, "label": loc.label, "x_m": loc.x_m, "y_m": loc.y_m, "row": loc.row, "column": loc.column, "runs": [archive_run(run) for run in loc.runs]} for loc in project.locations],
        }
        (root / "project.yaml").write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
        temporary.replace(destination)
    project.project_path = destination
    return destination


def load_project(source: str | Path, extraction_root: str | Path | None = None) -> SurveyProject:
    source = Path(source)
    extraction_root = Path(extraction_root) if extraction_root else Path(tempfile.mkdtemp(prefix="wall_survey_"))
    with zipfile.ZipFile(source) as archive:
        if "project.yaml" not in archive.namelist() or any(Path(name).is_absolute() or ".." in Path(name).parts for name in archive.namelist()):
            raise ValueError("Invalid or unsafe Wall Survey archive")
        archive.extractall(extraction_root)
    payload = yaml.safe_load((extraction_root / "project.yaml").read_text(encoding="utf-8"))
    if payload.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"Unsupported project format version: {payload.get('format_version')}")

    def run(item: dict) -> Run:
        return Run(item["id"], item.get("label", ""), str(extraction_root / item["source"]), item.get("notes", ""))

    meta = payload["project"]
    project = SurveyProject(meta["name"], meta.get("description", ""), meta.get("parameter", "S21"), meta.get("view", "front"))
    project.active_reference_id = meta.get("active_reference_id")
    project.references = [Reference(item["id"], item["name"], item.get("material", ""), [run(value) for value in item.get("runs", [])]) for item in payload.get("references", [])]
    project.locations = [Location(item["id"], item.get("label", ""), float(item["x_m"]), float(item["y_m"]), item.get("row"), item.get("column"), [run(value) for value in item.get("runs", [])]) for item in payload.get("locations", [])]
    project.project_path = source
    return project

