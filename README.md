# Wall Survey

Wall Survey is a PySide6 desktop application for acquiring, organizing, and analyzing NanoVNA S21 measurements on a physical wall grid. It connects directly to NanoVNA-H/H4 devices, imports existing Touchstone files, preserves raw captures with YAML metadata, compares measurements with reference runs, and presents RF metrics as tables, transformed traces, and spatial heatmaps.

Version 0.2 introduces built-in NanoVNA-H acquisition with COM-port discovery, application-controlled 101-point segmentation, complex averaging, quality warnings, flexible capture routing, and guided progression through empty grid locations. NanoVNA-Saver file import remains supported.

## Quick start

```powershell
uv sync --extra dev
uv run wall-survey
```

After the environment has been created on Windows, the application can also be started directly with:

```powershell
.\.venv\Scripts\wall-survey.exe
```

See [documentation/USER_GUIDE.md](documentation/USER_GUIDE.md) for the analysis workflow, [documentation/ACQUISITION_GUIDE.md](documentation/ACQUISITION_GUIDE.md) for direct NanoVNA-H scanning, and [documentation/DEVELOPER_GUIDE.md](documentation/DEVELOPER_GUIDE.md) for architecture and algorithms.

## Documentation

- [User guide and first-time tutorial](documentation/USER_GUIDE.md)
- [Direct NanoVNA-H acquisition](documentation/ACQUISITION_GUIDE.md)
- [File and YAML formats](documentation/FILE_FORMATS.md)
- [Developer architecture and algorithms](documentation/DEVELOPER_GUIDE.md)
- [Release notes](documentation/RELEASE_NOTES.md)
