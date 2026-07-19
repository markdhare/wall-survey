# Wall Survey User Guide

## Purpose and measurement convention

Wall Survey turns NanoVNA Touchstone measurements into a spatial transmission map. The primary workflow uses two antennas, one on each face of a wall, and S21 measurements taken at known front-view coordinates. The application is an analysis tool, not a safety or structural diagnosis system.

Every map is a **front view of the wall**. Stand on the chosen front side: positive X points right and positive Y points up. Record all positions using that convention even when an operator walks to the rear antenna. Do not mirror rear-side coordinates. Internally coordinates are metres; the interface displays centimetres.

## Installation and startup

Install [uv](https://docs.astral.sh/uv/) once, then from the repository:

```powershell
uv sync --extra dev
uv run wall-survey
```

Linux uses the same commands. PySide6 supplies the Qt runtime; a separate Qt installation is unnecessary.

## Recommended field workflow

1. Mark a front-view origin on the wall, normally the lower-left corner of the survey region.
2. Define the X/Y coordinates before collecting data. Spacing may be irregular; close spacing near a suspected boundary is useful.
3. Fix antenna orientation, polarization, stand-off, cable routing, NanoVNA sweep, calibration plane, and transmit power. Photograph or write down the fixture.
4. Measure references such as fixed-separation free space, known sandstone, and a known door. Repeat at least one reference after the survey to expose drift.
5. Export each sweep as `.s2p` from NanoVNA-Saver. Preserve raw files unchanged.
6. Optionally import a coordinate plan CSV, then add reference and measurement runs. Selecting an existing location label adds repeats instead of creating another point.
7. Choose a metric, comparison, reference, center frequency, and bandwidth. A bandwidth of zero samples the selected point by complex interpolation.
8. Inspect the result table, spatial map, and frequency traces. Export CSV and PNG outputs and save a portable `.wallscan` project.

## Quick comparison without a grid

No grid is required for exploratory work or calibration checks. Click **Add loose run** and select one or several Touchstone files. They appear immediately in **Run Lab**, and selected rows are overlaid in **Run comparison**. The current scalar result for every run follows the metric, center, and bandwidth controls.

To calculate one run relative to another, choose the baseline run from the **Baseline** selector, then choose **Reference delta (dB)**, **Complex ratio magnitude (dB)**, or **Reference phase delta**. Reference groups and individual Run Lab files are both available as baselines. This supports known-wall versus known-void experiments without creating map points. Use **Add reference** when several repeat files describe one baseline condition; select the References tab to inspect their spectra.

## Controls and analysis choices

The top analysis bar updates the tables, comparison graph, and map immediately. **Baseline** identifies the reference group or loose run used by a reference comparison; it has no effect on **Absolute measurement**. The graph title and vertical axis always identify the quantity currently displayed. A blue vertical line marks a point analysis; a translucent blue region marks the samples included in a band analysis.

- **Magnitude (dB)** is the mean of `20 log10(|S|)` in the selected band. This is usually the clearest starting point.
- **Linear magnitude** averages `|S|` without logarithmic weighting.
- **Mean linear power** averages `|S|²`; this is preferable when interpreting received-power ratios.
- **Integrated linear power** integrates `|S|² df` over a band and therefore has power-ratio-hertz units. At a point it falls back to `|S|²`.
- **Unwrapped phase** averages phase after one-dimensional unwrapping.
- **Group delay** is `-dφ/dω` in nanoseconds and requires a non-zero band with at least two sweep points.
- **Peak** and **minimum** select the largest or smallest magnitude in the band.

Comparisons remain explicitly separate from metrics:

- **Absolute measurement** analyzes the test run directly.
- **Reference delta (dB)** displays and averages `20 log10(|S_test / mean(S_reference)|)`. Because this comparison defines its result in dB, the separate metric selector is disabled.
- **Complex ratio magnitude (dB)** first forms the complex ratio `S_test / mean(S_reference)`, then applies the selected metric. This permits normalized linear power, phase, group delay, and the other metric choices as well as magnitude.
- **Reference phase delta** computes the circular mean of the phase of `S_test × conjugate(S_reference)`.

Reference repeats are interpolated onto each test run's analysis frequencies and averaged as complex values. Only the frequency overlap shared by the test and every selected reference repeat is compared; values are never extrapolated beyond a reference sweep. Location repeats are analyzed individually; the table reports their arithmetic mean and sample standard deviation. A dash means the requested frequency is outside a run, a required reference is absent, the sweeps do not overlap, or the metric is undefined.

## Reading the displays

The Measurements table preserves the exact coordinates and reports repeat statistics. The spatial map places measured dots at true coordinates and uses inverse-distance weighting to create a readable heatmap between them. The interpolated color field is a visualization, not additional measured data. Heatmap scale tools appear only while the heatmap tab is active. Colors autoscale to the current finite minimum and maximum, or uncheck **Auto scale** and enter fixed limits for comparable exports. Select measurement rows to show up to four locations in the trace view.

An optional grid CSV makes irregular or large surveys quick to prepare. It requires `label,x_cm,y_cm` headers and accepts optional `row,column` integer columns. For example:

```csv
label,x_cm,y_cm,row,column
R1C1,0,0,1,1
R1C2,22.5,0,1,2
R2C1,0,17,2,1
```

An apparent anomaly is evidence of changed RF transmission, not by itself proof of wood or a void. Compare several frequencies, both reference-normalized and absolute results, repeatability, and neighboring points. Cable movement, antenna coupling, polarization, metal, moisture, wall geometry, and NanoVNA drift can all produce contrast.

## File naming and bulk collection

The current release deliberately imports exported files rather than controlling NanoVNA-Saver. A useful manual naming scheme is:

`wall_<row>_<column>_x<cm>_y<cm>_repeat<n>.s2p`

For example, `wall_r03_c07_x120_y80_repeat2.s2p`. The name is not parsed yet, so coordinates are confirmed in the import dialog. This avoids silent placement errors while the acquisition workflow is being established.

Direct NanoVNA control is feasible later. It should be implemented as a separate acquisition adapter using the device's serial protocol, with explicit calibration/sweep state and a raw Touchstone snapshot written before analysis. This is moderate work rather than an architectural rewrite because imported runs already enter through a narrow reader/model boundary.

## Project and export files

See [FILE_FORMATS.md](FILE_FORMATS.md) for the archive schema. CSV exports contain SI coordinates, repeat count, result statistics, complete analysis settings, and selected reference. PNG export captures the spatial plot as displayed.
