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

This split is the extension seam for acquisition hardware, automated naming, interpolation methods, or S11 analysis. Keep device I/O and GUI concerns out of the numerical modules.

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

### Direct NanoVNA acquisition

Define an acquisition protocol returning a file-backed `Run`. A serial NanoVNA implementation should enumerate devices, read and display sweep/calibration state, acquire all complex points, write a standards-compliant raw Touchstone file, and only then add it to the model. NanoVNA-Saver automation is another possible adapter, but tight GUI automation is more brittle than using the serial protocol or a supported API.

### Continuous heatmaps

The present map overlays measured dots on an inverse-distance-weighted field for irregular samples. A future interpolation layer can offer nearest-neighbor and linear triangulation, convex-hull masking, configurable IDW power, and persisted interpolation settings. Always preserve measured dots over any interpolated field.

### Classification

Multi-reference material classification can compare each test spectrum with each reference using complex distance, weighted band features, or a trained model. Report distances/confidence and retain raw feature values; do not collapse an RF anomaly into an unqualified material assertion.

## Release and compatibility policy

Python 3.11 or newer is declared; the lockfile captures tested dependencies. Project format changes require a new integer `format_version` and a migration path. Never alter copied source Touchstone files. Keep metadata in the one project YAML unless a new document has a clear independent lifecycle.
