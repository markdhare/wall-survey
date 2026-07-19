# Release Notes

## Version 0.2.0 — Built-in NanoVNA-H acquisition

This is the first acquisition-enabled milestone. It builds on the known-good `baseline-pre-nanovna` tag while retaining the original Touchstone import workflow.

### Acquisition

- Added serial-port discovery and direct NanoVNA-H/H4 ASCII-shell connection.
- Added application-controlled start/stop frequency, totals in 101-point hardware segments, and complex averaging.
- Added threaded capture so the Qt interface remains responsive.
- Added immediate atomic S2P preservation followed by a consolidated YAML capture log.
- Added model, firmware, and instrument-calibration status display without changing calibration state.
- Added conservative, non-destructive quality warnings for clearly implausible data.

### Routing and workflow

- Added capture routing to Run Lab, new/existing references, new/existing map locations, and the next empty grid location.
- Added guided grid progression with an operator-controlled manual Capture button.
- Added **Map selected runs** so reviewed Run Lab measurements can be moved to new or existing wall coordinates without changing their source data.
- Added fallback to Run Lab when a post-capture destination cannot be completed.

### Documentation and validation

- Added a direct-acquisition operations guide and a complete first-time survey tutorial.
- Updated user, developer, file-format, README, and article documentation for the acquisition-enabled workflow.
- Hardware-tested on a NanoVNA-H at COM10 running firmware `0.4.5-1-gfbbceca` with 101-point, 202-point segmented, two-average, and UI-driven acquisitions.
- Preserved `baseline-pre-nanovna` as the rollback tag for the pre-acquisition application.

