"""Regression tests for Qt integration and visible run-table updates."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pyqtgraph as pg
from PySide6.QtGui import QPaintDevice
from PySide6.QtWidgets import QApplication

from wall_survey.metrics import Comparison
from wall_survey.model import Run
from wall_survey.ui import MainWindow


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
    window.close()
