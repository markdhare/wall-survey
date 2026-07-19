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

1. Mark a front-view origin on the wall, normally the lower-left corner of the survey region. Record which physical face is the front and never mirror rear-side positions in software.
2. Define the X/Y coordinates before collecting the main dataset. Spacing may be irregular; close spacing near a suspected boundary is useful.
3. Fix antenna orientation, polarization, stand-off, cable routing, NanoVNA calibration plane, and mounting geometry. Photograph or write down the fixture before it becomes familiar enough to forget.
4. Calibrate on the NanoVNA over the full intended frequency span. Wall Survey reads calibration status but intentionally leaves calibration operations to the instrument.
5. Capture references such as fixed-separation free space, known sandstone, and a known door or void. Repeat at least one reference after the wall scan to expose drift.
6. Use Run Lab for off-grid trials and frequency exploration. Decide on useful frequency points or bands using references and repeatability, not only whichever setting creates the most dramatic wall image.
7. Import or create the coordinate plan, then capture or import map measurements. Use repeats at selected locations to estimate measurement variability.
8. Compare absolute and baseline-normalized results, inspect the full traces, and check neighboring frequencies. Treat the heatmap as an interpolation of measurements rather than a photograph of the wall interior.
9. Save a portable `.wallscan` project, export any CSV/PNG reports, and separately back up the raw capture directory.

Wall Survey can also acquire directly from a NanoVNA-H. See [ACQUISITION_GUIDE.md](ACQUISITION_GUIDE.md) for serial connection, application-controlled segmented sweeps, averaging, immediate raw preservation, quality warnings, and guided grid routing.

## Where data belongs

Wall Survey has three intentionally different destinations:

- **Run Lab** holds off-grid or not-yet-classified runs. Use it for fixture checks, known-wall/known-void experiments, choosing a useful frequency band, and measurements that may be mapped later.
- **References** groups one or more repeat runs representing a named baseline condition. Choosing the group in **Baseline** complex-averages its repeats before comparison.
- **Wall Map** holds runs at explicit front-view X/Y coordinates. Several runs at one location are treated as repeats and produce mean and sample-standard-deviation results.

A run does not need a coordinate when it is captured. It can begin in Run Lab and be moved to the map after its trace and quality have been reviewed.

## First-time tutorial: from connection to heatmap

This tutorial uses direct acquisition, but imported S2P files can be substituted at the corresponding steps.

### 1. Start a clean session

Launch Wall Survey and click **New**. Decide where the raw acquisition directory will live; the default `captures/` folder is suitable for testing, but a named survey directory on a backed-up drive is better for field work. Raw acquisition survives independently of the project, while **Save** creates the portable `.wallscan` archive that preserves routed runs and project organization.

### 2. Prepare and connect the instrument

Power on the NanoVNA-H, perform or recall a suitable on-device two-port calibration, and attach the antennas in their controlled geometry. NanoVNA-Saver may remain open, but it must be disconnected from the serial port. In **NanoVNA acquisition**, click **Rescan**, choose the correct COM port, and click **Connect**. Read the model, firmware, and calibration response instead of treating a successful serial connection as proof of a valid measurement setup.

### 3. Make an exploratory Run Lab capture

Set the start/stop frequencies, total points, and averages. Begin with 101 points and one average. Set **Destination** to **Run Lab (off-grid)**, enter a useful label such as `free_space_fixture_check`, position the antennas, and click **Capture sweep**. Wait for the raw-file path and sanity-check result before moving anything.

Repeat for a known wall, known void, door, or obstacle if available. Select multiple Run Lab rows with Ctrl-click to overlay their traces. To calculate one run relative to another, select one in **Baseline**, choose a comparison mode, then adjust center frequency and bandwidth. The blue line or band on the graph shows exactly what the scalar result uses.

### 4. Create the map plan

Prepare a CSV with `label,x_cm,y_cm` and optional `row,column` columns, then click **Import grid CSV**. Check the **Wall Map** table before collecting: X must increase to the right in the chosen front view and Y must increase upward. Empty locations are useful because the guided acquisition destination can now identify the next unmeasured point.

