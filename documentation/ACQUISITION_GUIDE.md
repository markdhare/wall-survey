# Direct NanoVNA-H Acquisition

## Scope

Wall Survey can control and acquire calibrated S11/S21 data directly from a NanoVNA-H or NanoVNA-H4 using its ASCII shell over USB serial. The current driver intentionally does not support NanoVNA V2 hardware, which uses a different binary protocol. Hardware access is isolated behind the `VnaDevice` interface so a V2 driver can be added without changing project routing, raw-data storage, or the acquisition panel.

The application controls sweep start, stop, total point count, and averaging. Calibration remains the instrument's responsibility. Wall Survey reads and displays the NanoVNA calibration status but does not perform, alter, save, or recall calibration standards.

## Connecting

1. Connect and power on the NanoVNA-H with a data-capable USB cable.
2. Disconnect NanoVNA-Saver or any other program currently holding the serial port. The program may remain open as long as it is not connected.
3. Open Wall Survey and locate the **NanoVNA acquisition** panel on the right. The toolbar action with the same name shows or hides it.
4. Click **Rescan** if the device was connected after Wall Survey started.
5. Choose the COM port and click **Connect**. On the tested Windows system this is COM10.
6. Confirm that the reported model, firmware, and calibration text are plausible before measuring.

Port discovery lists all serial devices because some Windows driver combinations do not expose enough USB metadata to identify a NanoVNA in advance. Connection performs an ASCII-shell handshake and rejects a port that does not identify as a NanoVNA-H-family device.

## Configuring a sweep

Enter start and stop frequencies in MHz, the total desired points, and the number of averages. This NanoVNA-H firmware acquires 101 points per hardware segment and silently substitutes 101 when given unsupported nearby counts. Wall Survey therefore uses explicit totals of 101, 202, 303, and so on. It divides the requested span into contiguous 101-point segments and combines them in ascending frequency order. The panel shows the resulting number of hardware sweeps.

For each average, Wall Survey configures the segment, resumes the instrument, waits for a complete sweep, pauses it, and reads calibrated S11 and S21 complex values. It averages complex values—not dB magnitudes—then resumes the instrument when acquisition finishes. More points, segments, and averages increase capture time approximately proportionally.

Start with 101 points and one average while checking geometry. Increase the total points when looking for narrow spectral regions and increase averaging when repeat sweeps show random variation. Calibration must cover the requested span; an on-screen calibration indication does not prove that the calibration standards or fixture were correct.

## Preserving and routing captures

Every successful hardware acquisition is written to disk before it is added to the project or displayed. Choose a raw data directory in the panel and give the run a meaningful label. Each capture produces:

- A timestamped `.s2p` file containing S11 and S21 in real/imaginary form. S12 and S22 are zero because the NanoVNA-H does not measure those paths in this workflow.
- An entry in the directory's consolidated `capture_log.yaml`, including UTC timestamp, device identity, calibration text, sweep settings, intended route, and quality warnings.

The raw directory defaults to `captures/` and is excluded from Git. Back it up independently or save the project as a `.wallscan`, which packages all routed source files. Even if a routing dialog is cancelled or the project is never saved, the raw S2P and YAML log remain recoverable.

The destination choices are:

- **Run Lab (off-grid):** immediate exploratory analysis without map coordinates.
- **New reference group:** prompts for a new reference condition after raw preservation.
- **Existing reference group:** adds the capture as a repeat to the selected reference.
- **New map location:** prompts for a front-view label and metric coordinates.
- **Existing map location:** adds the capture as a repeat at a selected position.
- **Next empty grid location:** routes to the first location with no runs, then advances the panel hint to the next empty location. Import a coordinate CSV first to use this as a guided scan.

If a requested destination no longer exists or a post-capture dialog is cancelled, the preserved capture falls back to Run Lab rather than being discarded.

## Quality warnings

After preservation, the application performs deliberately conservative sanity checks. A red warning is raised for conditions such as:

- non-finite complex values;
- duplicated or decreasing frequencies;
- effectively zero S21 across the sweep;
- nearly identical S21 at every frequency;
- a large fraction of values at the numerical floor; or
- many passive-system transmission magnitudes far above one.

Warnings never delete or suppress a capture. They identify runs that deserve inspection for loose cables, wrong ports, missing antennas, unsuitable calibration, saturated/invalid output, or device communication problems. Passing these checks does not establish scientific validity or prove calibration quality.

## Field workflow

For guided wall mapping, import the complete coordinate grid and select **Next empty grid location**. Position and verify both antennas, read the prominently displayed next target, and manually click **Capture sweep**. Confirm successful raw preservation and routing before moving to the next point. The operator retains control of pacing; there is no countdown or automatic trigger.

Reference runs should be captured before and after the spatial scan when practical. Do not move cables unnecessarily, and record any repositioning, antenna change, calibration change, or interruption that could divide the dataset into different experimental conditions.

## Tested hardware

The initial implementation was exercised against a NanoVNA-H on COM10 running firmware `0.4.5-1-gfbbceca`. Its shell reported the expected `sweep`, `frequencies`, `data`, `pause`, `resume`, and calibration-status commands. A direct 500 MHz–1.5 GHz, 101-point capture and a complete UI-driven capture both returned valid data without sanity warnings.
