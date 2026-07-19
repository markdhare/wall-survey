"""Main PySide6 user interface."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMessageBox, QPushButton, QSplitter, QStatusBar,
    QTableWidget, QTableWidgetItem, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from .metrics import AnalysisSettings, Comparison, Metric, analyze
from .model import Location, Reference, Run, SurveyProject
from .project_io import load_project, save_project
from .touchstone import NetworkData, read_touchstone


class LocationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add measurement location")
        form = QFormLayout(self)
        self.label = QComboBox()
        self.label.setEditable(True)
        self.x = QDoubleSpinBox(); self.x.setRange(-100_000, 100_000); self.x.setDecimals(3); self.x.setSuffix(" cm")
        self.y = QDoubleSpinBox(); self.y.setRange(-100_000, 100_000); self.y.setDecimals(3); self.y.setSuffix(" cm")
        form.addRow("Location label", self.label)
        form.addRow("X from front-view left", self.x)
        form.addRow("Y above origin", self.y)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project = SurveyProject()
        self.network_cache: dict[str, NetworkData] = {}
        self.setWindowTitle("Wall Survey — NanoVNA transmission mapping")
        self.resize(1400, 850)
        self._build_actions()
        self._build_ui()
        self._apply_style()
        self.refresh()

    def _build_actions(self):
        toolbar = QToolBar("Project")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, slot in [("New", self.new_project), ("Open", self.open_project), ("Save", self.save_project), ("Import grid CSV", self.import_grid), ("Add reference", self.add_reference), ("Add loose run", self.add_loose_runs), ("Map a run", self.add_location_run), ("Export CSV", self.export_csv), ("Export heatmap", self.export_heatmap)]:
            action = QAction(text, self); action.triggered.connect(slot); toolbar.addAction(action)

    def _build_ui(self):
        outer = QWidget(); layout = QVBoxLayout(outer); layout.setContentsMargins(8, 8, 8, 8)
        self.guidance = QLabel("Start anywhere: add loose runs for quick comparison, add references for baselines, or import a grid for wall mapping.")
        self.guidance.setObjectName("guidance"); layout.addWidget(self.guidance)
        controls = QHBoxLayout()
        self.metric = QComboBox(); self.metric.addItems([item.value for item in Metric])
        self.comparison = QComboBox(); self.comparison.addItems([item.value for item in Comparison])
        self.reference = QComboBox()
        self.frequency = QDoubleSpinBox(); self.frequency.setRange(0.001, 100_000); self.frequency.setValue(900); self.frequency.setDecimals(3); self.frequency.setSuffix(" MHz")
        self.bandwidth = QDoubleSpinBox(); self.bandwidth.setRange(0, 100_000); self.bandwidth.setValue(0); self.bandwidth.setDecimals(3); self.bandwidth.setSuffix(" MHz")
        self.auto_scale = QCheckBox("Auto scale"); self.auto_scale.setChecked(True)
        self.scale_min = QDoubleSpinBox(); self.scale_min.setRange(-1e12, 1e12); self.scale_min.setDecimals(4); self.scale_min.setValue(-60)
        self.scale_max = QDoubleSpinBox(); self.scale_max.setRange(-1e12, 1e12); self.scale_max.setDecimals(4); self.scale_max.setValue(0)
        for label, widget in [("Metric", self.metric), ("Comparison", self.comparison), ("Baseline", self.reference), ("Center", self.frequency), ("Bandwidth (0 = point)", self.bandwidth)]:
            controls.addWidget(QLabel(label)); controls.addWidget(widget)
        controls.addStretch()
        layout.addLayout(controls)
        scale_controls = QHBoxLayout(); scale_controls.addWidget(self.auto_scale); scale_controls.addWidget(QLabel("Color minimum")); scale_controls.addWidget(self.scale_min); scale_controls.addWidget(QLabel("Color maximum")); scale_controls.addWidget(self.scale_max); scale_controls.addStretch(); layout.addLayout(scale_controls)
        splitter = QSplitter(Qt.Horizontal)
        self.data_tabs = QTabWidget()
        self.location_table = QTableWidget(0, 8); self.location_table.setHorizontalHeaderLabels(["Label", "X (cm)", "Y (cm)", "Row", "Column", "Repeats", "Mean", "Std. dev."])
        self.location_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.location_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.reference_table = QTableWidget(0, 3); self.reference_table.setHorizontalHeaderLabels(["Reference", "Material / condition", "Runs"]); self.reference_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.reference_table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.reference_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.loose_table = QTableWidget(0, 4); self.loose_table.setHorizontalHeaderLabels(["Run", "Source file", "Current result", "Frequency span"]); self.loose_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.loose_table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.loose_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.data_tabs.addTab(self.loose_table, "Run Lab"); self.data_tabs.addTab(self.location_table, "Wall Map"); self.data_tabs.addTab(self.reference_table, "References")
        splitter.addWidget(self.data_tabs)
        self.plot_tabs = QTabWidget()
        self.heat_plot = pg.PlotWidget(); self.heat_plot.setLabel("bottom", "X — front view", units="cm"); self.heat_plot.setLabel("left", "Y", units="cm"); self.heat_plot.showGrid(x=True, y=True, alpha=0.25); self.heat_plot.setAspectLocked(True)
        self.heat_image = pg.ImageItem(axisOrder="row-major"); self.heat_plot.addItem(self.heat_image)
        self.heat_scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen("w", width=1)); self.heat_plot.addItem(self.heat_scatter)
        self.trace_plot = pg.PlotWidget(); self.trace_plot.setLabel("bottom", "Frequency", units="Hz"); self.trace_plot.setLabel("left", "S parameter magnitude", units="dB"); self.trace_plot.showGrid(x=True, y=True, alpha=0.25); self.trace_plot.addLegend(offset=(12, 12))
        self.plot_tabs.addTab(self.trace_plot, "Run comparison"); self.plot_tabs.addTab(self.heat_plot, "Wall heatmap")
        splitter.addWidget(self.plot_tabs); splitter.setSizes([520, 850]); layout.addWidget(splitter)
        self.setCentralWidget(outer); self.setStatusBar(QStatusBar())
        for widget in (self.metric, self.comparison, self.reference): widget.currentIndexChanged.connect(self.refresh_results)
        self.frequency.valueChanged.connect(self.refresh_results); self.bandwidth.valueChanged.connect(self.refresh_results)
        self.auto_scale.toggled.connect(self.refresh_results); self.scale_min.valueChanged.connect(self.refresh_results); self.scale_max.valueChanged.connect(self.refresh_results)
        self.location_table.itemSelectionChanged.connect(self.refresh_trace)
        self.reference_table.itemSelectionChanged.connect(self.refresh_trace); self.loose_table.itemSelectionChanged.connect(self.refresh_trace); self.data_tabs.currentChanged.connect(self.refresh_trace)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #111820; color: #dce8f2; }
            QToolBar { background: #18232e; border: 0; spacing: 5px; padding: 6px; }
            QToolButton { background: #243646; border: 1px solid #355064; border-radius: 4px; padding: 7px 10px; }
            QToolButton:hover { background: #2d5268; border-color: #48b9d6; }
            QTabWidget::pane { border: 1px solid #2e4354; }
            QTabBar::tab { background: #18232e; padding: 8px 14px; border: 1px solid #2e4354; }
            QTabBar::tab:selected { background: #24546a; color: white; }
            QTableWidget { background: #10171e; alternate-background-color: #16212a; gridline-color: #2b3e4c; selection-background-color: #27677d; }
            QHeaderView::section { background: #21313e; color: #b9d7e7; padding: 6px; border: 0; border-right: 1px solid #344b5c; }
            QComboBox, QDoubleSpinBox { background: #1b2934; border: 1px solid #3b566a; border-radius: 3px; padding: 4px; }
            QLabel#guidance { background: #153746; color: #bdeeff; border-left: 4px solid #41bad7; padding: 9px; font-size: 13px; }
            QStatusBar { background: #18232e; color: #9dc5d6; }
        """)
        pg.setConfigOption("background", "#10171e"); pg.setConfigOption("foreground", "#c7dae5")

    def settings(self) -> AnalysisSettings:
        return AnalysisSettings(Metric(self.metric.currentText()), Comparison(self.comparison.currentText()), self.frequency.value() * 1e6, self.bandwidth.value() * 1e6, self.project.parameter)

    def network(self, run: Run) -> NetworkData:
        if run.id not in self.network_cache: self.network_cache[run.id] = read_touchstone(run.source)
        return self.network_cache[run.id]

    def reference_networks(self) -> list[NetworkData]:
        item = self.reference.currentData()
        reference = self.project.reference(item)
        if reference: return [self.network(run) for run in reference.runs]
        loose = next((run for run in self.project.loose_runs if run.id == item), None)
        return [self.network(loose)] if loose else []

    def new_project(self):
        self.project = SurveyProject(); self.network_cache.clear(); self.refresh(); self.statusBar().showMessage("New project", 3000)

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Wall Survey", "", "Wall Survey (*.wallscan)")
        if not path: return
        try: self.project = load_project(path); self.network_cache.clear(); self.refresh(); self.statusBar().showMessage(f"Opened {path}", 5000)
        except Exception as exc: self._error("Could not open project", exc)

    def save_project(self):
        path = str(self.project.project_path or "")
        if not path: path, _ = QFileDialog.getSaveFileName(self, "Save Wall Survey", f"{self.project.name}.wallscan", "Wall Survey (*.wallscan)")
        if not path: return
        try: save_project(self.project, path); self.statusBar().showMessage(f"Saved {path}", 5000)
        except Exception as exc: self._error("Could not save project", exc)

    def add_reference(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add reference Touchstone runs", "", "Touchstone (*.s2p *.s1p)")
        if not files: return
        name, accepted = QInputDialog.getText(self, "Reference name", "Reference condition (for example, Free space 18 cm)")
        if not accepted or not name.strip(): return
        try:
            runs = [Run(label=Path(path).stem, source=path) for path in files]
            for run in runs: self.network(run)
            ref = Reference(name=name.strip(), runs=runs); self.project.references.append(ref)
            if not self.project.active_reference_id: self.project.active_reference_id = ref.id
            self.refresh(); self.data_tabs.setCurrentIndex(2); self.reference_table.selectRow(len(self.project.references) - 1); self.plot_tabs.setCurrentIndex(0)
            self.statusBar().showMessage(f"Imported {len(runs)} run(s) into reference '{ref.name}'", 7000)
        except Exception as exc: self._error("Could not import reference", exc)

    def add_loose_runs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add off-grid Touchstone runs", "", "Touchstone (*.s2p *.s1p)")
        if not files: return
        try:
            runs = [Run(label=Path(path).stem, source=path) for path in files]
            for run in runs: self.network(run)
            self.project.loose_runs.extend(runs); self.refresh(); self.data_tabs.setCurrentIndex(0)
            self.loose_table.clearSelection()
            for row in range(len(self.project.loose_runs) - len(runs), len(self.project.loose_runs)): self.loose_table.selectRow(row)
            self.plot_tabs.setCurrentIndex(0); self.statusBar().showMessage(f"Added {len(runs)} off-grid run(s) to Run Lab", 7000)
        except Exception as exc: self._error("Could not import run", exc)

    def import_grid(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import coordinate grid", "", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.DictReader(handle))
            required = {"label", "x_cm", "y_cm"}
            if not rows or not required.issubset(rows[0]):
                raise ValueError("Grid CSV must have label, x_cm, and y_cm columns; row and column are optional")
            known = {loc.label for loc in self.project.locations}
            for item in rows:
                label = item["label"].strip()
                if not label or label in known: raise ValueError(f"Duplicate or empty location label: {label!r}")
                self.project.locations.append(Location(label=label, x_m=float(item["x_cm"]) / 100, y_m=float(item["y_cm"]) / 100, row=int(item["row"]) if item.get("row", "").strip() else None, column=int(item["column"]) if item.get("column", "").strip() else None))
                known.add(label)
            self.refresh(); self.statusBar().showMessage(f"Imported {len(rows)} grid locations", 5000)
        except Exception as exc: self._error("Could not import grid", exc)

    def add_location_run(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add measurement runs", "", "Touchstone (*.s2p *.s1p)")
        if not files: return
        dialog = LocationDialog(self)
        for loc in self.project.locations: dialog.label.addItem(loc.label, loc.id)
        if dialog.exec() != QDialog.Accepted: return
        try:
            runs = [Run(label=Path(path).stem, source=path) for path in files]
            for run in runs: self.network(run)
            location_id = dialog.label.currentData()
            existing = next((loc for loc in self.project.locations if loc.id == location_id), None)
            if existing: existing.runs.extend(runs)
            else:
                label = dialog.label.currentText().strip() or f"P{len(self.project.locations) + 1}"
                self.project.locations.append(Location(label=label, x_m=dialog.x.value() / 100, y_m=dialog.y.value() / 100, runs=runs))
            self.refresh(); self.data_tabs.setCurrentIndex(1); self.location_table.selectRow(self.project.locations.index(existing) if existing else len(self.project.locations) - 1); self.plot_tabs.setCurrentIndex(1)
            self.statusBar().showMessage(f"Mapped {len(runs)} run(s) at {existing.label if existing else label}", 7000)
        except Exception as exc: self._error("Could not import measurement", exc)

    def refresh(self):
        selected = self.project.active_reference_id
        self.reference.blockSignals(True); self.reference.clear(); self.reference.addItem("(none — absolute only)", None)
        for ref in self.project.references: self.reference.addItem(f"Reference · {ref.name}", ref.id)
        for run in self.project.loose_runs: self.reference.addItem(f"Run Lab · {run.label}", run.id)
        index = self.reference.findData(selected); self.reference.setCurrentIndex(max(0, index)); self.reference.blockSignals(False)
        self.reference_table.setRowCount(len(self.project.references))
        for row, ref in enumerate(self.project.references):
            for col, value in enumerate((ref.name, ref.material, str(len(ref.runs)))): self.reference_table.setItem(row, col, QTableWidgetItem(value))
        self.loose_table.setRowCount(len(self.project.loose_runs))
        reference = self.reference_networks(); settings = self.settings()
        for row, run in enumerate(self.project.loose_runs):
            net = self.network(run); result = analyze(net, settings, reference); span = f"{net.frequency_hz[0] / 1e6:.3f}–{net.frequency_hz[-1] / 1e6:.3f} MHz"
            for col, value in enumerate((run.label, Path(run.source).name, self._number(result), span)): self.loose_table.setItem(row, col, QTableWidgetItem(value))
        self.refresh_results(); self.refresh_trace()

    def results(self):
        reference = self.reference_networks(); settings = self.settings(); rows = []
        for loc in self.project.locations:
            values = np.asarray([analyze(self.network(run), settings, reference) for run in loc.runs], dtype=float)
            finite = values[np.isfinite(values)]
            rows.append((loc, float(np.mean(finite)) if finite.size else np.nan, float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0))
        return rows

    def refresh_results(self):
        self.project.active_reference_id = self.reference.currentData()
        reference = self.reference_networks(); settings = self.settings()
        for row, run in enumerate(self.project.loose_runs):
            if self.loose_table.item(row, 2): self.loose_table.item(row, 2).setText(self._number(analyze(self.network(run), settings, reference)))
        rows = self.results(); self.location_table.setRowCount(len(rows))
        spots, finite_values = [], [value for _, value, _ in rows if np.isfinite(value)]
        low, high = (min(finite_values), max(finite_values)) if finite_values else (0.0, 1.0)
        if not self.auto_scale.isChecked(): low, high = self.scale_min.value(), self.scale_max.value()
        if high == low: high = low + 1.0
        cmap = pg.colormap.get("viridis")
        for row, (loc, mean, std) in enumerate(rows):
            values = (loc.label, f"{loc.x_m * 100:.3f}", f"{loc.y_m * 100:.3f}", "" if loc.row is None else str(loc.row), "" if loc.column is None else str(loc.column), str(len(loc.runs)), self._number(mean), self._number(std))
            for col, value in enumerate(values): self.location_table.setItem(row, col, QTableWidgetItem(value))
            normalized = 0 if not np.isfinite(mean) else (mean - low) / (high - low)
            spots.append({"pos": (loc.x_m * 100, loc.y_m * 100), "brush": pg.mkBrush(cmap.map(normalized)), "data": loc.label, "tip": f"{loc.label}: {self._number(mean)}"})
        self.heat_scatter.setData(spots)
        valid = [(loc.x_m * 100, loc.y_m * 100, value) for loc, value, _ in rows if np.isfinite(value)]
        if len(valid) >= 2:
            points = np.asarray(valid); x_pad = max(np.ptp(points[:, 0]) * .03, 1.0); y_pad = max(np.ptp(points[:, 1]) * .03, 1.0)
            x0, x1 = points[:, 0].min() - x_pad, points[:, 0].max() + x_pad; y0, y1 = points[:, 1].min() - y_pad, points[:, 1].max() + y_pad
            gx = np.linspace(x0, x1, 160); gy = np.linspace(y0, y1, 160); xx, yy = np.meshgrid(gx, gy)
            distance2 = (xx[..., None] - points[:, 0]) ** 2 + (yy[..., None] - points[:, 1]) ** 2
            weights = 1.0 / np.maximum(distance2, 1e-9)
            image = np.sum(weights * points[:, 2], axis=2) / np.sum(weights, axis=2)
            self.heat_image.setImage(image, levels=(low, high), autoLevels=False); self.heat_image.setColorMap(cmap); self.heat_image.setRect(QRectF(x0, y0, x1 - x0, y1 - y0)); self.heat_image.show()
        else: self.heat_image.hide()
        self.statusBar().showMessage(f"{len(rows)} locations · scale {self._number(low)} to {self._number(high)}")

    def refresh_trace(self):
        self.trace_plot.clear(); rows = sorted({item.row() for item in self.location_table.selectedItems()})
        selected: list[tuple[str, Run]] = []
        tab = self.data_tabs.currentIndex()
        if tab == 0:
            run_rows = sorted({item.row() for item in self.loose_table.selectedItems()})
            if not run_rows and self.project.loose_runs: run_rows = [0]
            selected = [(self.project.loose_runs[row].label, self.project.loose_runs[row]) for row in run_rows]
        elif tab == 1:
            if not rows and self.project.locations: rows = [0]
            selected = [(f"{self.project.locations[row].label} · {run.label}", run) for row in rows for run in self.project.locations[row].runs]
        else:
            ref_rows = sorted({item.row() for item in self.reference_table.selectedItems()})
            if not ref_rows and self.project.references: ref_rows = [0]
            selected = [(f"{self.project.references[row].name} · {run.label}", run) for row in ref_rows for run in self.project.references[row].runs]
        colors = ["#00b7ff", "#ff9d00", "#8bd450", "#ef476f"]
        for index, (label, run) in enumerate(selected[:12]):
            net = self.network(run); values = net.parameter(self.project.parameter); db = 20 * np.log10(np.maximum(np.abs(values), 1e-15))
            self.trace_plot.plot(net.frequency_hz, db, pen=pg.mkPen(colors[index % len(colors)], width=2), name=label)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export result table", "wall_survey_results.csv", "CSV (*.csv)")
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle); settings = self.settings()
            writer.writerow(["location", "x_m", "y_m", "repeat_count", "mean", "standard_deviation", "metric", "comparison", "center_hz", "bandwidth_hz", "reference"])
            for loc, mean, std in self.results(): writer.writerow([loc.label, loc.x_m, loc.y_m, len(loc.runs), mean, std, settings.metric.value, settings.comparison.value, settings.center_hz, settings.bandwidth_hz, self.reference.currentText()])
        self.statusBar().showMessage(f"Exported {path}", 5000)

    def export_heatmap(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export spatial map", "wall_survey_heatmap.png", "PNG image (*.png)")
        if path: self.heat_plot.grab().save(path); self.statusBar().showMessage(f"Exported {path}", 5000)

    @staticmethod
    def _number(value: float) -> str: return "—" if not np.isfinite(value) else f"{value:.6g}"

    def _error(self, title: str, exc: Exception): QMessageBox.critical(self, title, str(exc))
