# Developer Guide

## Architecture and data flow

```text
Touchstone files -> strict parser -> NetworkData (NumPy complex arrays)
                                      |
YAML project -> domain model ---------+-> metric engine -> repeat statistics
                                                              |
                                      PySide6 tables / pyqtgraph plots / exports
```

The package uses a `src` layout:

- `touchstone.py` parses raw S1P/S2P into frequencies and a complex `(frequency, output port, input port)` matrix.
- `model.py` defines projects, reference conditions, spatial locations, and off-grid Run Lab runs. The model has no Qt dependency.
- `metrics.py` handles complex interpolation, reference aggregation, frequency windows, and scalar metrics.
- `project_io.py` serializes the model to a safe portable archive.
- `ui.py` owns interaction, repeat aggregation, table rendering, traces, and the spatial scatter map.
- `app.py` is the console entry point.
- `acquisition/base.py` defines the protocol-neutral `VnaDevice`, identity, settings, and result contracts.
- `acquisition/nanovna_h.py` implements the NanoVNA-H/H4 ASCII serial protocol and segmented complex averaging.
- `acquisition/storage.py` writes raw S2P before updating the consolidated YAML capture log.
- `acquisition/quality.py` supplies non-destructive sanity warnings.
- `acquisition_ui.py` provides threaded connection/capture workers and the persistent routing dock.

This split is the extension seam for acquisition hardware, automated naming, interpolation methods, or S11 analysis. Keep device I/O and GUI concerns out of the numerical modules.

### Acquisition boundary

New hardware families implement `VnaDevice` without leaking protocol details into Qt or the project model. A future NanoVNA V2 adapter should implement its binary register/FIFO protocol in a separate module and return the same `AcquisitionResult`. UI capture work runs through `QThreadPool`; the raw file is saved in the worker before `capture_ready` is emitted to the main window for routing.

The NanoVNA-H driver uses contiguous 101-point segments, matching the tested firmware and NanoVNA-Saver convention; unsupported nearby point counts can otherwise be silently changed by the device. It controls each sweep, waits for acquisition, pauses before reading `frequencies`, `data 0`, and `data 1`, complex-averages repeats, and resumes in a `finally` block. S11 and S21 occupy their standard two-port matrix positions; unmeasured reverse terms remain zero. Serial access is guarded by a reentrant lock.

## Numerical conventions

Touchstone two-port ordering is column-major by stimulus: S11, S21, S12, S22. The parser reshapes with Fortran order so `s[:, output, input]` is correct. Frequencies are sorted ascending.

Complex interpolation linearly interpolates real and imaginary components. This avoids discontinuities at ±180 degrees and is appropriate for narrow gaps in a dense sweep. Reference interpolation is masked outside each reference's measured span; scalar analysis and trace display use only the common finite overlap and never extrapolate reference values.

For a band, the engine selects native sample frequencies within `[center - bandwidth/2, center + bandwidth/2]`. A point request interpolates exactly at the center. Reference repeats are independently interpolated and complex-averaged. Test repeats are not complex-averaged: each becomes a scalar result so experimental spread remains visible.

`trace_series` applies the same comparison semantics as `analyze` across a complete sweep and returns an axis label and unit with the graph-ready values. The UI must use this function rather than independently recreating RF transformations. Its non-movable `InfiniteLine` or `LinearRegionItem` shows the frequency selection reduced by `analyze`.

Loose runs use the same `Run` object but are owned by `SurveyProject.loose_runs`. They can act as a one-run analysis baseline without duplication: the UI baseline selector resolves either a reference-group ID or a loose-run ID into a list of networks.

Group delay uses numerical differentiation of unwrapped phase against angular frequency. It is noise-sensitive, so users should select a meaningful bandwidth. Integrated power uses trapezoidal integration. Phase differences use a circular mean.

## Development commands

```powershell
uv sync --extra dev
uv run pytest
uv run pytest --cov=wall_survey --cov-report=html
uv run wall-survey
```

For an offscreen UI construction smoke test:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
uv run python -c "from PySide6.QtWidgets import QApplication; from wall_survey.ui import MainWindow; app=QApplication([]); window=MainWindow(); print(window.windowTitle())"
```

Tests exercise the real NanoVNA-Saver examples, numerical reference behavior, and archive round trips. Add focused synthetic files for MA/DB/S1P edge cases when those workflows become active.

## Planned extension points

### Filename-assisted placement

Add a preview-stage importer that applies a user-editable regular expression, displays every parsed coordinate before mutation, and records the selected naming rule in project YAML. Never silently infer coordinates.

### NanoVNA V2 acquisition

The current ASCII-shell driver is limited deliberately to NanoVNA-H/H4. A NanoVNA V2 implementation should live beside it and implement the binary register/FIFO protocol behind `VnaDevice`. Device-family detection belongs in a driver registry or factory; it must not add V2-specific branches to project routing, raw preservation, or analysis code. Hardware-specific sweep constraints should remain in the driver and be surfaced clearly by the acquisition panel.

### Continuous heatmaps

The present map overlays measured dots on an inverse-distance-weighted field for irregular samples. A future interpolation layer can offer nearest-neighbor and linear triangulation, convex-hull masking, configurable IDW power, and persisted interpolation settings. Always preserve measured dots over any interpolated field.

### Classification

Multi-reference material classification can compare each test spectrum with each reference using complex distance, weighted band features, or a trained model. Report distances/confidence and retain raw feature values; do not collapse an RF anomaly into an unqualified material assertion.

## Release and compatibility policy

Python 3.11 or newer is declared; the lockfile captures tested dependencies. Project format changes require a new integer `format_version` and a migration path. Never alter copied source Touchstone files. Keep metadata in the one project YAML unless a new document has a clear independent lifecycle.
