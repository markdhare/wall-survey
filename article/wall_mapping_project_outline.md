# Seeing Through Stone with a NanoVNA

## A hobby-scale experiment in mapping hidden wall construction with radio-frequency transmission measurements

**Author:** [Your name]  
**Project dates:** [Start date–present]  
**Project repository:** [Repository URL]  
**Status:** Working article outline / project narrative

---

## Abstract

This project explores whether a low-cost NanoVNA-H and two antennas can reveal changes in the internal construction of a thick masonry wall. The motivating question is practical: part of an approximately 45–60 cm sandstone wall may contain a concealed wooden doorway, void, brick infill, or some other nonuniform construction that is no longer visible from the surface. By placing antennas on opposite sides of the wall and measuring forward transmission, or S21, over a grid of positions and frequencies, the experiment attempts to turn local differences in radio-frequency propagation into a two-dimensional map.

The work combines a repeatable field-measurement procedure with a custom Python/PySide6 application for importing Touchstone files, organizing measurements spatially, comparing them with reference runs, and displaying derived quantities as tables, spectra, and heatmaps. This is an exploratory hobby project rather than a controlled research study. Its central question is therefore not whether the instrument can identify wall materials with certainty, but whether inexpensive measurements can produce stable, interpretable contrast that is useful for locating anomalies and motivating more focused investigation.

> **Fill in later:** Add one or two sentences summarizing the most interesting result, the frequencies that worked best, and whether the suspected opening was supported by another form of evidence.

## 1. Motivation and project goal