### 5. Map an exploratory run if appropriate

If a Run Lab measurement was actually taken at a known wall coordinate, select its row and click **Map selected runs**. Choose an existing location or type a new label and coordinates. The operation moves the same run into the map; it does not duplicate or rewrite the source S2P file. Multiple selected rows can be moved together as repeats at one location.

Do not map free-space checks or material references merely to make them disappear from Run Lab. They are not spatial samples of the wall and should remain loose or belong to a reference group.

### 6. Capture the grid

In the acquisition panel choose **Next empty grid location**. The target hint displays the location that will receive the next run. Position both antennas, verify the front-view coordinate, enter a run label, and manually click **Capture sweep**. After successful preservation, the run is routed to that location and the hint advances to the next empty position. There is no countdown or automatic trigger.

To add a repeat, use **Existing map location** and select the desired point. To create coordinates during capture rather than ahead of time, use **New map location**. If a requested destination disappears or a post-capture dialog is cancelled, the raw file remains safe and the run falls back to Run Lab.

### 7. Analyze the completed map

Choose **Magnitude (dB)** with **Absolute measurement** as an initial view. Then select an appropriate reference and try **Reference delta (dB)**. Move the center frequency through regions where known conditions separate while watching the complete transformed trace. Use a non-zero bandwidth when a stable region is more defensible than a single resonant point.

Open **Wall heatmap**, retain automatic scale while exploring, and use fixed color limits when comparing several exports. Check the table for repeat standard deviation and inspect suspicious points individually. An isolated extreme with poor repeatability is less persuasive than a contiguous, physically plausible region reproduced across nearby settings.

### 8. Save and preserve the work

Click **Save** and create a `.wallscan` project. Export a CSV result table and PNG heatmap for the chosen analysis settings. Keep the original raw acquisition directory and its `capture_log.yaml`; the archive is portable, but preserving both gives the clearest recovery and audit trail.

## Quick comparison without a grid

No grid is required for exploratory work or calibration checks. Click **Add loose run** and select one or several Touchstone files. They appear immediately in **Run Lab**, and selected rows are overlaid in **Run comparison**. The current scalar result for every run follows the metric, center, and bandwidth controls.

To calculate one run relative to another, choose the baseline run from the **Baseline** selector, then choose **Reference delta (dB)**, **Complex ratio magnitude (dB)**, or **Reference phase delta**. Reference groups and individual Run Lab files are both available as baselines. This supports known-wall versus known-void experiments without creating map points. Use **Add reference** when several repeat files describe one baseline condition; select the References tab to inspect their spectra.

### Moving Run Lab runs onto the wall map

Select one or more Run Lab rows and click **Map selected runs**. In the location dialog:

- choose an existing label to append the runs as repeats at that location; or
- type a new label and enter X/Y coordinates in centimetres to create a location.

The runs are removed from Run Lab and moved to the chosen location. Their IDs and source files are unchanged. If a moved loose run was the active comparison baseline, the baseline selection is cleared because that run is no longer a Run Lab baseline; choose an appropriate reference again.

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

Wall Survey supports both direct NanoVNA-H acquisition and files exported by NanoVNA-Saver. A useful naming scheme for manually exported files is:

`wall_<row>_<column>_x<cm>_y<cm>_repeat<n>.s2p`

For example, `wall_r03_c07_x120_y80_repeat2.s2p`. The name is not parsed yet, so coordinates are confirmed in the import dialog. This avoids silent placement errors while the acquisition workflow is being established.

Direct captures use UTC timestamps plus the operator-entered run label and are indexed in `capture_log.yaml`. The application does not infer coordinates from either naming scheme; routing remains an explicit operator decision.

## Project and export files

See [FILE_FORMATS.md](FILE_FORMATS.md) for the archive schema. CSV exports contain SI coordinates, repeat count, result statistics, complete analysis settings, and selected reference. PNG export captures the spatial plot as displayed.
