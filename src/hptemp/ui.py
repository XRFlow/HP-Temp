# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from .sensors import celsius_to_fahrenheit


COLOR_BG = "#07141c"
COLOR_SURFACE = "#0d1f2b"
COLOR_RAISED = "#123044"
COLOR_BORDER = "#1f4b63"
COLOR_TEXT = "#e8f4fa"
COLOR_MUTED = "#8fb4c7"
COLOR_ACCENT = "#0096d6"
COLOR_ACCENT_SOFT = "#5ec8f0"
COLOR_COOL = "#38bdf8"
COLOR_OK = "#34d399"
COLOR_WARN = "#fbbf24"
COLOR_HOT = "#fb923c"
COLOR_CRIT = "#f87171"


APP_QSS = f"""
QMainWindow, QDialog, QWidget {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
}}
QLabel {{
    color: {COLOR_TEXT};
    background: transparent;
}}
QStatusBar {{
    background: {COLOR_SURFACE};
    color: {COLOR_MUTED};
    border-top: 1px solid {COLOR_BORDER};
}}
QLineEdit, QComboBox {{
    background: {COLOR_RAISED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    min-height: 18px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: #0f172a;
}}
QSpinBox, QDoubleSpinBox {{
    background: {COLOR_RAISED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 4px 22px 4px 10px;
    min-height: 22px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: #0f172a;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {COLOR_SURFACE};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: {COLOR_RAISED};
}}
QPushButton, QToolButton {{
    background: {COLOR_RAISED};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
}}
QPushButton:hover, QToolButton:hover {{
    border-color: {COLOR_ACCENT};
    color: #fff;
}}
QPushButton:pressed, QToolButton:pressed,
QToolButton:checked {{
    background: #2a1a10;
    border-color: {COLOR_ACCENT};
    color: {COLOR_ACCENT_SOFT};
}}
QCheckBox {{
    color: {COLOR_TEXT};
    spacing: 8px;
}}
QHeaderView::section {{
    background: {COLOR_SURFACE};
    color: {COLOR_MUTED};
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
    padding: 8px 10px;
    font-weight: 600;
}}
QTableWidget {{
    background: {COLOR_SURFACE};
    alternate-background-color: #162033;
    color: {COLOR_TEXT};
    gridline-color: #1f2a3d;
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    selection-background-color: #2a1f14;
    selection-color: {COLOR_TEXT};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QTableCornerButton::section {{
    background: {COLOR_SURFACE};
    border: none;
}}
QScrollBar:vertical, QScrollBar:horizontal {{
    background: {COLOR_SURFACE};
    border: none;
    width: 10px;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER};
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0;
    width: 0;
}}
QSplitter::handle {{
    background: {COLOR_BG};
}}
QSplitter::handle:vertical {{
    height: 8px;
}}
QGroupBox {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    color: {COLOR_TEXT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: {COLOR_MUTED};
}}
QDialogButtonBox QPushButton {{
    min-width: 88px;
}}
QFrame#MetricCard {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 12px;
}}
QFrame#HeaderBar, QFrame#FilterBar, QFrame#ChartPanel {{
    background: transparent;
    border: none;
}}
QLabel#AppTitle {{
    font-size: 20px;
    font-weight: 700;
    color: {COLOR_TEXT};
}}
QLabel#AppSubtitle {{
    color: {COLOR_MUTED};
    font-size: 12px;
}}
QLabel#MetricKicker {{
    color: {COLOR_MUTED};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}
QLabel#MetricValue {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#MetricCaption {{
    color: {COLOR_MUTED};
    font-size: 12px;
}}
QLabel#ChartHeading {{
    font-size: 14px;
    font-weight: 600;
}}
QLabel#Placeholder {{
    color: {COLOR_MUTED};
    font-size: 14px;
}}
"""


def apply_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    font = QtGui.QFont("Ubuntu", 10)
    if not QtGui.QFontInfo(font).family():
        font = QtGui.QFont("Sans Serif", 10)
    app.setFont(font)

    palette = QtGui.QPalette()
    bg = QtGui.QColor(COLOR_BG)
    surface = QtGui.QColor(COLOR_SURFACE)
    text = QtGui.QColor(COLOR_TEXT)
    muted = QtGui.QColor(COLOR_MUTED)
    accent = QtGui.QColor(COLOR_ACCENT)
    palette.setColor(QtGui.QPalette.ColorRole.Window, bg)
    palette.setColor(QtGui.QPalette.ColorRole.WindowText, text)
    palette.setColor(QtGui.QPalette.ColorRole.Base, surface)
    palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor("#162033"))
    palette.setColor(QtGui.QPalette.ColorRole.Text, text)
    palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(COLOR_RAISED))
    palette.setColor(QtGui.QPalette.ColorRole.ButtonText, text)
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, accent)
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor("#0f172a"))
    palette.setColor(QtGui.QPalette.ColorRole.PlaceholderText, muted)
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, surface)
    palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, text)
    app.setPalette(palette)
    app.setStyleSheet(APP_QSS)


