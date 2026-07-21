"""Regression tests for Qt integration and visible run-table updates."""

import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QTimer
from PySide6.QtGui import QPaintDevice
from PySide6.QtWidgets import QApplication

from wall_survey.metrics import Comparison
from wall_survey.acquisition.base import AcquisitionResult, SweepSettings, VnaIdentity
from wall_survey.model import Location, Run
from wall_survey.touchstone import read_touchstone
from wall_survey.ui import LocationDialog, MainWindow


EXAMPLES = Path(__file__).parents[1] / "example_s2p_files"


def test_qt_metric_virtual_method_and_run_lab_refresh():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()

    # Qt calls this virtual method during paint/layout. A widget attribute named
    # ``metric`` used to shadow it and break redraws across the whole window.
    assert window.metric(QPaintDevice.PdmWidth) >= 0

    run = Run(label="Visible run", source=str(EXAMPLES / "example_baseline.s2p"))
    window.project.loose_runs.append(run)
    window.refresh()
    app.processEvents()

    assert window.loose_table.rowCount() == 1
    assert window.loose_table.item(0, 0).text() == "Visible run"
    assert window.loose_table.item(0, 2).text() != ""
    window.close()


def test_trace_updates_for_baseline_comparison_and_band():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    baseline = Run(label="Baseline", source=str(EXAMPLES / "example_baseline.s2p"))
    obstacle = Run(label="Obstacle", source=str(EXAMPLES / "example_with_obstacle.s2p"))
    window.project.loose_runs.extend([baseline, obstacle])
    window.refresh()
    window.loose_table.selectRow(1)
    absolute_y = window.trace_plot.listDataItems()[0].yData.copy()

    window.reference.setCurrentIndex(window.reference.findData(baseline.id))
    window.comparison.setCurrentText(Comparison.DELTA_DB.value)
    window.bandwidth.setValue(20.0)
    app.processEvents()

    compared_y = window.trace_plot.listDataItems()[0].yData
    assert not np.allclose(absolute_y, compared_y)
    assert "Magnitude delta from baseline" in window.trace_plot.getAxis("left").labelText
    assert any(isinstance(item, pg.LinearRegionItem) for item in window.trace_plot.plotItem.items)
    assert not window.metric_combo.isEnabled()
    window.plot_tabs.setCurrentIndex(1)
    app.processEvents()
    assert not window.scale_panel.isHidden()
    window.plot_tabs.setCurrentIndex(0)
    assert window.scale_panel.isHidden()
    window._set_dirty(False)
    window.close()


def test_acquisition_controls_enable_after_connection_finishes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.acquisition.device = SimpleNamespace(connected=True, disconnect=lambda: None)
    window.acquisition._set_connected(True)
    window.acquisition._set_busy(False)
    app.processEvents()
    assert window.acquisition.capture_button.isEnabled()
    assert window.acquisition.connect_button.text() == "Disconnect"
    window.close()


def test_preserved_capture_routes_to_next_empty_grid_location():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    location = Location(label="R1C1", x_m=0.1, y_m=0.2)
    window.project.locations.append(location)
    path = EXAMPLES / "example_baseline.s2p"
    result = AcquisitionResult(
        read_touchstone(path),
        VnaIdentity("test", "COM10", "NanoVNA-H", "test", "test"),
        SweepSettings(),
        datetime.now(timezone.utc),
    )
    window.acquisition.destination.setCurrentIndex(window.acquisition.destination.findData("next_empty"))
    window.route_capture(result, str(path), "next_empty", location.id, "Guided run")
    app.processEvents()
    assert location.runs[0].label == "Guided run"
    assert window.data_tabs.currentIndex() == 1
    assert "R1C1" in window.acquisition.target_hint.text() or "No empty" in window.acquisition.target_hint.text()
    window._set_dirty(False)
    window.close()


def test_selected_run_lab_run_can_be_moved_to_new_map_location():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    run = Run(label="Exploratory", source=str(EXAMPLES / "example_baseline.s2p"))
    window.project.loose_runs.append(run); window.refresh(); window.loose_table.selectRow(0)

    def complete_dialog():
        dialog = next(widget for widget in app.topLevelWidgets() if isinstance(widget, LocationDialog))
        dialog.label.setEditText("Mapped later"); dialog.x.setValue(25); dialog.y.setValue(80); dialog.accept()

    QTimer.singleShot(0, complete_dialog)
    window.map_selected_runs()
    assert not window.project.loose_runs
    assert window.project.locations[0].runs[0].id == run.id
    assert window.project.locations[0].x_m == 0.25
    assert window.project.locations[0].y_m == 0.8
    window._set_dirty(False)
    window.close()


def test_typed_location_label_does_not_reuse_combo_item_id(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    first = Location(label="First", x_m=0.1, y_m=0.2)
    window.project.locations.append(first); window.refresh()
    monkeypatch.setattr(
        "wall_survey.ui.QFileDialog.getOpenFileNames",
        lambda *args, **kwargs: ([str(EXAMPLES / "example_baseline.s2p")], ""),
    )

    def complete_dialog():
        dialog = next(widget for widget in app.topLevelWidgets() if isinstance(widget, LocationDialog))
        dialog.label.setEditText("Second"); dialog.x.setValue(30); dialog.y.setValue(40); dialog.accept()

    QTimer.singleShot(0, complete_dialog)
    window.add_location_run()
    assert [location.label for location in window.project.locations] == ["First", "Second"]
    assert not first.runs
    assert window.project.locations[1].runs
    window._set_dirty(False); window.close()


def test_standard_menus_and_project_title_are_present():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert [action.text().replace("&", "") for action in window.menuBar().actions()] == ["File", "Import", "Map", "View"]
    assert "Untitled wall survey" in window.windowTitle()
    window.close()
