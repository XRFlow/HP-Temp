# SPDX-License-Identifier: GPL-3.0-or-later
from types import SimpleNamespace

from hptemp.ui import (
    COLOR_COOL,
    COLOR_CRIT,
    COLOR_HOT,
    COLOR_OK,
    COLOR_WARN,
    format_compact_value,
    pick_cpu,
    pick_fan,
    pick_gpu,
    pick_hottest,
    reading_accent,
)


def _reading(**kwargs):
    defaults = {
        "category": "Temperature",
        "name": "Sensor",
        "value": 40.0,
        "unit": "°C",
        "source": "lm-sensors",
        "group": "Chip",
        "identity": "temp1_input",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_reading_accent_thresholds() -> None:
    cool = _reading(value=42.0)
    warn = _reading(value=62.0)
    hot = _reading(value=80.0)
    crit = _reading(value=90.0)
    fan = _reading(category="Fan", unit="RPM", value=2000)
    assert reading_accent(cool, 85.0) == COLOR_OK
    assert reading_accent(warn, 85.0) == COLOR_WARN
    assert reading_accent(hot, 85.0) == COLOR_HOT
    assert reading_accent(crit, 85.0) == COLOR_CRIT
    assert reading_accent(fan, 85.0) == COLOR_COOL


def test_format_compact_value_units() -> None:
    temp = _reading(value=40.0)
    assert format_compact_value(temp, "C") == "40.0°C"
    assert format_compact_value(temp, "F") == "104.0°F"
    fan = _reading(category="Fan", unit="RPM", value=2578.0)
    assert format_compact_value(fan, "C") == "2578 RPM"


def test_summary_pickers() -> None:
    cpu = _reading(name="Package Id 0", group="Coretemp Isa 0000", value=44.0)
    nvme = _reading(name="Composite", group="Nvme", value=70.0)
    gpu = _reading(category="GPU Temperature", name="Rtx", group="GPU 0", value=61.0)
    fan = _reading(category="Fan", name="Processor Fan", unit="RPM", value=2400.0, group="HP Superio")
    readings = [cpu, nvme, gpu, fan]
    wifi = _reading(name="Temp1", group="Iwlwifi 1 Virtual 0", value=80.0)
    assert pick_hottest(readings) is nvme
    assert pick_hottest([wifi, cpu, gpu]) is gpu
    assert pick_cpu(readings) is cpu
    assert pick_gpu(readings) is gpu
    assert pick_fan(readings) is fan
