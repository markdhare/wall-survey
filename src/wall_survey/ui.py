"""Main PySide6 user interface."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QHeaderView, QHBoxLayout, QInputDialog,
    QLabel, QMainWindow, QMessageBox, QSizePolicy, QSplitter, QStatusBar,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .metrics import AnalysisSettings, Comparison, Metric, analyze, trace_series
from .model import Location, Reference, Run, SurveyProject
from .project_io import load_project, save_project
from .touchstone import NetworkData, read_touchstone
from .acquisition_ui import AcquisitionDock


class LocationDialog(QDialog):
    def __init__(self, parent=None, title="Add measurement location"):
        super().__init__(parent)
        self.setWindowTitle(title)
        form = QFormLayout(self)
        self.label = QComboBox()
        self.label.setEditable(True)
        self.x = QDoubleSpinBox(); self.x.setRange(-100_000, 100_000); self.x.setDecimals(3); self.x.setSuffix(" cm")
        self.y = QDoubleSpinBox(); self.y.setRange(-100_000, 100_000); self.y.setDecimals(3); self.y.setSuffix(" cm")
        self.x.setButtonSymbols(QAbstractSpinBox.NoButtons); self.y.setButtonSymbols(QAbstractSpinBox.NoButtons)
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
        self.dirty = False
        self._updating_band = False
        self.setWindowTitle("Wall Survey — NanoVNA transmission mapping")
        self.setAnimated(False)
        self.resize(1400, 850)
        self._build_actions()
        self._build_ui()
        self.acquisition = AcquisitionDock(self); self.addDockWidget(Qt.RightDockWidgetArea, self.acquisition)
        self.acquisition.capture_ready.connect(self.route_capture)
        self.view_menu.addAction(self.acquisition.toggleViewAction())
        self._apply_style()
        self.refresh()
        self._set_dirty(False)

    def _build_actions(self):
        def action(text, slot, shortcut=None):
            item = QAction(text, self); item.triggered.connect(slot)
            if shortcut: item.setShortcut(shortcut)
            return item

        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(action("&New", self.new_project, QKeySequence.New))
        file_menu.addAction(action("&Open…", self.open_project, QKeySequence.Open))
        file_menu.addSeparator()
        file_menu.addAction(action("&Save", self.save_project, QKeySequence.Save))
        file_menu.addAction(action("Save &As…", self.save_project_as, QKeySequence.SaveAs))
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("Export")
        export_menu.addAction(action("Results CSV…", self.export_csv))
        export_menu.addAction(action("Heatmap Image…", self.export_heatmap))
        file_menu.addSeparator(); file_menu.addAction(action("E&xit", self.close, QKeySequence.Quit))

        import_menu = menu.addMenu("&Import")
        import_menu.addAction(action("&Grid CSV…", self.import_grid))
        import_menu.addAction(action("&Reference Runs…", self.add_reference))
        import_menu.addAction(action("&Loose Runs…", self.add_loose_runs))
        import_menu.addAction(action("&Mapped Runs…", self.add_location_run))

        map_menu = menu.addMenu("&Map")
        map_menu.addAction(action("&Add Grid Point…", self.add_grid_point, "Ctrl+Shift+N"))
        self.edit_location_action = action("&Edit Selected Grid Point…", self.edit_grid_point)
        map_menu.addAction(self.edit_location_action)
        map_menu.addSeparator()
        self.map_selected_action = action("Map Selected Run Lab Runs…", self.map_selected_runs)
        map_menu.addAction(self.map_selected_action)
        self.view_menu = menu.addMenu("&View")

    def _build_ui(self):
        outer = QWidget(); layout = QVBoxLayout(outer); layout.setContentsMargins(8, 8, 8, 8)
        self.guidance = QLabel("Start anywhere: add loose runs for quick comparison, add references for baselines, or import a grid for wall mapping.")
        self.guidance.setObjectName("guidance"); self.guidance.setFixedHeight(38); self.guidance.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed); layout.addWidget(self.guidance)
        controls = QHBoxLayout()
        # Do not call this ``self.metric``: QPaintDevice.metric() is a virtual
        # method that Qt calls internally while painting every widget.
        self.metric_combo = QComboBox(); self.metric_combo.addItems([item.value for item in Metric])
        self.comparison = QComboBox(); self.comparison.addItems([item.value for item in Comparison])
        self.reference = QComboBox()
        self.frequency = QDoubleSpinBox(); self.frequency.setRange(0.001, 100_000); self.frequency.setValue(900); self.frequency.setDecimals(3); self.frequency.setSuffix(" MHz")
        self.bandwidth = QDoubleSpinBox(); self.bandwidth.setRange(0, 100_000); self.bandwidth.setValue(0); self.bandwidth.setDecimals(3); self.bandwidth.setSuffix(" MHz")
        self.auto_scale = QCheckBox("Auto scale"); self.auto_scale.setChecked(True)
        self.scale_min = QDoubleSpinBox(); self.scale_min.setRange(-1e12, 1e12); self.scale_min.setDecimals(4); self.scale_min.setValue(-60)
        self.scale_max = QDoubleSpinBox(); self.scale_max.setRange(-1e12, 1e12); self.scale_max.setDecimals(4); self.scale_max.setValue(0)
        for spinbox in (self.frequency, self.bandwidth, self.scale_min, self.scale_max):
            spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.metric_combo.setToolTip("Quantity plotted and reduced over the selected frequency point or band.")
        self.comparison.setToolTip("Show an absolute measurement or transform it relative to the selected baseline.")
        self.reference.setToolTip("Reference group or Run Lab file used as the comparison baseline.")
        self.frequency.setToolTip("Center of the highlighted analysis point or band.")
        self.bandwidth.setToolTip("Analysis width. Zero selects a single interpolated frequency.")
        for label, widget in [("Metric", self.metric_combo), ("Comparison", self.comparison), ("Baseline", self.reference), ("Center", self.frequency), ("Bandwidth (0 = point)", self.bandwidth)]:
            controls.addWidget(QLabel(label)); controls.addWidget(widget)
        controls.addStretch()
        layout.addLayout(controls)
        self.scale_panel = QWidget(); scale_controls = QHBoxLayout(self.scale_panel); scale_controls.setContentsMargins(0, 0, 0, 0)
        scale_controls.addWidget(self.auto_scale); scale_controls.addWidget(QLabel("Color minimum")); scale_controls.addWidget(self.scale_min); scale_controls.addWidget(QLabel("Color maximum")); scale_controls.addWidget(self.scale_max); scale_controls.addStretch(); layout.addWidget(self.scale_panel)
        splitter = QSplitter(Qt.Horizontal)
        self.data_tabs = QTabWidget()
        self.location_table = QTableWidget(0, 8); self.location_table.setHorizontalHeaderLabels(["Label", "X (cm)", "Y (cm)", "Row", "Column", "Repeats", "Mean", "Std. dev."])
        self.location_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.location_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.reference_table = QTableWidget(0, 3); self.reference_table.setHorizontalHeaderLabels(["Reference", "Material / condition", "Runs"]); self.reference_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.reference_table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.reference_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.loose_table = QTableWidget(0, 4); self.loose_table.setHorizontalHeaderLabels(["Run", "Source file", "Current result", "Frequency span"]); self.loose_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.loose_table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.loose_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for table in (self.location_table, self.reference_table, self.loose_table):
            table.setAlternatingRowColors(True); table.setShowGrid(False); table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True); table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.data_tabs.addTab(self.loose_table, "Run Lab"); self.data_tabs.addTab(self.location_table, "Wall Map"); self.data_tabs.addTab(self.reference_table, "References")
        splitter.addWidget(self.data_tabs)
        self.plot_tabs = QTabWidget()
        self.heat_plot = pg.PlotWidget(); self.heat_plot.setLabel("bottom", "X — front view", units="cm"); self.heat_plot.setLabel("left", "Y", units="cm"); self.heat_plot.showGrid(x=True, y=True, alpha=0.25); self.heat_plot.setAspectLocked(True)
        self.heat_image = pg.ImageItem(axisOrder="row-major"); self.heat_plot.addItem(self.heat_image)
        self.heat_scatter = pg.ScatterPlotItem(size=14, pen=pg.mkPen("w", width=1)); self.heat_plot.addItem(self.heat_scatter)
        self.trace_plot = pg.PlotWidget(); self.trace_plot.setLabel("bottom", "Frequency", units="MHz"); self.trace_plot.setLabel("left", "Magnitude", units="dB"); self.trace_plot.showGrid(x=True, y=True, alpha=0.25); self.trace_plot.addLegend(offset=(12, 12))
        self.plot_tabs.addTab(self.trace_plot, "Run comparison"); self.plot_tabs.addTab(self.heat_plot, "Wall heatmap")
        splitter.addWidget(self.plot_tabs); splitter.setSizes([520, 850]); layout.addWidget(splitter)
        self.setCentralWidget(outer); self.setStatusBar(QStatusBar())
        for widget in (self.metric_combo, self.comparison, self.reference): widget.currentIndexChanged.connect(self.refresh_results)
        self.frequency.valueChanged.connect(self.refresh_results); self.bandwidth.valueChanged.connect(self.refresh_results)
        self.auto_scale.toggled.connect(self.refresh_results); self.scale_min.valueChanged.connect(self.refresh_results); self.scale_max.valueChanged.connect(self.refresh_results)
        self.location_table.itemSelectionChanged.connect(self.refresh_trace)
        self.location_table.itemSelectionChanged.connect(self._update_run_actions)
        self.location_table.itemDoubleClicked.connect(lambda _item: self.edit_grid_point())
        self.reference_table.itemSelectionChanged.connect(self.refresh_trace); self.loose_table.itemSelectionChanged.connect(self.refresh_trace); self.loose_table.itemSelectionChanged.connect(self._update_run_actions); self.data_tabs.currentChanged.connect(self.refresh_trace); self.data_tabs.currentChanged.connect(self._update_run_actions)
        self.plot_tabs.currentChanged.connect(self._update_control_states)
        self._update_control_states()
        self._update_run_actions()

    def _update_control_states(self):
        comparison = Comparison(self.comparison.currentText())
        needs_baseline = comparison != Comparison.ABSOLUTE
        # Keep Baseline selectable even for absolute plots so users can choose
        # it before switching to a normalized comparison.
        self.reference.setEnabled(True)
        self.metric_combo.setEnabled(comparison in {Comparison.ABSOLUTE, Comparison.COMPLEX_RATIO_DB})
        manual_scale = not self.auto_scale.isChecked()
        self.scale_min.setEnabled(manual_scale); self.scale_max.setEnabled(manual_scale)
        self.scale_panel.setVisible(self.plot_tabs.currentIndex() == 1)
        if needs_baseline and self.reference.currentData() is None:
            self.guidance.setText("Choose a Baseline to calculate this comparison. Add a reference group or a loose Run Lab file if needed.")
        else:
            self.guidance.setText("Start anywhere: add loose runs for quick comparison, add references for baselines, or import a grid for wall mapping.")

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
            QDockWidget { color: #dce8f2; font-weight: 600; }
            QDockWidget::title { background: #21313e; padding: 7px; }
            QGroupBox { border: 1px solid #30485a; border-radius: 4px; margin-top: 9px; padding-top: 8px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #9ed9ec; }
            QLineEdit, QSpinBox { background: #1b2934; border: 1px solid #3b566a; border-radius: 3px; padding: 4px; }
            QPushButton { background: #243646; border: 1px solid #355064; border-radius: 4px; padding: 6px 9px; }
            QPushButton:hover { background: #2d5268; border-color: #48b9d6; }
            QPushButton#captureButton { background: #176d78; border-color: #40c2d0; font-weight: 700; padding: 9px; }
            QLabel#secondary { color: #8eacba; font-size: 11px; }
            QLabel#quality[warning="true"], QLabel[error="true"] { color: #ff7373; }
            QLabel#quality[warning="false"], QLabel[connected="true"] { color: #6ed69b; }
        """)
        pg.setConfigOption("background", "#10171e"); pg.setConfigOption("foreground", "#c7dae5")

    def settings(self) -> AnalysisSettings:
        return AnalysisSettings(Metric(self.metric_combo.currentText()), Comparison(self.comparison.currentText()), self.frequency.value() * 1e6, self.bandwidth.value() * 1e6, self.project.parameter)

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
        if not self._confirm_discard_changes(): return
        self.project = SurveyProject(); self.network_cache.clear(); self._set_dirty(False); self.refresh(); self.statusBar().showMessage("New project", 3000)

    def open_project(self):
        if not self._confirm_discard_changes(): return
        path, _ = QFileDialog.getOpenFileName(self, "Open Wall Survey", "", "Wall Survey (*.wallscan)")
        if not path: return
        try: self.project = load_project(path); self.network_cache.clear(); self._set_dirty(False); self.refresh(); self.statusBar().showMessage(f"Opened {path}", 5000)
        except Exception as exc: self._error("Could not open project", exc)

    def save_project(self):
        path = str(self.project.project_path or "")
        if not path: return self.save_project_as()
        return self._save_to(path)

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Wall Survey As", str(self.project.project_path or f"{self.project.name}.wallscan"), "Wall Survey (*.wallscan)")
        if not path: return False
        return self._save_to(path)

    def _save_to(self, path):
        try:
            saved = save_project(self.project, path); self._set_dirty(False)
            self.statusBar().showMessage(f"Saved {saved}", 5000); return True
        except Exception as exc: self._error("Could not save project", exc)
        return False

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
            self._set_dirty()
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
            self._set_dirty()
            self.loose_table.clearSelection()
            for row in range(len(self.project.loose_runs) - len(runs), len(self.project.loose_runs)): self.loose_table.selectRow(row)
            self.plot_tabs.setCurrentIndex(0); self.statusBar().showMessage(f"Added {len(runs)} off-grid run(s) to Run Lab", 7000)
        except Exception as exc: self._error("Could not import run", exc)

    def map_selected_runs(self):
        rows = sorted({item.row() for item in self.loose_table.selectedItems()})
        if not rows:
            QMessageBox.information(self, "Map Run Lab runs", "Select one or more Run Lab rows first.")
            return
        runs = [self.project.loose_runs[row] for row in rows]
        dialog = LocationDialog(self)
        self._configure_location_dialog(dialog)
        if dialog.exec() != QDialog.Accepted: return
        selected_id = dialog.label.currentData(); entered_label = dialog.label.currentText().strip()
        existing = next((location for location in self.project.locations if location.id == selected_id and location.label == entered_label), None)
        if existing:
            existing.runs.extend(runs); location = existing
        else:
            location = Location(label=entered_label or f"P{len(self.project.locations) + 1}", x_m=dialog.x.value() / 100, y_m=dialog.y.value() / 100, runs=list(runs))
            self.project.locations.append(location)
        moved_ids = {run.id for run in runs}; self.project.loose_runs = [run for run in self.project.loose_runs if run.id not in moved_ids]
        if self.project.active_reference_id in moved_ids: self.project.active_reference_id = None
        self._set_dirty()
        self.refresh(); self.data_tabs.setCurrentIndex(1); self.plot_tabs.setCurrentIndex(1); self.location_table.selectRow(self.project.locations.index(location))
        self.statusBar().showMessage(f"Moved {len(runs)} Run Lab run(s) to map location '{location.label}'", 7000)

    def _update_run_actions(self):
        if hasattr(self, "map_selected_action"):
            self.map_selected_action.setEnabled(bool(self.loose_table.selectedItems()) and self.data_tabs.currentIndex() == 0)
        if hasattr(self, "edit_location_action"):
            self.edit_location_action.setEnabled(bool(self.location_table.selectedItems()) and self.data_tabs.currentIndex() == 1)

    def _configure_location_dialog(self, dialog: LocationDialog):
        for location in self.project.locations: dialog.label.addItem(location.label, location.id)

        def update_coordinates():
            location_id = dialog.label.currentData(); text = dialog.label.currentText()
            existing = next((item for item in self.project.locations if item.id == location_id and item.label == text), None)
            if existing:
                dialog.x.setValue(existing.x_m * 100); dialog.y.setValue(existing.y_m * 100)
            dialog.x.setEnabled(existing is None); dialog.y.setEnabled(existing is None)

        dialog.label.currentIndexChanged.connect(update_coordinates); dialog.label.editTextChanged.connect(update_coordinates)
        update_coordinates()

    def add_grid_point(self):
        dialog = LocationDialog(self, "Add grid point")
        if dialog.exec() != QDialog.Accepted: return
        label = dialog.label.currentText().strip() or f"P{len(self.project.locations) + 1}"
        if any(item.label == label for item in self.project.locations):
            QMessageBox.warning(self, "Duplicate grid point", f"A grid point named '{label}' already exists.")
            return
        location = Location(label=label, x_m=dialog.x.value() / 100, y_m=dialog.y.value() / 100)
        self.project.locations.append(location); self._set_dirty(); self.refresh()
        self.data_tabs.setCurrentIndex(1); self.location_table.selectRow(len(self.project.locations) - 1)

    def edit_grid_point(self):
        rows = sorted({item.row() for item in self.location_table.selectedItems()})
        if len(rows) != 1: return
        location = self.project.locations[rows[0]]
        dialog = LocationDialog(self, "Edit grid point")
        dialog.label.setEditText(location.label); dialog.x.setValue(location.x_m * 100); dialog.y.setValue(location.y_m * 100)
        if dialog.exec() != QDialog.Accepted: return
        label = dialog.label.currentText().strip() or location.label
        if any(item is not location and item.label == label for item in self.project.locations):
            QMessageBox.warning(self, "Duplicate grid point", f"A grid point named '{label}' already exists.")
            return
        location.label = label; location.x_m = dialog.x.value() / 100; location.y_m = dialog.y.value() / 100
        self._set_dirty(); self.refresh(); self.data_tabs.setCurrentIndex(1); self.location_table.selectRow(rows[0])

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
            self._set_dirty()
            self.refresh(); self.statusBar().showMessage(f"Imported {len(rows)} grid locations", 5000)
        except Exception as exc: self._error("Could not import grid", exc)

    def add_location_run(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add measurement runs", "", "Touchstone (*.s2p *.s1p)")
        if not files: return
        dialog = LocationDialog(self)
        self._configure_location_dialog(dialog)
        if dialog.exec() != QDialog.Accepted: return
        try:
            runs = [Run(label=Path(path).stem, source=path) for path in files]
            for run in runs: self.network(run)
            location_id = dialog.label.currentData(); entered_label = dialog.label.currentText().strip()
            existing = next((loc for loc in self.project.locations if loc.id == location_id and loc.label == entered_label), None)
            if existing: existing.runs.extend(runs)
            else:
                label = dialog.label.currentText().strip() or f"P{len(self.project.locations) + 1}"
                self.project.locations.append(Location(label=label, x_m=dialog.x.value() / 100, y_m=dialog.y.value() / 100, runs=runs))
            self._set_dirty()
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
        if hasattr(self, "acquisition"): self.acquisition.set_targets(self.project.references, self.project.locations)
        self.refresh_results(); self.refresh_trace()

    def route_capture(self, result, path: str, destination: str, target_id: str, label: str):
        """Attach an already-preserved raw capture to the selected project area."""
        run = Run(label=label or Path(path).stem, source=path)
        routed = "Run Lab"
        if destination == "new_reference":
            name, accepted = QInputDialog.getText(self, "New reference group", "Reference condition name")
            if accepted and name.strip():
                reference = Reference(name=name.strip(), runs=[run]); self.project.references.append(reference); routed = f"reference '{reference.name}'"
            else: self.project.loose_runs.append(run)
        elif destination == "existing_reference":
            reference = self.project.reference(target_id)
            if reference: reference.runs.append(run); routed = f"reference '{reference.name}'"
            else: self.project.loose_runs.append(run)
        elif destination == "new_location":
            dialog = LocationDialog(self)
            if dialog.exec() == QDialog.Accepted:
                location_label = dialog.label.currentText().strip() or f"P{len(self.project.locations) + 1}"
                location = Location(label=location_label, x_m=dialog.x.value() / 100, y_m=dialog.y.value() / 100, runs=[run]); self.project.locations.append(location); routed = f"map location '{location.label}'"
            else: self.project.loose_runs.append(run)
        elif destination in {"existing_location", "next_empty"}:
            location = next((item for item in self.project.locations if item.id == target_id), None)
            if location: location.runs.append(run); routed = f"map location '{location.label}'"
            else: self.project.loose_runs.append(run)
        else:
            self.project.loose_runs.append(run)
        self._set_dirty()
        self.refresh()
        if destination in {"new_reference", "existing_reference"} and routed != "Run Lab": self.data_tabs.setCurrentIndex(2)
        elif destination in {"new_location", "existing_location", "next_empty"} and routed != "Run Lab": self.data_tabs.setCurrentIndex(1); self.plot_tabs.setCurrentIndex(1)
        else: self.data_tabs.setCurrentIndex(0); self.plot_tabs.setCurrentIndex(0)
        warning = f" · {len(result.quality_flags)} quality warning(s)" if result.quality_flags else ""
        self.statusBar().showMessage(f"Capture preserved and routed to {routed}{warning}", 10000)

    def results(self):
        reference = self.reference_networks(); settings = self.settings(); rows = []
        for loc in self.project.locations:
            values = np.asarray([analyze(self.network(run), settings, reference) for run in loc.runs], dtype=float)
            finite = values[np.isfinite(values)]
            rows.append((loc, float(np.mean(finite)) if finite.size else np.nan, float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0))
        return rows

    def refresh_results(self):
        self._update_control_states()
        selected_reference = self.reference.currentData()
        if self.project.active_reference_id != selected_reference:
            self.project.active_reference_id = selected_reference; self._set_dirty()
        reference = self.reference_networks(); settings = self.settings()
        for row, run in enumerate(self.project.loose_runs):
            if self.loose_table.item(row, 2): self.loose_table.item(row, 2).setText(self._number(analyze(self.network(run), settings, reference)))
        result_name = self._result_name(settings)
        self.loose_table.horizontalHeaderItem(2).setText(result_name)
        self.location_table.horizontalHeaderItem(6).setText(f"Mean · {result_name}")
        self.location_table.horizontalHeaderItem(7).setText("Std. dev.")
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
            spots.append({"pos": (loc.x_m * 100, loc.y_m * 100), "brush": pg.mkBrush(cmap.map(normalized)), "data": {"label": loc.label, "value": mean}})
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
        self.refresh_trace()

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
        settings = self.settings(); reference = self.reference_networks()
        colors = ["#00b7ff", "#ff9d00", "#8bd450", "#ef476f", "#b388ff", "#f7d154"]
        axis_label, units = "Result", ""
        for index, (label, run) in enumerate(selected[:12]):
            series = trace_series(self.network(run), settings, reference)
            axis_label, units = series.axis_label, series.units
            finite = np.isfinite(series.values)
            self.trace_plot.plot(series.frequency_hz[finite] / 1e6, series.values[finite], pen=pg.mkPen(colors[index % len(colors)], width=2), name=label)
        self.trace_plot.setLabel("left", axis_label, units=units or None)
        baseline = self.reference.currentText() if settings.comparison != Comparison.ABSOLUTE else "No baseline"
        self.trace_plot.setTitle(f"{self._result_name(settings)} · {baseline}", color="#bdeeff", size="10pt")
        center_mhz = settings.center_hz / 1e6
        if settings.bandwidth_hz > 0:
            half_mhz = settings.bandwidth_hz / 2e6
            region = pg.LinearRegionItem((center_mhz - half_mhz, center_mhz + half_mhz), movable=True, brush=pg.mkBrush(65, 185, 215, 35), pen=pg.mkPen(65, 185, 215, 150))
            region.setToolTip("Drag the band or either edge to change the analysis center and bandwidth")
            region.sigRegionChangeFinished.connect(lambda: self._band_region_changed(region))
            region.setZValue(-10); self.trace_plot.addItem(region)
        else:
            marker = pg.InfiniteLine(center_mhz, angle=90, movable=False, pen=pg.mkPen(65, 185, 215, 190, width=2))
            marker.setZValue(-10); self.trace_plot.addItem(marker)

    def _band_region_changed(self, region):
        if self._updating_band: return
        low, high = sorted(region.getRegion())
        self._updating_band = True
        self.frequency.setValue((low + high) / 2); self.bandwidth.setValue(high - low)
        self._updating_band = False

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

    @staticmethod
    def _result_name(settings: AnalysisSettings) -> str:
        if settings.comparison == Comparison.DELTA_DB: return "Magnitude delta (dB)"
        if settings.comparison == Comparison.PHASE_DELTA: return "Phase delta (deg)"
        if settings.comparison == Comparison.COMPLEX_RATIO_DB: return f"Normalized {settings.metric.value}"
        return settings.metric.value

    def _error(self, title: str, exc: Exception): QMessageBox.critical(self, title, str(exc))

    def _set_dirty(self, dirty=True):
        self.dirty = dirty
        name = self.project.project_path.name if self.project.project_path else self.project.name
        self.setWindowTitle(f"{'*' if dirty else ''}{name} — Wall Survey")
        self.setWindowModified(dirty)

    def _confirm_discard_changes(self):
        if not self.dirty: return True
        answer = QMessageBox.warning(
            self, "Unsaved changes", "Save changes to the current Wall Survey project?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save,
        )
        if answer == QMessageBox.Save: return bool(self.save_project())
        return answer == QMessageBox.Discard

    def closeEvent(self, event):
        if not self._confirm_discard_changes():
            event.ignore(); return
        self.acquisition.shutdown()
        event.accept()
