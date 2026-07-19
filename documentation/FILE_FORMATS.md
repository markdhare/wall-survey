# File Formats

## Input Touchstone

Supported inputs are Touchstone 1.x `.s2p` and `.s1p` files containing S-parameters in RI (real/imaginary), MA (linear magnitude/angle degrees), or DB (decibels/angle degrees) format, with Hz, kHz, MHz, or GHz units. The reader honors the reference impedance and Touchstone default option line (`GHz S MA R 50`) when none is present.

For a two-port file, the standard record order is frequency, S11, S21, S12, S22. Continuation lines and `!` comments are accepted. Touchstone 2.0 bracketed sections and noise records are rejected explicitly rather than guessed. S1P support enables future S11 reflection surveys; the application project parameter must then be `S11`.

## Portable `.wallscan` project

A `.wallscan` file is a ZIP archive. It contains a single metadata document and immutable copies of all raw inputs:

```text
project.yaml
data/
  <run-id>_<original-name>.s2p
  ...
```

`project.yaml` is UTF-8 YAML with this version-1 shape:

```yaml
format_version: 1
project:
  name: West wall
  description: Optional notes
  parameter: S21
  view: front
  active_reference_id: abc123
references:
  - id: abc123
    name: Free space
    material: 18 cm antenna separation
    runs:
      - id: run001
        label: baseline_before
        source: data/run001_baseline_before.s2p
        notes: ''
locations:
  - id: point01
    label: R1C1
    x_m: 0.0
    y_m: 0.0
    row: 1
    column: 1
    runs: []
loose_runs:
  - id: exploratory01
    label: known_void
    source: data/exploratory01_known_void.s2p
    notes: Off-grid comparison run
```

All coordinates are SI metres. IDs are opaque and stable within a project. `source` is always relative to the archive root. The loader rejects absolute paths and parent traversal. Saving writes a temporary archive and replaces the destination only after completion. Extracted working copies live in a temporary directory; saving repackages them.

YAML is used for all editable metadata. Raw RF data remains Touchstone and reports remain CSV/PNG, avoiding redundant sidecar files.

## Direct-acquisition log

Every raw capture directory contains one `capture_log.yaml` rather than one metadata sidecar per S2P file. It uses `format_version: 1` and a `captures` list. Each entry records the relative raw filename, label, intended destination, UTC acquisition time, device identity and calibration report, sweep settings, and any quality warnings. The S2P file is written atomically before the log is updated, so a raw sweep survives even if logging or project routing is interrupted.

## CSV result export

CSV columns are `location`, `x_m`, `y_m`, `repeat_count`, `mean`, `standard_deviation`, `metric`, `comparison`, `center_hz`, `bandwidth_hz`, and `reference`. Values are recalculated from raw runs at export time. Missing/undefined numeric values use the platform CSV representation of NaN.
