"""Persistent side panel for direct VNA connection and acquisition."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from .acquisition import NanoVNAHDevice, SweepSettings, discover_serial_ports, save_capture


DESTINATIONS = [
    ("Run Lab (off-grid)", "run_lab"),
    ("New reference group", "new_reference"),
    ("Existing reference group", "existing_reference"),
    ("New map location", "new_location"),
    ("Existing map location", "existing_location"),
    ("Next empty grid location", "next_empty"),
]


class WorkerSignals(QObject):
    connected = Signal(object)
    captured = Signal(object, str, str, str, str)
    progress = Signal(int, int, str)
    failed = Signal(str)
    done = Signal()


class ConnectWorker(QRunnable):
    def __init__(self, device: NanoVNAHDevice):
        super().__init__(); self.device = device; self.signals = WorkerSignals()

    def run(self):
        try: self.signals.connected.emit(self.device.connect())
        except Exception as exc: self.signals.failed.emit(str(exc))
        finally: self.signals.done.emit()


class CaptureWorker(QRunnable):
    def __init__(self, device, settings, directory, label, destination, target_id):
        super().__init__(); self.device = device; self.settings = settings; self.directory = directory
        self.label = label; self.destination = destination; self.target_id = target_id; self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.device.acquire(self.settings, lambda n, total, message: self.signals.progress.emit(n, total, message))
            path = save_capture(result, self.directory, self.label, self.destination)
            self.signals.captured.emit(result, str(path), self.destination, self.target_id, self.label)
        except Exception as exc: self.signals.failed.emit(str(exc))
        finally: self.signals.done.emit()


class AcquisitionDock(QDockWidget):
    capture_ready = Signal(object, str, str, str, str)

    def __init__(self, parent=None):
        super().__init__("NanoVNA acquisition", parent)
        self.setObjectName("nanovna_acquisition")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.device: NanoVNAHDevice | None = None
        self.pool = QThreadPool.globalInstance(); self._workers: set[QRunnable] = set()
        self.settings_store = QSettings()
        self._build_ui(); self.rescan_ports(); self._update_destination(); self._set_connected(False)

    def _build_ui(self):
        body = QWidget(); outer = QVBoxLayout(body); outer.setContentsMargins(8, 8, 8, 8); outer.setSpacing(8)
        connection = QGroupBox("Connection"); form = QFormLayout(connection)
        port_row = QWidget(); port_layout = QHBoxLayout(port_row); port_layout.setContentsMargins(0, 0, 0, 0)
        self.port = QComboBox(); self.rescan = QPushButton("Rescan"); self.rescan.clicked.connect(self.rescan_ports)
        port_layout.addWidget(self.port, 1); port_layout.addWidget(self.rescan); form.addRow("Serial port", port_row)
        self.connect_button = QPushButton("Connect"); self.connect_button.clicked.connect(self.toggle_connection)
        self.device_status = QLabel("Disconnected"); self.device_status.setWordWrap(True)
        form.addRow(self.connect_button); form.addRow("Status", self.device_status); outer.addWidget(connection)

        sweep = QGroupBox("Application-controlled sweep"); sweep_form = QFormLayout(sweep)
        self.start = QDoubleSpinBox(); self.start.setRange(0.05, 1_500); self.start.setDecimals(3); self.start.setValue(500); self.start.setSuffix(" MHz")
        self.stop = QDoubleSpinBox(); self.stop.setRange(0.05, 1_500); self.stop.setDecimals(3); self.stop.setValue(1500); self.stop.setSuffix(" MHz")
        self.points = QSpinBox(); self.points.setRange(101, 10_100); self.points.setSingleStep(101); self.points.setValue(101)
        self.points.editingFinished.connect(self._normalize_points)
        self.averages = QSpinBox(); self.averages.setRange(1, 100); self.averages.setValue(1)
        self.sweep_summary = QLabel(); self.sweep_summary.setObjectName("secondary")
        for widget in (self.start, self.stop, self.points, self.averages): widget.valueChanged.connect(self._update_sweep_summary)
        sweep_form.addRow("Start", self.start); sweep_form.addRow("Stop", self.stop); sweep_form.addRow("Total points (101×)", self.points); sweep_form.addRow("Averages", self.averages); sweep_form.addRow(self.sweep_summary)
        outer.addWidget(sweep)

        routing = QGroupBox("Preserve and route capture"); route_form = QFormLayout(routing)
        self.run_label = QLineEdit("capture"); self.destination = QComboBox()
        for label, key in DESTINATIONS: self.destination.addItem(label, key)
        self.destination.currentIndexChanged.connect(self._update_destination)
        self.target = QComboBox(); self.target_hint = QLabel(); self.target_hint.setWordWrap(True); self.target_hint.setObjectName("secondary")
        raw_row = QWidget(); raw_layout = QHBoxLayout(raw_row); raw_layout.setContentsMargins(0, 0, 0, 0)
        default_dir = self.settings_store.value("acquisition/raw_directory", str(Path.cwd() / "captures"))
        self.raw_directory = QLineEdit(str(default_dir)); self.browse = QPushButton("…"); self.browse.setFixedWidth(32); self.browse.clicked.connect(self.choose_directory)
        raw_layout.addWidget(self.raw_directory, 1); raw_layout.addWidget(self.browse)
        route_form.addRow("Run label", self.run_label); route_form.addRow("Destination", self.destination); route_form.addRow("Target", self.target); route_form.addRow(self.target_hint); route_form.addRow("Raw data folder", raw_row)
        outer.addWidget(routing)

        self.capture_button = QPushButton("Capture sweep"); self.capture_button.setObjectName("captureButton"); self.capture_button.clicked.connect(self.capture)
        self.progress = QLabel("Ready"); self.progress.setWordWrap(True)
        self.quality = QLabel(); self.quality.setWordWrap(True); self.quality.setObjectName("quality")
        outer.addWidget(self.capture_button); outer.addWidget(self.progress); outer.addWidget(self.quality); outer.addStretch()
        self.setWidget(body); self.setMinimumWidth(330)
        self._update_sweep_summary()

    def rescan_ports(self):
        previous = self.port.currentData() or self.settings_store.value("acquisition/port", "COM10")
        self.port.clear()
        for device, label in discover_serial_ports(): self.port.addItem(label, device)
        index = self.port.findData(previous)
        if index >= 0: self.port.setCurrentIndex(index)
        if not self.port.count(): self.port.addItem("No serial ports found", None)

    def toggle_connection(self):
        if self.device and self.device.connected:
            self.device.disconnect(); self.device = None; self._set_connected(False); return
        port = self.port.currentData()
        if not port: self._failure("Select a serial port first."); return
        self.device = NanoVNAHDevice(port); self._set_busy(True, "Connecting…")
        worker = ConnectWorker(self.device); self._track(worker)
        worker.signals.connected.connect(self._connected); worker.signals.failed.connect(self._failure); worker.signals.done.connect(lambda: self._set_busy(False))
        self.pool.start(worker)

    def capture(self):
        if not self.device or not self.device.connected: self._failure("Connect to a NanoVNA-H before capturing."); return
        settings = SweepSettings(round(self.start.value() * 1e6), round(self.stop.value() * 1e6), self.points.value(), self.averages.value())
        try: settings.validate()
        except ValueError as exc: self._failure(str(exc)); return
        directory = self.raw_directory.text().strip()
        if not directory: self._failure("Choose a raw data folder."); return
        label = self.run_label.text().strip() or "capture"; destination = self.destination.currentData(); target_id = self.target.currentData() or ""
        self.settings_store.setValue("acquisition/raw_directory", directory)
        self._set_busy(True, "Starting capture…"); self.quality.clear()
        worker = CaptureWorker(self.device, settings, directory, label, destination, target_id); self._track(worker)
        worker.signals.progress.connect(self._progress); worker.signals.failed.connect(self._failure)
        worker.signals.captured.connect(self._captured); worker.signals.done.connect(lambda: self._set_busy(False))
        self.pool.start(worker)

    def set_targets(self, references, locations):
        self._references = [(item.id, item.name) for item in references]
        self._locations = [(item.id, item.label, bool(item.runs)) for item in locations]
        self._update_destination()

    def _update_destination(self):
        if not hasattr(self, "target"): return
        key = self.destination.currentData(); self.target.clear(); hint = ""
        if key == "existing_reference":
            for id_, name in getattr(self, "_references", []): self.target.addItem(name, id_)
            hint = "The new run will be added as another repeat in this reference group."
        elif key == "existing_location":
            for id_, name, has_runs in getattr(self, "_locations", []): self.target.addItem(f"{name}{' · measured' if has_runs else ''}", id_)
            hint = "The new run will become a repeat at this map position."
        elif key == "next_empty":
            empty = next(((id_, name) for id_, name, has_runs in getattr(self, "_locations", []) if not has_runs), None)
            if empty: self.target.addItem(empty[1], empty[0]); hint = f"Guided scan next position: {empty[1]}"
            else: hint = "No empty grid locations remain; the capture will fall back to Run Lab."
        elif key == "new_reference": hint = "You will name the new reference group after the raw file is safely written."
        elif key == "new_location": hint = "You will enter coordinates after the raw file is safely written."
        else: hint = "The run remains off-grid for immediate comparison in Run Lab."
        self.target.setVisible(key in {"existing_reference", "existing_location", "next_empty"}); self.target_hint.setText(hint)

    def choose_directory(self):
        value = QFileDialog.getExistingDirectory(self, "Raw NanoVNA capture folder", self.raw_directory.text())
        if value: self.raw_directory.setText(value)

    def _connected(self, identity):
        self.settings_store.setValue("acquisition/port", identity.port)
        self.device_status.setText(f"{identity.model} · firmware {identity.firmware}\nCalibration: {identity.calibration}")
        self.device_status.setProperty("connected", True); self.device_status.style().unpolish(self.device_status); self.device_status.style().polish(self.device_status)
        self._set_connected(True); self.progress.setText("Connected and ready.")

    def _captured(self, result, path, destination, target_id, label):
        if result.quality_flags:
            self.quality.setText("⚠ Quality warning\n" + "\n".join(f"• {flag}" for flag in result.quality_flags))
            self.quality.setProperty("warning", True)
        else:
            self.quality.setText("✓ Capture passed basic sanity checks."); self.quality.setProperty("warning", False)
        self.quality.style().unpolish(self.quality); self.quality.style().polish(self.quality)
        self._set_progress(f"Raw data saved: {path}"); self.capture_ready.emit(result, path, destination, target_id, label)

    def _progress(self, current, total, message): self._set_progress(f"{message} ({current}/{total})")

    def _failure(self, message):
        self.progress.setText(f"Error: {message}"); self.progress.setProperty("error", True); self.progress.style().unpolish(self.progress); self.progress.style().polish(self.progress)

    def _set_progress(self, message):
        self.progress.setText(message); self.progress.setProperty("error", False); self.progress.style().unpolish(self.progress); self.progress.style().polish(self.progress)

    def _set_busy(self, busy: bool, message: str | None = None):
        self.connect_button.setEnabled(not busy); self.capture_button.setEnabled(not busy and bool(self.device and self.device.connected)); self.rescan.setEnabled(not busy)
        if message: self._set_progress(message)

    def _set_connected(self, connected: bool):
        self.connect_button.setText("Disconnect" if connected else "Connect"); self.capture_button.setEnabled(connected); self.port.setEnabled(not connected); self.rescan.setEnabled(not connected)
        self.device_status.setProperty("connected", connected); self.device_status.style().unpolish(self.device_status); self.device_status.style().polish(self.device_status)
        if not connected: self.device_status.setText("Disconnected")

    def _update_sweep_summary(self):
        segments = max(1, round(self.points.value() / 101)); captures = segments * self.averages.value()
        self.sweep_summary.setText(f"{segments} segment(s), {captures} device sweep(s); 101 points per segment.")

    def _normalize_points(self):
        self.points.setValue(max(101, round(self.points.value() / 101) * 101))

    def _track(self, worker):
        self._workers.add(worker); worker.signals.done.connect(lambda: self._workers.discard(worker))

    def shutdown(self):
        if self.device: self.device.disconnect(); self.device = None
