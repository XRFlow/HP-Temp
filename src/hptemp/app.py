# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import csv
import math
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

try:
    from PyQt6 import QtCharts

    HAS_CHARTS = True
except ImportError:  # pragma: no cover - optional dependency
    QtCharts = None
    HAS_CHARTS = False

from . import __license__, __version__
from .sensors import (
    collect_readings,
    celsius_to_fahrenheit,
    format_sensor_value,
    humanize,
    reading_key,
)
from .ui import (
    COLOR_ACCENT,
    COLOR_BG,
    COLOR_BORDER,
    COLOR_MUTED,
    COLOR_SURFACE,
    COLOR_TEXT,
    COLOR_WARN,
    MetricStrip,
    app_icon,
    apply_theme,
    format_compact_value,
    reading_accent,
)
from .settings import (
    ALERT_COOLDOWN_MAX,
    ALERT_COOLDOWN_MIN,
    ALERT_TEMP_MAX,
    ALERT_TEMP_MIN,
    LOG_INTERVAL_MAX,
    LOG_INTERVAL_MIN,
    REFRESH_MS_MAX,
    REFRESH_MS_MIN,
    TOOLTIP_LIMIT_MAX,
    TOOLTIP_LIMIT_MIN,
    Settings,
    load_settings,
    logs_dir,
    save_settings,
)


HISTORY_SECONDS = 15 * 60
SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
WORKER_SHUTDOWN_MS = 10_000
ALL_TYPES = "All types"
TYPE_SORT = {
    "Temperature": 0,
    "GPU Temperature": 1,
    "Fan": 2,
    "GPU Fan": 3,
    "Power": 4,
    "Voltage": 5,
    "Current": 6,
    "Humidity": 7,
}


class SensorTableItem(QtWidgets.QTableWidgetItem):
    def __lt__(self, other: QtWidgets.QTableWidgetItem) -> bool:
        left = self.data(SORT_ROLE)
        right = other.data(SORT_ROLE) if other is not None else None
        if left is not None and right is not None:
            try:
                return left < right
            except TypeError:
                pass
        return super().__lt__(other)


class SensorWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object, str)

    @QtCore.pyqtSlot()
    def collect(self) -> None:
        error = ""
        readings = []
        try:
            readings = collect_readings()
        except Exception as exc:
            error = str(exc) or exc.__class__.__name__
            readings = []
        self.finished.emit(readings, error)


class HistoryChart(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChartPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._heading = QtWidgets.QLabel("Select a sensor to view history")
        self._heading.setObjectName("ChartHeading")
        layout.addWidget(self._heading)

        if not HAS_CHARTS:
            self._heading.hide()
            self._label = QtWidgets.QLabel(
                "Install python3-pyqt6.qtcharts to enable history graphs.", self
            )
            self._label.setObjectName("Placeholder")
            self._label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._label)
            self.setMaximumHeight(56)
            self._chart_view = None
            return

        self._series = QtCharts.QLineSeries()
        pen = QtGui.QPen(QtGui.QColor(COLOR_ACCENT))
        pen.setWidth(2)
        self._series.setPen(pen)
        self._chart = QtCharts.QChart()
        self._chart.addSeries(self._series)
        self._chart.legend().hide()
        self._chart.setBackgroundBrush(QtGui.QColor(COLOR_SURFACE))
        self._chart.setPlotAreaBackgroundBrush(QtGui.QColor(COLOR_SURFACE))
        self._chart.setPlotAreaBackgroundVisible(True)
        self._chart.setBackgroundRoundness(10)
        self._chart.setTitle("")
        self._chart.setMargins(QtCore.QMargins(8, 8, 12, 8))
        self._axis_x = QtCharts.QValueAxis()
        self._axis_y = QtCharts.QValueAxis()
        self._axis_x.setTitleText("Seconds ago")
        self._axis_x.setRange(-HISTORY_SECONDS, 0)
        self._axis_x.setTickCount(7)
        self._axis_y.setLabelFormat("%.1f")
        for axis in (self._axis_x, self._axis_y):
            axis.setLabelsColor(QtGui.QColor(COLOR_MUTED))
            axis.setTitleBrush(QtGui.QColor(COLOR_MUTED))
            axis.setGridLineColor(QtGui.QColor(COLOR_BORDER))
            axis.setLinePenColor(QtGui.QColor(COLOR_BORDER))
        self._chart.addAxis(self._axis_x, QtCore.Qt.AlignmentFlag.AlignBottom)
        self._chart.addAxis(self._axis_y, QtCore.Qt.AlignmentFlag.AlignLeft)
        self._series.attachAxis(self._axis_x)
        self._series.attachAxis(self._axis_y)
        self._chart_view = QtCharts.QChartView(self._chart)
        self._chart_view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self._chart_view.setBackgroundBrush(QtGui.QColor(COLOR_SURFACE))
        self._chart_view.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        layout.addWidget(self._chart_view, 1)

    def update_series(self, history: list[tuple[float, float]], label: str, unit: str) -> None:
        self._heading.setText(label or "Select a sensor to view history")
        if not HAS_CHARTS or self._chart_view is None:
            return
        if not history:
            self._series.clear()
            return

        now = time.time()
        points = [
            QtCore.QPointF(ts - now, value)
            for ts, value in history
            if math.isfinite(value)
        ]
        if not points:
            self._series.clear()
            return
        self._series.replace(points)
        values = [point.y() for point in points]
        min_value = min(values)
        max_value = max(values)
        pad = max(0.5, (max_value - min_value) * 0.12)
        if min_value == max_value:
            pad = 1
        self._axis_y.setRange(min_value - pad, max_value + pad)
        self._axis_y.setTitleText(unit)


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About HPTemp")
        self.setMinimumWidth(420)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        title = QtWidgets.QLabel(f"HPTemp {__version__}")
        title.setObjectName("AppTitle")
        subtitle = QtWidgets.QLabel("HP Z workstation sensor monitor")
        subtitle.setObjectName("AppSubtitle")
        body = QtWidgets.QLabel(
            "Copyright (C) 2026 XRFlow\n"
            "support@xrflows.com\n\n"
            "This program is free software: you can redistribute it and/or modify "
            "it under the terms of the GNU General Public License as published by "
            "the Free Software Foundation, either version 3 of the License, or "
            "(at your option) any later version.\n\n"
            "This program comes with ABSOLUTELY NO WARRANTY.\n\n"
            f"License: {__license__}"
        )
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(body)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        license_btn = buttons.addButton(
            "View license", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole
        )
        license_btn.clicked.connect(self._open_license)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _open_license(self) -> None:
        path = _license_file()
        if path is None:
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl("https://www.gnu.org/licenses/gpl-3.0.html")
            )
            return
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))


class SettingsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        settings: Settings,
        readings: list,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("HPTemp Settings")
        self.setMinimumWidth(520)
        self._settings = settings.copy()
        self._readings = readings

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)

        display = QtWidgets.QGroupBox("Display and tray")
        display_form = QtWidgets.QFormLayout(display)
        display_form.setHorizontalSpacing(16)
        display_form.setVerticalSpacing(10)

        self._refresh_ms = QtWidgets.QSpinBox()
        self._refresh_ms.setRange(REFRESH_MS_MIN, REFRESH_MS_MAX)
        self._refresh_ms.setSingleStep(250)
        self._refresh_ms.setSuffix(" ms")
        self._refresh_ms.setValue(settings.refresh_ms)
        display_form.addRow("Refresh every", self._refresh_ms)

        self._tooltip_mode = QtWidgets.QComboBox()
        self._tooltip_mode.addItem("Hottest sensors", "hottest")
        self._tooltip_mode.addItem("Favorite sensors", "favorites")
        mode_index = self._tooltip_mode.findData(settings.tooltip_mode)
        if mode_index >= 0:
            self._tooltip_mode.setCurrentIndex(mode_index)
        display_form.addRow("Tray tooltip", self._tooltip_mode)

        self._tooltip_limit = QtWidgets.QSpinBox()
        self._tooltip_limit.setRange(TOOLTIP_LIMIT_MIN, TOOLTIP_LIMIT_MAX)
        self._tooltip_limit.setValue(settings.tooltip_limit)
        display_form.addRow("Tooltip items", self._tooltip_limit)

        self._tray_sensor = QtWidgets.QComboBox()
        self._tray_sensor.addItem("Auto (hottest °C)", "")
        for reading in self._readings:
            if reading.unit != "°C":
                continue
            label = f"{_display_name(reading)}"
            self._tray_sensor.addItem(label, reading_key(reading))
        if settings.tray_sensor_key:
            index = self._tray_sensor.findData(settings.tray_sensor_key)
            if index < 0:
                self._tray_sensor.addItem(
                    "Last selected sensor (unavailable)", settings.tray_sensor_key
                )
                index = self._tray_sensor.findData(settings.tray_sensor_key)
            if index >= 0:
                self._tray_sensor.setCurrentIndex(index)
        display_form.addRow("Tray icon sensor", self._tray_sensor)

        self._icon_temp_unit = QtWidgets.QComboBox()
        self._icon_temp_unit.addItems(["C", "F"])
        if settings.icon_temp_unit.upper() == "F":
            self._icon_temp_unit.setCurrentText("F")
        display_form.addRow("Temperature unit", self._icon_temp_unit)

        alerts = QtWidgets.QGroupBox("Alerts")
        alerts_form = QtWidgets.QFormLayout(alerts)
        alerts_form.setHorizontalSpacing(16)
        alerts_form.setVerticalSpacing(10)

        self._alerts_enabled = QtWidgets.QCheckBox("Enable temperature alerts")
        self._alerts_enabled.setChecked(settings.alerts_enabled)
        alerts_form.addRow(self._alerts_enabled)

        self._alert_scope = QtWidgets.QComboBox()
        self._alert_scope.addItem("All temperature sensors", "all")
        self._alert_scope.addItem("Favorites only", "favorites")
        self._alert_scope.addItem("Tray icon sensor", "tray")
        scope_index = self._alert_scope.findData(settings.alert_scope)
        if scope_index >= 0:
            self._alert_scope.setCurrentIndex(scope_index)
        alerts_form.addRow("Alert on", self._alert_scope)

        self._alert_temp = QtWidgets.QDoubleSpinBox()
        self._alert_temp.setRange(ALERT_TEMP_MIN, ALERT_TEMP_MAX)
        self._alert_temp.setDecimals(1)
        self._alert_temp.setSuffix(" °C")
        self._alert_temp.setValue(settings.alert_temp_c)
        alerts_form.addRow("Threshold", self._alert_temp)

        self._alert_cooldown = QtWidgets.QSpinBox()
        self._alert_cooldown.setRange(ALERT_COOLDOWN_MIN, ALERT_COOLDOWN_MAX)
        self._alert_cooldown.setSuffix(" sec")
        self._alert_cooldown.setValue(settings.alert_cooldown_sec)
        alerts_form.addRow("Cooldown", self._alert_cooldown)

        logging = QtWidgets.QGroupBox("Logging")
        logging_form = QtWidgets.QFormLayout(logging)
        logging_form.setHorizontalSpacing(16)
        logging_form.setVerticalSpacing(10)
        self._logging_enabled = QtWidgets.QCheckBox("Write daily CSV logs")
        self._logging_enabled.setChecked(settings.logging_enabled)
        logging_form.addRow(self._logging_enabled)
        self._log_interval = QtWidgets.QSpinBox()
        self._log_interval.setRange(LOG_INTERVAL_MIN, LOG_INTERVAL_MAX)
        self._log_interval.setSuffix(" sec")
        self._log_interval.setValue(settings.log_interval_sec)
        logging_form.addRow("Log every", self._log_interval)

        startup = QtWidgets.QGroupBox("Startup")
        startup_form = QtWidgets.QVBoxLayout(startup)
        self._start_minimized = QtWidgets.QCheckBox("Start minimized to tray")
        self._start_minimized.setChecked(settings.start_minimized)
        self._autostart_enabled = QtWidgets.QCheckBox("Start on login")
        self._autostart_enabled.setChecked(settings.autostart_enabled)
        startup_form.addWidget(self._start_minimized)
        startup_form.addWidget(self._autostart_enabled)

        layout.addWidget(display)
        layout.addWidget(alerts)
        layout.addWidget(logging)
        layout.addWidget(startup)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> Settings:
        settings = self._settings.copy()
        settings.refresh_ms = int(self._refresh_ms.value())
        settings.tooltip_mode = str(self._tooltip_mode.currentData() or "hottest")
        settings.tooltip_limit = int(self._tooltip_limit.value())
        settings.tray_sensor_key = str(self._tray_sensor.currentData() or "")
        settings.icon_temp_unit = self._icon_temp_unit.currentText()
        settings.alerts_enabled = bool(self._alerts_enabled.isChecked())
        settings.alert_scope = str(self._alert_scope.currentData() or "all")
        settings.alert_temp_c = float(self._alert_temp.value())
        settings.alert_cooldown_sec = int(self._alert_cooldown.value())
        settings.logging_enabled = bool(self._logging_enabled.isChecked())
        settings.log_interval_sec = int(self._log_interval.value())
        settings.start_minimized = bool(self._start_minimized.isChecked())
        settings.autostart_enabled = bool(self._autostart_enabled.isChecked())
        return settings.clamp()