def app_icon() -> QtGui.QIcon:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                exe_dir / "hptemp.ico",
                meipass / "packaging" / "hptemp.ico",
                meipass / "packaging" / "hptemp.svg",
            ]
        )
    repo = Path(__file__).resolve().parents[2]
    candidates.extend(
        [
            repo / "packaging" / "hptemp.ico",
            repo / "packaging" / "hptemp.svg",
            Path("/usr/share/icons/hicolor/scalable/apps/hptemp.svg"),
        ]
    )
    for path in candidates:
        if path.exists():
            return QtGui.QIcon(str(path))
    return QtGui.QIcon.fromTheme("utilities-system-monitor")


def reading_accent(reading, alert_temp_c: float) -> str:
    unit = getattr(reading, "unit", "")
    value = float(getattr(reading, "value", 0.0))
    if unit == "°C":
        if value >= alert_temp_c:
            return COLOR_CRIT
        if value >= max(alert_temp_c - 15.0, 70.0):
            return COLOR_HOT
        if value >= 55.0:
            return COLOR_WARN
        return COLOR_OK
    if unit == "RPM":
        return COLOR_COOL
    if unit == "%":
        return COLOR_COOL
    return COLOR_MUTED


def format_compact_value(reading, icon_unit: str = "C") -> str:
    unit = reading.unit
    value = float(reading.value)
    if unit == "°C":
        if str(icon_unit).upper() == "F":
            return f"{celsius_to_fahrenheit(value):.1f}°F"
        return f"{value:.1f}°C"
    if unit == "RPM":
        return f"{int(round(value))} RPM"
    if unit == "%":
        return f"{value:.0f}%"
    if value.is_integer():
        return f"{int(value)} {unit}".strip()
    return f"{value:.1f} {unit}".strip()


def _haystack(reading) -> str:
    return f"{reading.category} {reading.group} {reading.name}".lower()


def pick_hottest(readings: list):
    temps = [item for item in readings if item.unit == "°C"]
    if not temps:
        return None
    preferred = [
        item
        for item in temps
        if not any(skip in _haystack(item) for skip in ("iwlwifi", "wifi", "wlan"))
    ]
    pool = preferred or temps
    return max(pool, key=lambda item: item.value)


def pick_cpu(readings: list):
    temps = [
        item
        for item in readings
        if item.unit == "°C" and item.category == "Temperature"
    ]
    for needle in ("package", "tctl", "tdie", "cpu"):
        for item in temps:
            if needle in _haystack(item):
                return item
    return pick_hottest(temps)


def pick_gpu(readings: list):
    temps = [item for item in readings if item.unit == "°C" and "gpu" in _haystack(item)]
    if not temps:
        return None
    return max(temps, key=lambda item: item.value)


def pick_fan(readings: list):
    fans = [
        item
        for item in readings
        if item.unit in {"RPM", "%"} and "fan" in item.category.lower()
    ]
    if not fans:
        return None
    rpm = [item for item in fans if item.unit == "RPM"]
    pool = rpm or fans
    return max(pool, key=lambda item: item.value)


class MetricCard(QtWidgets.QFrame):
    def __init__(self, kicker: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        self._kicker = QtWidgets.QLabel(kicker.upper())
        self._kicker.setObjectName("MetricKicker")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("MetricValue")
        self._caption = QtWidgets.QLabel("Waiting for sensors")
        self._caption.setObjectName("MetricCaption")
        self._caption.setWordWrap(True)
        layout.addWidget(self._kicker)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)

    def set_reading(self, reading, alert_temp_c: float, icon_unit: str) -> None:
        if reading is None:
            self._value.setText("—")
            self._value.setStyleSheet(f"color: {COLOR_MUTED};")
            self._caption.setText("No sensor")
            return
        self._value.setText(format_compact_value(reading, icon_unit))
        self._value.setStyleSheet(f"color: {reading_accent(reading, alert_temp_c)};")
        name = reading.name or reading.category
        group = reading.group
        self._caption.setText(f"{group} · {name}" if group else name)


class MetricStrip(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.hottest = MetricCard("Hottest")
        self.cpu = MetricCard("CPU")
        self.gpu = MetricCard("GPU")
        self.fan = MetricCard("Fan")
        for card in (self.hottest, self.cpu, self.gpu, self.fan):
            layout.addWidget(card)

    def update_readings(self, readings: list, alert_temp_c: float, icon_unit: str) -> None:
        self.hottest.set_reading(pick_hottest(readings), alert_temp_c, icon_unit)
        self.cpu.set_reading(pick_cpu(readings), alert_temp_c, icon_unit)
        self.gpu.set_reading(pick_gpu(readings), alert_temp_c, icon_unit)
        self.fan.set_reading(pick_fan(readings), alert_temp_c, icon_unit)