[Describe the building, wall, and practical reason for suspecting a hidden opening. Include the wall's approximate age, dimensions, accessible faces, visible construction, and any historical or architectural clues. Explain why conventional inspection methods were inconvenient, destructive, expensive, or inconclusive.]

The basic hypothesis is that sandstone, mortar, brick, wood, air gaps, and composite infill will not transmit an RF signal identically. Their dielectric properties, moisture content, conductivity, thickness, and internal interfaces should affect attenuation and phase. If those effects are large compared with measurement drift and positioning error, a spatial survey may reveal a region whose transmission differs consistently from the surrounding masonry.

The immediate goal is anomaly mapping rather than definitive material identification. A strong, repeatable boundary or region of contrast would be useful even if the data cannot distinguish confidently between wood, brick, and an air-filled cavity. The broader goal is to learn how far inexpensive RF test equipment can be pushed when the measurement procedure, data preservation, and visualization are treated carefully.

> **Possible figure:** Photograph or sketch of the wall, showing the suspected doorway and the survey area without revealing private location details.

## 2. Measurement methodology

The experiment uses a NanoVNA-H as a swept-frequency source and receiver. One antenna is positioned on each side of the wall, nominally aligned along the same transmission path. At every survey location, the instrument records S21 over a broad frequency span—for example, 500 MHz to 1.5 GHz—and the Wall Survey application acquires and immediately preserves the complex measurements as Touchstone `.s2p` files. NanoVNA-Saver exports remain compatible as an alternate workflow. Coordinates are defined from a front view of the wall, with X increasing to the right and Y increasing upward, so measurements taken from opposite sides are not accidentally mirrored during mapping.

Reference measurements provide context for the wall survey. Candidate references include a fixed antenna separation in free space, known sandstone construction, a known wooden door or void, and repeated baseline measurements before and after a scan. Repeats help distinguish persistent spatial contrast from cable movement, antenna misalignment, instrument drift, or changes in the surrounding environment. The experimental setup should keep antenna polarization, stand-off distance, cable placement, calibration plane, sweep configuration, and mounting geometry as constant as practical.

> **Fill in later:** Record antenna models and polarization, NanoVNA firmware, calibration procedure, frequency range, point count, averaging, grid coordinates, fixture design, wall thickness, weather/moisture conditions, and number of repeats. Note any deviations from the planned procedure instead of silently cleaning them up.

> **Possible figure:** Diagram of the opposed antennas, wall thickness, front-view coordinate system, and direction of S21 transmission.

## 3. Software and analysis implementation

The accompanying Wall Survey application was written in Python with PySide6. It imports Touchstone S1P/S2P data, preserves original measurement files in portable project archives, and groups runs either as reference conditions, off-grid comparison experiments, or measurements assigned to arbitrary wall coordinates. Repeated runs can occupy the same location. Project metadata is stored in human-readable YAML, while calculated tables and images can be exported as CSV and PNG.

Analysis can focus on a single interpolated frequency or a finite band. Available quantities include magnitude in decibels, linear magnitude, phase, mean or integrated linear power, group delay, and peak or minimum magnitude. Measurements can be shown absolutely or normalized to a complex-averaged reference. The application plots the transformed frequency trace, marks the active frequency or band, reports repeat statistics, and generates a spatial heatmap using inverse-distance weighting while retaining markers at the actual measured coordinates.

This separation between raw measurements and derived views is important. A visually persuasive heatmap can be produced from sparse or noisy data, particularly when its color scale is narrow. The measured points, analysis settings, reference choice, interpolation method, and scale therefore need to remain visible or recoverable. The heatmap is best understood as a navigational summary of the samples—not a literal image of the wall interior.

> **Fill in later:** Include screenshots of the Run Lab, a representative baseline comparison, the final grid table, and one or two heatmaps. Explain why the selected frequency or band was chosen rather than presenting it as inevitable.

## 4. Initial observations and interpretation

[Describe what appeared in the spectra before discussing the map. Which frequency regions separated the reference conditions? Were differences broadband or narrow resonances? How well did repeated baselines agree? Did phase or power add useful information beyond magnitude in dB?]

[Describe the spatial result. Identify regions that were consistently higher or lower than the surrounding wall, whether their boundaries resembled a plausible doorway, and whether the anomaly persisted across nearby frequencies and repeat measurements. Note unexpected features and failed measurement attempts as well as the attractive result.]

Any claimed wall feature should be supported by converging evidence. Useful signs include a contiguous region spanning several independently measured points, a physically plausible shape, agreement across repeated scans, behavior resembling a known reference, and confirmation by drawings, inspection holes, thermal imaging, radar, construction work, or another independent method. A single bright heatmap cell or an anomaly found only after extensive frequency searching is much weaker evidence.

> **Results table placeholder:** Reference repeatability, strongest discrimination frequency/band, anomaly dimensions, effect size relative to local variability, and any independent confirmation.

## 5. How valid is this approach?

There are sound physical reasons to expect contrast, but many reasons to be cautious about interpreting it. S21 is affected by the complete propagation path: both antennas and their near fields, wall interfaces, multiple reflections, diffraction around edges, polarization, cable motion, nearby metal, moisture, surface geometry, and coupling through routes other than the intended straight line. A thick, irregular masonry wall is not a uniform laboratory sample. At these wavelengths, the system may respond to features over a broad volume rather than a narrow ray between the antennas.

Consequently, this setup is unlikely to produce an unambiguous material map in the way that an X-ray or carefully engineered radar system might. It may nevertheless function as a comparative anomaly detector. Its credibility depends less on the visual polish of the map than on repeatability, controls, blinded or predeclared analysis where practical, and independent validation. Useful follow-up experiments would include moving a known obstacle through the path, scanning a wall with known construction, reversing antenna roles, changing polarization and stand-off, repeating on different days, withholding some known locations during frequency selection, and comparing results with a second sensing method.

> **Personal assessment:** [Explain what level of evidence would make you comfortable drilling, opening the wall, recommending a professional survey, or concluding that the method was inconclusive.]

## 6. Other possible applications

The same measurement and visualization workflow could support other small-scale RF experiments. Examples include locating studs, cavities, repairs, moisture-related changes, or different masonry infill; comparing shielding or attenuation across building materials; mapping RF leakage through enclosures; testing antenna alignment through partitions; and documenting how transmission changes as materials cure, dry, or become wet. Many of these applications would require their own reference fixtures and should not inherit conclusions from the sandstone-wall experiment automatically.

A related extension is reflection-mode surveying using S11 and a single antenna, moving the project closer to a simple ground-penetrating-radar concept. That introduces additional challenges: direct antenna reflections can dominate the signal, depth estimation requires time-domain processing and assumptions about wave velocity, and useful spatial resolution competes with penetration depth and antenna bandwidth. Still, the existing data model and Touchstone workflow provide a starting point for experiments with frequency-domain reflectometry, synthetic-aperture scans, or comparisons between known layered samples.

There may also be a modest service or product opportunity in repeatable, nondestructive anomaly screening for unusual buildings, restoration projects, or educational demonstrations. Any such use would need clear limits: this instrument would indicate areas worth investigating, not certify structural condition, identify hazardous materials, or replace professional radar, engineering, or conservation expertise. A practical offering might emphasize documented measurements, transparent uncertainty, and collaboration with specialists rather than definitive claims.

## 7. Next steps

The software now includes direct NanoVNA-H acquisition, immediate raw preservation, guided grid routing, and basic capture sanity checks. Near-term improvements include stronger metadata capture, better comparison of multiple reference materials, richer repeatability diagnostics, and support for additional VNA protocols. On the experimental side, the most valuable next step is likely a controlled mock wall or known doorway that can be scanned without uncertainty about the ground truth. That would allow frequency choice, grid spacing, antenna geometry, and classification ideas to be evaluated without tuning them solely against the mystery wall.

> **Fill in later:** List the next three experiments in priority order, what each would test, what equipment or construction is required, and what outcome would change your confidence in the approach.

## 8. Conclusion

This project asks a deliberately modest question: can accessible RF equipment help a careful hobbyist find evidence of hidden nonuniform construction in a wall? The combination of complex transmission measurements, repeatable spatial sampling, reference comparisons, and honest visualization appears capable of producing interesting—and potentially useful—anomaly maps. Whether those anomalies correspond to a concealed doorway remains an empirical question that should be answered with repeat measurements and independent evidence.

Regardless of the final wall result, the project provides a useful platform for learning about RF propagation, measurement uncertainty, scientific software, and the difference between detecting contrast and explaining its cause. That distinction is likely the most important lesson to preserve as the experiment becomes more polished.

> **Final paragraph placeholder:** End with the actual outcome, what surprised you, and the next question the project made you want to investigate.

## Suggested supporting material

- Photographs of the apparatus and antenna fixtures
- Survey grid diagram and coordinate CSV
- Representative raw and normalized S21 spectra
- Baseline repeatability plot
- Heatmaps at several preselected frequencies or bands
- Comparison with known-wall and known-void references
- Table of acquisition and analysis settings
- Link to source code and a small anonymized example dataset
- Short limitations and safety statement