class SensorWindow(QtWidgets.QMainWindow):
    readings_updated = QtCore.pyqtSignal(list)
    alert_triggered = QtCore.pyqtSignal(str, str)
    settings_changed = QtCore.pyqtSignal(object)
    _collect_requested = QtCore.pyqtSignal()

    def __init__(self, settings: Settings, tray_available: bool = True) -> None:
        super().__init__()
        self._settings = settings
        self._tray_available = tray_available
        self._allow_close = False
        self._collecting = False
        self._history: dict[str, list[tuple[float, float]]] = {}
        self._last_readings: list = []
        self._last_log_time = 0.0
        self._last_alert_time: dict[str, float] = {}

        self.setWindowTitle("HPTemp")
        self.setWindowIcon(app_icon())
        self.resize(1080, 740)
        self.setMinimumSize(880, 600)

        header = QtWidgets.QFrame()
        header.setObjectName("HeaderBar")
        header_layout = QtWidgets.QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_block = QtWidgets.QVBoxLayout()
        title_block.setSpacing(0)
        title = QtWidgets.QLabel("HPTemp")
        title.setObjectName("AppTitle")
        subtitle = QtWidgets.QLabel("HP Z workstation sensors")
        subtitle.setObjectName("AppSubtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header_layout.addLayout(title_block, 1)
        self._updated_label = QtWidgets.QLabel("Updating…")
        self._updated_label.setObjectName("AppSubtitle")
        self._updated_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        header_layout.addWidget(self._updated_label)

        self._metrics = MetricStrip(self)

        self._search = QtWidgets.QLineEdit()
        self._search.setPlaceholderText("Search sensors")
        self._search.setClearButtonEnabled(True)
        self._search.setText(self._settings.search_text)
        self._search.textChanged.connect(self._on_filters_edited)
        self._search.editingFinished.connect(self._persist_settings)

        self._category_filter = QtWidgets.QComboBox()
        self._category_filter.setMinimumWidth(150)
        self._category_filter.addItem("All types")
        self._category_filter.currentIndexChanged.connect(self._on_filters_edited)

        self._favorites_only = QtWidgets.QToolButton()
        self._favorites_only.setText("★ Favorites")
        self._favorites_only.setCheckable(True)
        self._favorites_only.setChecked(self._settings.show_favorites_only)
        self._favorites_only.setToolTip("Show only favorite sensors")
        self._favorites_only.toggled.connect(self._on_filter_toggled)

        self._clear_filters = QtWidgets.QToolButton()
        self._clear_filters.setText("Reset")
        self._clear_filters.setToolTip("Clear search and filters")
        self._clear_filters.clicked.connect(self._clear_filter_controls)

        self._open_settings_button = QtWidgets.QToolButton()
        self._open_settings_button.setText("Settings")
        self._open_settings_button.clicked.connect(self.open_settings)

        self._about_button = QtWidgets.QToolButton()
        self._about_button.setText("About")
        self._about_button.clicked.connect(self.open_about)

        filters = QtWidgets.QFrame()
        filters.setObjectName("FilterBar")
        controls = QtWidgets.QHBoxLayout(filters)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)
        controls.addWidget(self._search, 1)
        controls.addWidget(self._category_filter)
        controls.addWidget(self._favorites_only)
        controls.addWidget(self._clear_filters)
        controls.addWidget(self._open_settings_button)
        controls.addWidget(self._about_button)

        self._table = QtWidgets.QTableWidget(0, 6, self)
        self._table.setHorizontalHeaderLabels(
            ["★", "Name", "Group", "Type", "Reading", "Source"]
        )
        header_view = self._table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(0, 44)
        header_view.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header_view.sectionDoubleClicked.connect(self._auto_resize_column)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(3, QtCore.Qt.SortOrder.AscendingOrder)
        self._table.verticalHeader().setDefaultSectionSize(34)
        self._table.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self._table.itemSelectionChanged.connect(self._update_chart_from_selection)
        self._table.cellClicked.connect(self._on_cell_clicked)

        self._empty = QtWidgets.QLabel(
            _no_sensors_message()
        )
        self._empty.setObjectName("Placeholder")
        self._empty.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._empty.hide()

        table_stack = QtWidgets.QStackedWidget()
        table_stack.addWidget(self._table)
        table_stack.addWidget(self._empty)
        self._table_stack = table_stack

        self._chart = HistoryChart(self)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        splitter.addWidget(self._table_stack)
        splitter.addWidget(self._chart)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 0 if not HAS_CHARTS else 2)
        splitter.setChildrenCollapsible(False)

        central = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(18, 16, 18, 8)
        layout.setSpacing(12)
        layout.addWidget(header)
        layout.addWidget(self._metrics)
        layout.addWidget(filters)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self._persist_timer = QtCore.QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.setInterval(500)
        self._persist_timer.timeout.connect(self._persist_settings)

        self._did_shutdown = False
        self._worker = SensorWorker()
        self._thread = QtCore.QThread()
        self._worker.moveToThread(self._thread)
        self._collect_requested.connect(self._worker.collect)
        self._worker.finished.connect(self._on_readings)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(self._settings.refresh_ms)
        self.refresh()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._allow_close or not self._tray_available:
            if not self._shutdown():
                event.ignore()
                self._updated_label.setText("Waiting for sensor poll to finish…")
                return
            event.accept()
            if self._tray_available:
                QtWidgets.QApplication.quit()
            return
        self._persist_settings()
        event.ignore()
        self.hide()

    def allow_close(self) -> None:
        self._allow_close = True

    def _shutdown(self) -> bool:
        if self._did_shutdown:
            return True
        self._persist_timer.stop()
        self._persist_settings()
        self._timer.stop()
        try:
            self._collect_requested.disconnect()
        except TypeError:
            pass
        try:
            self._worker.finished.disconnect(self._on_readings)
        except TypeError:
            pass
        if self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(WORKER_SHUTDOWN_MS):
                return False
        self._did_shutdown = True
        return True

    @property
    def settings(self) -> Settings:
        return self._settings

    def apply_settings(self, settings: Settings) -> None:
        self._settings = settings.copy().clamp()
        self._favorites_only.blockSignals(True)
        self._favorites_only.setChecked(self._settings.show_favorites_only)
        self._favorites_only.blockSignals(False)
        self._timer.setInterval(self._settings.refresh_ms)
        self._metrics.update_readings(
            self._last_readings, self._settings.alert_temp_c, self._settings.icon_temp_unit
        )
        self._persist_settings()
        self._apply_filters()

    def current_readings(self) -> list:
        return list(self._last_readings)

    def refresh(self) -> None:
        if self._collecting:
            return
        if not self._thread.isRunning():
            return
        self._collecting = True
        self._collect_requested.emit()

    def _on_readings(self, readings: object, error: str) -> None:
        self._collecting = False
        parsed = list(readings) if isinstance(readings, list) else []
        parsed.sort(key=lambda r: (r.category, r.group, r.name, r.identity))
        self._last_readings = parsed

        self._update_history(parsed)
        self._metrics.update_readings(
            parsed, self._settings.alert_temp_c, self._settings.icon_temp_unit
        )
        self._apply_filters()
        self._update_window_title(parsed)
        self._write_logs(parsed)
        self._check_alerts(parsed)
        self._update_chart_from_selection()

        now = datetime.now().strftime("%H:%M:%S")
        if error and not parsed:
            message = f"Sensor update failed: {error}"
            self._updated_label.setText(message)
        elif parsed:
            message = f"Updated {now}  ·  {len(parsed)} sensors"
            self._updated_label.setText(message)
        else:
            self._updated_label.setText("No sensors")

        self.readings_updated.emit(parsed)

    def _update_history(self, readings: list) -> None:
        cutoff = time.time() - HISTORY_SECONDS
        now = time.time()
        for reading in readings:
            key = reading_key(reading)
            history = self._history.setdefault(key, [])
            history.append((now, reading.value))
            self._history[key] = [(stamp, value) for stamp, value in history if stamp >= cutoff]
        for key, history in list(self._history.items()):
            trimmed = [(stamp, value) for stamp, value in history if stamp >= cutoff]
            if trimmed:
                self._history[key] = trimmed
            else:
                del self._history[key]

    def _on_filters_edited(self) -> None:
        self._capture_filter_state()
        self._persist_timer.start()
        self._apply_filters()

    def _on_filter_toggled(self, _checked: bool = False) -> None:
        self._capture_filter_state()
        self._persist_settings()
        self._apply_filters()

    def _capture_filter_state(self) -> None:
        self._settings.show_favorites_only = self._favorites_only.isChecked()
        self._settings.search_text = self._search.text().strip()

    def _persist_settings(self) -> None:
        self._persist_timer.stop()
        self._capture_filter_state()
        try:
            save_settings(self._settings)
        except OSError as exc:
            self._updated_label.setText(f"Could not save settings: {exc}")

    def _apply_filters(self) -> None:
        readings = self._last_readings
        search = self._search.text().strip().lower()
        category = self._category_filter.currentText()
        favorites_only = self._favorites_only.isChecked()

        filtered = []
        categories = {ALL_TYPES}
        for reading in readings:
            categories.add(reading.category)
            if category not in {ALL_TYPES, "All"} and reading.category != category:
                continue
            if favorites_only and reading_key(reading) not in self._settings.favorites:
                continue
            if search and search not in _display_name(reading).lower():
                continue
            filtered.append(reading)

        self._refresh_categories(sorted(categories))
        if self._category_filter.currentText() != category:
            self._apply_filters()
            return
        self._render_table(filtered)
        self._update_chart_from_selection()

    def _refresh_categories(self, categories: list[str]) -> None:
        current = self._category_filter.currentText()
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItems(categories)
        if current in categories:
            self._category_filter.setCurrentText(current)
        self._category_filter.blockSignals(False)

    def _render_table(self, readings: list) -> None:
        selected_key = self._selected_reading_key()
        scroll = self._table.verticalScrollBar().value()
        header = self._table.horizontalHeader()
        sort_column = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()
        sorting_enabled = self._table.isSortingEnabled()

        self._table.blockSignals(True)
        self._table.setSortingEnabled(False)

        existing: dict[str, int] = {}
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item is None:
                continue
            key = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if key:
                existing[str(key)] = row

        wanted_keys = [reading_key(reading) for reading in readings]
        reuse = set(existing) == set(wanted_keys) and len(existing) == len(wanted_keys)

        if not reuse:
            self._table.setRowCount(len(readings))

        for row, reading in enumerate(readings):
            if reuse:
                row = existing[reading_key(reading)]
            self._populate_row(row, reading)

        if not reuse:
            self._table.setRowCount(len(readings))

        if sorting_enabled:
            self._table.setSortingEnabled(True)
            if 0 <= sort_column < self._table.columnCount():
                self._table.sortItems(sort_column, sort_order)
        else:
            self._table.setSortingEnabled(False)

        restored = False
        if selected_key:
            for row in range(self._table.rowCount()):
                item = self._table.item(row, 0)
                if item and str(item.data(QtCore.Qt.ItemDataRole.UserRole)) == selected_key:
                    self._table.selectRow(row)
                    restored = True
                    break
        if not restored:
            self._table.clearSelection()

        self._table.verticalScrollBar().setValue(scroll)
        self._table.blockSignals(False)
        if self._last_readings:
            self._table_stack.setCurrentWidget(self._table)
        else:
            self._table_stack.setCurrentWidget(self._empty)

    def _populate_row(self, row: int, reading) -> None:
        key = reading_key(reading)
        is_favorite = key in self._settings.favorites
        favorite = "★" if is_favorite else "☆"
        compact = format_compact_value(reading, self._settings.icon_temp_unit)
        both, both_unit = format_sensor_value(reading.value, reading.unit)
        tooltip = f"{_display_name(reading)}\n{both} {both_unit}"
        accent = QtGui.QColor(reading_accent(reading, self._settings.alert_temp_c))
        muted = QtGui.QColor(COLOR_MUTED)
        star_color = QtGui.QColor(COLOR_WARN) if is_favorite else muted
        values = [
            (favorite, 0 if is_favorite else 1, star_color),
            (reading.name or reading.category, (reading.name or "").lower(), None),
            (reading.group, (reading.group or "").lower(), muted),
            (
                reading.category,
                (TYPE_SORT.get(reading.category, 20), reading.category),
                None,
            ),
            (compact, float(reading.value), accent),
            (reading.source, reading.source, muted),
        ]
        for column, (display, sort_value, color) in enumerate(values):
            item = self._table.item(row, column)
            if item is None:
                item = SensorTableItem()
                self._table.setItem(row, column, item)
            item.setData(QtCore.Qt.ItemDataRole.DisplayRole, str(display))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, key)
            item.setData(SORT_ROLE, sort_value)
            item.setToolTip(tooltip)
            if column == 0:
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if color is not None:
                item.setForeground(QtGui.QBrush(color))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(COLOR_TEXT)))
            if column == 4:
                font = item.font()
                font.setWeight(QtGui.QFont.Weight.Bold)
                item.setFont(font)

    def _auto_resize_column(self, column: int) -> None:
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._table.resizeColumnToContents(column)
        header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeMode.Interactive)

    def _selected_reading_key(self) -> str | None:
        items = self._table.selectedItems()
        if not items:
            return None
        key = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        return str(key) if key else None

    def _update_chart_from_selection(self) -> None:
        key = self._selected_reading_key()
        if key is None:
            self._chart.update_series([], "", "")
            return
        history = self._history.get(key, [])
        reading = next((r for r in self._last_readings if reading_key(r) == key), None)
        label = _display_name(reading) if reading else "Sensor History"
        unit = reading.unit if reading else ""
        self._chart.update_series(history, label, unit)

    def _on_cell_clicked(self, row: int, column: int) -> None:
        if column != 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        key = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if key:
            self._toggle_favorite_key(str(key))

    def _toggle_selected_favorite(self) -> None:
        key = self._selected_reading_key()
        if key:
            self._toggle_favorite_key(key)

    def _toggle_favorite_key(self, key: str) -> None:
        if key in self._settings.favorites:
            self._settings.favorites.remove(key)
        else:
            self._settings.favorites.add(key)
        self._persist_settings()
        self._apply_filters()
        self.settings_changed.emit(self._settings)

    def _clear_filter_controls(self) -> None:
        self._search.blockSignals(True)
        self._favorites_only.blockSignals(True)
        self._category_filter.blockSignals(True)
        self._search.clear()
        self._favorites_only.setChecked(False)
        if self._category_filter.findText(ALL_TYPES) >= 0:
            self._category_filter.setCurrentText(ALL_TYPES)
        self._search.blockSignals(False)
        self._favorites_only.blockSignals(False)
        self._category_filter.blockSignals(False)
        self._capture_filter_state()
        self._persist_settings()
        self._apply_filters()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, self._last_readings, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        settings = dialog.apply()
        settings.show_favorites_only = self._settings.show_favorites_only
        settings.search_text = self._settings.search_text
        settings.favorites = set(self._settings.favorites)
        self.apply_settings(settings)
        try:
            ensure_autostart(settings.autostart_enabled, settings.start_minimized)
        except OSError as exc:
            self._updated_label.setText(f"Could not update autostart: {exc}")
        self.settings_changed.emit(settings)
        self._update_window_title(self._last_readings)

    def open_about(self) -> None:
        AboutDialog(self).exec()

    def _write_logs(self, readings: list) -> None:
        if not self._settings.logging_enabled:
            return
        now = time.time()
        if now - self._last_log_time < self._settings.log_interval_sec:
            return
        self._last_log_time = now

        try:
            logs_dir().mkdir(parents=True, exist_ok=True)
            log_path = logs_dir() / f"hptemp-{datetime.now().strftime('%Y%m%d')}.csv"
            new_file = not log_path.exists() or log_path.stat().st_size == 0
            with log_path.open("a", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                if new_file:
                    writer.writerow(
                        [
                            "timestamp",
                            "category",
                            "name",
                            "group",
                            "value",
                            "unit",
                            "source",
                        ]
                    )
                timestamp = datetime.now().isoformat(timespec="seconds")
                for reading in readings:
                    writer.writerow(
                        [
                            timestamp,
                            reading.category,
                            reading.name,
                            reading.group,
                            f"{reading.value:.2f}",
                            reading.unit,
                            reading.source,
                        ]
                    )
        except OSError as exc:
            self._updated_label.setText(f"Could not write log: {exc}")

    def _check_alerts(self, readings: list) -> None:
        if not self._settings.alerts_enabled:
            return
        threshold = self._settings.alert_temp_c
        cooldown = self._settings.alert_cooldown_sec
        now = time.time()
        tray_key = self._settings.tray_sensor_key
        hottest_key = None
        if self._settings.alert_scope == "tray" and not tray_key:
            temps = [reading for reading in readings if reading.unit == "°C"]
            if temps:
                hottest = max(temps, key=lambda reading: reading.value)
                hottest_key = reading_key(hottest)

        for reading in readings:
            if reading.unit != "°C":
                continue
            if reading.value < threshold:
                continue
            key = reading_key(reading)
            if self._settings.alert_scope == "favorites":
                if key not in self._settings.favorites:
                    continue
            elif self._settings.alert_scope == "tray":
                if tray_key:
                    if key != tray_key:
                        continue
                elif key != hottest_key:
                    continue
            last_time = self._last_alert_time.get(key, 0.0)
            if now - last_time < cooldown:
                continue
            self._last_alert_time[key] = now
            display_value, display_unit = format_sensor_value(reading.value, reading.unit)
            self.alert_triggered.emit(
                "Temperature Alert",
                f"{_display_name(reading)} is {display_value}{display_unit}",
            )

    def _update_window_title(self, readings: list) -> None:
        reading = _select_tray_reading(readings, self._settings)
        if reading is None:
            self.setWindowTitle("HPTemp")
            return
        if reading.unit == "°C":
            if self._settings.icon_temp_unit.upper() == "F":
                value = int(round(celsius_to_fahrenheit(reading.value)))
                unit = "°F"
            else:
                value = int(round(reading.value))
                unit = "°C"
        else:
            value, unit = format_sensor_value(reading.value, reading.unit)
        self.setWindowTitle(f"HPTemp — {_display_name(reading)} {value}{unit}")


class TrayController(QtCore.QObject):
    def __init__(self, window: SensorWindow, settings: Settings) -> None:
        super().__init__()
        self._window = window
        self._tray = QtWidgets.QSystemTrayIcon(self._window)
        self._tray.setIcon(QtGui.QIcon.fromTheme("utilities-system-monitor"))
        self._tray.setToolTip("HPTemp")

        menu = QtWidgets.QMenu()
        action_show = menu.addAction("Show Dashboard")
        action_show.triggered.connect(self._window.showNormal)
        action_hide = menu.addAction("Hide Dashboard")
        action_hide.triggered.connect(self._window.hide)
        menu.addSeparator()
        action_settings = menu.addAction("Settings")
        action_settings.triggered.connect(self._window.open_settings)
        action_about = menu.addAction("About")
        action_about.triggered.connect(self._window.open_about)
        menu.addSeparator()
        action_quit = menu.addAction("Quit")
        action_quit.triggered.connect(self._quit_app)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._handle_activation)
        self._tray.show()

        self._window.readings_updated.connect(self._update_tooltip)
        self._window.alert_triggered.connect(self.show_alert)
        self._update_tooltip()

    def apply_settings(self, settings: Settings | None = None) -> None:
        self._update_tooltip()

    def _quit_app(self) -> None:
        self._window.allow_close()
        self._window.close()

    def _handle_activation(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        click_reasons = {
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
            QtWidgets.QSystemTrayIcon.ActivationReason.MiddleClick,
        }
        if reason not in click_reasons:
            return
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.showNormal()
            self._window.raise_()
            self._window.activateWindow()

    def _update_tooltip(self) -> None:
        readings = self._window.current_readings()
        settings = self._window.settings
        tooltip_lines = ["HPTemp"]
        if settings.tooltip_mode == "favorites" and settings.favorites:
            selected = [r for r in readings if reading_key(r) in settings.favorites]
        else:
            selected = [r for r in readings if r.unit == "°C"]
            selected.sort(key=lambda r: r.value, reverse=True)
        for reading in selected[: settings.tooltip_limit]:
            display_value, display_unit = format_sensor_value(reading.value, reading.unit)
            tooltip_lines.append(f"{reading.name}: {display_value}{display_unit}")
        self._tray.setToolTip("\n".join(tooltip_lines))
        self._update_icon(readings)

    def show_alert(self, title: str, message: str) -> None:
        self._tray.showMessage(
            title,
            message,
            QtWidgets.QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def _update_icon(self, readings: list) -> None:
        reading = _select_tray_reading(readings, self._window.settings)
        if reading is None:
            return
        if reading.unit == "°C":
            if self._window.settings.icon_temp_unit.upper() == "F":
                icon_label = f"{int(round(celsius_to_fahrenheit(reading.value)))}°"
            else:
                icon_label = f"{int(round(reading.value))}°"
        else:
            display_value, display_unit = format_sensor_value(reading.value, reading.unit)
            icon_label = f"{display_value}{display_unit}"
        accent = reading_accent(reading, self._window.settings.alert_temp_c)
        icon = _make_tray_icon(icon_label, accent)
        self._tray.setIcon(icon)


class HPTempApp(QtWidgets.QApplication):
    def __init__(self, argv: list[str], start_minimized: bool) -> None:
        super().__init__(argv)
        self.setApplicationName("HPTemp")
        self.setApplicationDisplayName("HPTemp")
        self.setDesktopFileName("hptemp")
        apply_theme(self)
        self.setWindowIcon(app_icon())

        self._settings = load_settings()

        tray_available = QtWidgets.QSystemTrayIcon.isSystemTrayAvailable()
        self.setQuitOnLastWindowClosed(not tray_available)

        self._window = SensorWindow(self._settings, tray_available=tray_available)
        self._tray = TrayController(self._window, self._settings) if tray_available else None
        self._window.settings_changed.connect(self.apply_settings)

        hide = (start_minimized or self._settings.start_minimized) and tray_available
        if hide:
            self._window.hide()
        else:
            self._window.show()
            if (start_minimized or self._settings.start_minimized) and not tray_available:
                self._window._updated_label.setText(
                    "System tray is unavailable; started in a window instead."
                )

    def apply_settings(self, settings: Settings) -> None:
        self._settings = settings.copy()
        if self._tray is not None:
            self._tray.apply_settings(settings)


def ensure_autostart(enabled: bool, minimized: bool = True) -> None:
    if sys.platform == "win32":
        _ensure_autostart_windows(enabled, minimized)
        return
    _ensure_autostart_linux(enabled, minimized)


def _ensure_autostart_linux(enabled: bool, minimized: bool) -> None:
    autostart_path = Path.home() / ".config" / "autostart" / "hptemp.desktop"
    if not enabled:
        if autostart_path.exists():
            autostart_path.unlink()
        return
    command = _autostart_command()
    if minimized:
        command = f"{command} --minimized"
    autostart_path.parent.mkdir(parents=True, exist_ok=True)
    autostart_path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=HPTemp\n"
        f"Exec={command}\n"
        "Icon=hptemp\n"
        "X-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )


def _windows_startup_path() -> Path:
    roaming = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    return roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "HPTemp.bat"


def _ensure_autostart_windows(enabled: bool, minimized: bool) -> None:
    path = _windows_startup_path()
    if not enabled:
        if path.exists():
            path.unlink()
        return
    command = _windows_launch_command(minimized)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "@echo off\r\n"
        f"{command}\r\n",
        encoding="utf-8",
    )


def _windows_launch_command(minimized: bool) -> str:
    extra = " --minimized" if minimized else ""
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        return f'start "" "{exe}"{extra}'
    python = str(Path(sys.executable).resolve())
    src_dir = str(Path(__file__).resolve().parent.parent)
    pythonw = python.lower().replace("python.exe", "pythonw.exe")
    launcher = pythonw if Path(pythonw).exists() else python
    return (
        f'set "PYTHONPATH={src_dir}"\r\n'
        f'start "" "{launcher}" -m hptemp{extra}'
    )


def _license_file() -> Path | None:
    candidates = [
        Path(__file__).resolve().parents[2] / "LICENSE",
        Path("/usr/share/doc/hptemp/copyright"),
        Path.home() / ".local" / "share" / "doc" / "hptemp" / "copyright",
    ]
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            exe_dir / "LICENSE",
            meipass / "LICENSE",
            *candidates,
        ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _no_sensors_message() -> str:
    if sys.platform == "win32":
        return (
            "No sensors detected.\n"
            "Install NVIDIA drivers for GPU temps, or Libre Hardware Monitor for CPU/fans.\n"
            "HP WMI sensors appear when HP Client Management / BIOS numeric sensors are available."
        )
    return (
        "No sensors detected.\n"
        "Install lm-sensors (and hp-wmi-sensors if available), then run sensors-detect.\n"
        "On ProLiant/Z systems, hpasmcli or ipmitool adds HP hardware sensors."
    )


def _desktop_quote(value: str) -> str:
    specials = set(' \t\n"\'\\><~|&;$*?#()`')
    if value and not any(char in specials for char in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return _desktop_quote(str(Path(sys.executable).resolve()))
    installed = shutil.which("hptemp")
    if installed:
        return _desktop_quote(installed)
    src_dir = str(Path(__file__).resolve().parent.parent)
    return (
        f"env PYTHONPATH={_desktop_quote(src_dir)} "
        f"{_desktop_quote(sys.executable)} -m hptemp"
    )


def _select_tray_reading(readings: list, settings: Settings):
    if settings.tray_sensor_key:
        match = next(
            (reading for reading in readings if reading_key(reading) == settings.tray_sensor_key),
            None,
        )
        if match is not None:
            return match
    temps = [reading for reading in readings if reading.unit == "°C"]
    temps.sort(key=lambda reading: reading.value, reverse=True)
    return temps[0] if temps else None


def _display_name(reading) -> str:
    group = humanize(reading.group)
    name = humanize(reading.name)
    if not name:
        name = "Sensor"
    if group:
        return f"{group} • {name}"
    return name


def _make_tray_icon(label: str, accent: str = COLOR_ACCENT) -> QtGui.QIcon:
    base_size = QtWidgets.QApplication.style().pixelMetric(
        QtWidgets.QStyle.PixelMetric.PM_SmallIconSize
    )
    size = max(22, base_size)
    scale = 2.0
    pixmap = QtGui.QPixmap(int(size * scale), int(size * scale))
    pixmap.setDevicePixelRatio(scale)
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    bg = QtGui.QColor(COLOR_BG)
    painter.setBrush(bg)
    painter.setPen(QtGui.QPen(QtGui.QColor(accent), 1.5))
    painter.drawRoundedRect(1, 1, size - 2, size - 2, size * 0.25, size * 0.25)

    text = label.replace(" ", "")
    font_size = max(8, int(size * 0.5))
    font = QtGui.QFont("Sans Serif", font_size, QtGui.QFont.Weight.Bold)
    painter.setPen(QtGui.QColor("#f9fafb"))
    while font_size > 6:
        painter.setFont(font)
        metrics = painter.fontMetrics()
        if metrics.horizontalAdvance(text) <= size - 4:
            break
        font_size -= 1
        font.setPointSize(font_size)
    painter.drawText(
        QtCore.QRectF(2, 0, size - 4, size),
        QtCore.Qt.AlignmentFlag.AlignCenter,
        text,
    )
    painter.end()
    return QtGui.QIcon(pixmap)


def main() -> int:
    parser = argparse.ArgumentParser(description="HPTemp Sensor Dashboard")
    parser.add_argument("--minimized", action="store_true", help="Start minimized")
    args = parser.parse_args()

    app = HPTempApp(sys.argv, start_minimized=args.minimized)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
