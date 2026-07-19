"""Regression tests for Qt integration and visible run-table updates."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPaintDevice
from PySide6.QtWidgets import QApplication

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
