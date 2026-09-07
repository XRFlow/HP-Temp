# SPDX-License-Identifier: GPL-3.0-or-later
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional

import psutil


@dataclass(frozen=True)
class SensorReading:
    category: str
    name: str
    value: float
    unit: str
    source: str
    group: str
    identity: str = ""


_NON_JSON_NUMBER = re.compile(
    r"(?<![A-Za-z0-9_+-])[+-]?(?:NaN|Infinity|Inf)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def collect_readings() -> List[SensorReading]:
    psutil_temps = _safe_collect(_from_psutil_temps)
    psutil_fans = _safe_collect(_from_psutil_fans)
    lm_readings = _safe_collect(_from_lm_sensors)
    nvidia_readings = _safe_collect(_from_nvidia_smi)
    windows_readings = _safe_collect(_from_windows)
    hpasm_readings = _safe_collect(_from_hpasmcli)
    ipmi_readings = _safe_collect(_from_ipmi)

    readings: List[SensorReading] = []
    lm_categories = {reading.category for reading in lm_readings}
    if "Temperature" not in lm_categories:
        readings.extend(psutil_temps)
    if "Fan" not in lm_categories:
        readings.extend(psutil_fans)
    readings.extend(lm_readings)
    readings.extend(nvidia_readings)
    readings.extend(windows_readings)
    readings.extend(hpasm_readings)
    readings.extend(ipmi_readings)
    return [_normalize_reading(reading) for reading in _dedupe(readings)]


def reading_key(reading: SensorReading) -> str:
    identity = (reading.identity or "").strip()
    base = f"{reading.source}|{reading.group}|{reading.category}|{reading.name}"
    if identity:
        return f"{base}|{identity}"
    return base


def celsius_to_fahrenheit(celsius: float) -> float:
    return (float(celsius) * 9 / 5) + 32


def format_sensor_value(value: float, unit: str) -> tuple[str, str]:
    value = float(value)
    if unit == "°C":
        fahrenheit = celsius_to_fahrenheit(value)
        return (f"{value:.1f} / {fahrenheit:.1f}", "°C/°F")
    if value.is_integer():
        return f"{int(value)}", unit
    return f"{value:.1f}", unit


def sanitize_lm_sensors_json(text: str) -> str:
    return _NON_JSON_NUMBER.sub("null", text)


def parse_lm_sensors_payload(payload: dict) -> List[SensorReading]:
    readings: List[SensorReading] = []
    if not isinstance(payload, dict):
        return readings
    for chip, features in payload.items():
        if not isinstance(features, dict):
            continue
        for feature_name, feature in features.items():
            if not isinstance(feature, dict):
                continue
            label = feature.get(f"{feature_name}_label")
            for key, value in feature.items():
                if not _looks_like_input(key, value):
                    continue
                current = _finite_float(value)
                if current is None:
                    continue
                category, unit = _category_for_key(key)
                display = label or feature_name
                readings.append(
                    SensorReading(
                        category=category,
                        name=humanize(display),
                        value=current,
                        unit=unit,
                        source="lm-sensors",
                        group=humanize(chip),
                        identity=str(key),
                    )
                )
    return readings


def parse_windows_acpi_temps(payload: Any) -> List[SensorReading]:
    items = _as_item_list(payload)
    readings: List[SensorReading] = []
    for index, item in enumerate(items):
        name = str(item.get("Name") or item.get("InstanceName") or f"Zone {index}")
        celsius = _finite_float(item.get("C") if "C" in item else item.get("Celsius"))
        if celsius is None:
            tenths_k = _finite_float(item.get("CurrentTemperature"))
            if tenths_k is not None:
                celsius = (tenths_k / 10.0) - 273.15
        if celsius is None:
            continue
        readings.append(
            SensorReading(
                category="Temperature",
                name=humanize(name.split("\\")[-1]),
                value=celsius,
                unit="°C",
                source="wmi",
                group="ACPI Thermal",
                identity=str(item.get("InstanceName") or index),
            )
        )
    return readings


def parse_ohm_sensors(payload: Any) -> List[SensorReading]:
    items = _as_item_list(payload)
    readings: List[SensorReading] = []
    for index, item in enumerate(items):
        sensor_type = str(item.get("SensorType") or "").strip()
        value = _finite_float(item.get("Value"))
        if value is None:
            continue
        name = str(item.get("Name") or sensor_type or f"Sensor {index}")
        ident = str(item.get("Identifier") or index)
        if sensor_type.lower() == "temperature":
            readings.append(
                SensorReading(
                    category="Temperature",
                    name=humanize(name),
                    value=value,
                    unit="°C",
                    source="lhm",
                    group="Hardware Monitor",
                    identity=ident,
                )
            )
        elif sensor_type.lower() == "fan":
            readings.append(
                SensorReading(
                    category="Fan",
                    name=humanize(name),
                    value=value,
                    unit="RPM",
                    source="lhm",
                    group="Hardware Monitor",
                    identity=ident,
                )
            )
        elif sensor_type.lower() == "voltage":
            readings.append(
                SensorReading(
                    category="Voltage",
                    name=humanize(name),
                    value=value,
                    unit="V",
                    source="lhm",
                    group="Hardware Monitor",
                    identity=ident,
                )
            )
    return readings


def parse_hpasmcli_temp(text: str) -> List[SensorReading]:
    readings: List[SensorReading] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw.startswith("#"):
            continue
        parts = raw.split()
        if len(parts) < 3:
            continue
        ident = parts[0].lstrip("#")
        loc_parts: list[str] = []
        temp_token = ""
        for part in parts[1:]:
            if part == "-" or re.match(r"^[0-9.]+C", part, re.IGNORECASE):
                temp_token = part
                break
            loc_parts.append(part)
        if not temp_token or temp_token == "-":
            continue
        match = re.match(r"([0-9.]+)C", temp_token, re.IGNORECASE)
        if not match:
            continue
        celsius = _finite_float(match.group(1))
        if celsius is None:
            continue
        location = " ".join(loc_parts) or f"Sensor {ident}"
        readings.append(
            SensorReading(
                category="Temperature",
                name=humanize(location),
                value=celsius,
                unit="°C",
                source="hpasmcli",
                group="HP System",
                identity=ident,
            )
        )
    return readings


def parse_hpasmcli_fans(text: str) -> List[SensorReading]:
    readings: List[SensorReading] = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw.startswith("#"):
            continue
        parts = raw.split()
        if len(parts) < 3:
            continue
        ident = parts[0].lstrip("#")
        percent = None
        rpm = None
        loc_parts: list[str] = []
        for part in parts[1:]:
            if part.lower() in {"yes", "no", "normal", "n/a"}:
                continue
            if part.endswith("%"):
                percent = _finite_float(part.rstrip("%"))
                continue
            if part.upper().endswith("RPM"):
                rpm = _finite_float(part[:-3])
                continue
            if re.fullmatch(r"[0-9.]+", part) and loc_parts:
                continue
            loc_parts.append(part)
        location = " ".join(loc_parts) or f"Fan {ident}"
        if rpm is not None:
            readings.append(
                SensorReading(
                    category="Fan",
                    name=humanize(location),
                    value=rpm,
                    unit="RPM",
                    source="hpasmcli",
                    group="HP System",
                    identity=f"{ident}-rpm",
                )
            )
        elif percent is not None:
            readings.append(
                SensorReading(
                    category="Fan",
                    name=humanize(location),
                    value=percent,
                    unit="%",
                    source="hpasmcli",
                    group="HP System",
                    identity=f"{ident}-pct",
                )
            )
    return readings


def parse_ipmitool_sdr(text: str) -> List[SensorReading]:
    readings: List[SensorReading] = []
    for index, line in enumerate((text or "").splitlines()):
        if "|" not in line:
            continue
        fields = [part.strip() for part in line.split("|")]
        if len(fields) < 2:
            continue
        name, reading = fields[0], fields[1]
        lowered = reading.lower()
        if lowered in {"disabled", "no reading", "not readable", "ns", "na"}:
            continue
        if "degree" in lowered:
            match = re.search(r"([0-9.]+)", reading)
            value = _finite_float(match.group(1) if match else None)
            if value is None:
                continue
            readings.append(
                SensorReading(
                    category="Temperature",
                    name=humanize(name),
                    value=value,
                    unit="°C",
                    source="ipmi",
                    group="IPMI",
                    identity=f"temp-{index}",
                )
            )
        elif "rpm" in lowered:
            match = re.search(r"([0-9.]+)", reading)
            value = _finite_float(match.group(1) if match else None)
            if value is None:
                continue
            readings.append(
                SensorReading(
                    category="Fan",
                    name=humanize(name),
                    value=value,
                    unit="RPM",
                    source="ipmi",
                    group="IPMI",
                    identity=f"fan-{index}",
                )
            )
    return readings


def parse_hp_bios_numeric(payload: Any) -> List[SensorReading]:
    items = _as_item_list(payload)
    readings: List[SensorReading] = []
    for index, item in enumerate(items):
        value = _finite_float(item.get("CurrentReading") or item.get("Value"))
        if value is None:
            continue
        name = str(item.get("Name") or item.get("Description") or f"HP Sensor {index}")
        hay = name.lower()
        if "fan" in hay:
            category, unit = "Fan", "RPM"
        elif "temp" in hay or "thermal" in hay or "ambient" in hay:
            category, unit = "Temperature", "°C"
        elif "volt" in hay:
            category, unit = "Voltage", "V"
        else:
            continue
        readings.append(
            SensorReading(
                category=category,
                name=humanize(name),
                value=value,
                unit=unit,
                source="hp-wmi",
                group="HP BIOS",
                identity=str(item.get("Name") or index),
            )
        )
    return readings


def parse_nvidia_smi_csv(text: str) -> List[SensorReading]:
    readings: List[SensorReading] = []
    for index, line in enumerate((text or "").strip().splitlines()):
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            continue
        fan = parts[-1]
        temp = parts[-2]
        name = ", ".join(parts[:-2]).strip()
        if temp and temp.upper() != "N/A":
            current = _finite_float(temp)
            if current is not None:
                readings.append(
                    SensorReading(
                        category="GPU Temperature",
                        name=humanize(name),
                        value=current,
                        unit="°C",
                        source="nvidia-smi",
                        group=f"GPU {index}",
                        identity="temperature.gpu",
                    )
                )
        if fan and fan.upper() != "N/A":
            current = _finite_float(fan)
            if current is not None:
                readings.append(
                    SensorReading(
                        category="GPU Fan",
                        name=humanize(name),
                        value=current,
                        unit="%",
                        source="nvidia-smi",
                        group=f"GPU {index}",
                        identity="fan.speed",
                    )
                )
    return readings


def _safe_collect(
    collector: Callable[[], Iterable[SensorReading]],
) -> List[SensorReading]:
    try:
        return list(collector())
    except Exception:
        return []


def _normalize_reading(reading: SensorReading) -> SensorReading:
    category = reading.category.strip() if isinstance(reading.category, str) else ""
    name = reading.name.strip() if isinstance(reading.name, str) else ""
    unit = reading.unit.strip() if isinstance(reading.unit, str) else ""
    source = reading.source.strip() if isinstance(reading.source, str) else ""
    group = reading.group.strip() if isinstance(reading.group, str) else ""
    identity = reading.identity.strip() if isinstance(reading.identity, str) else ""
    if not category:
        category = "Sensor"
    if not name:
        name = category
    if not source:
        source = "unknown"
    return SensorReading(
        category=category,
        name=name,
        value=reading.value,
        unit=unit,
        source=source,
        group=group,
        identity=identity,
    )


def _from_psutil_temps() -> Iterable[SensorReading]:
    try:
        temps = psutil.sensors_temperatures(fahrenheit=False) or {}
    except (OSError, AttributeError, TypeError):
        return []

    readings: List[SensorReading] = []
    for group, entries in temps.items():
        for index, entry in enumerate(entries or []):
            current = _finite_float(getattr(entry, "current", None))
            if current is None:
                continue
            label = getattr(entry, "label", None) or "Temperature"
            readings.append(
                SensorReading(
                    category="Temperature",
                    name=humanize(label),
                    value=current,
                    unit="°C",
                    source="psutil",
                    group=humanize(group),
                    identity=str(index),
                )
            )
    return readings


def _from_psutil_fans() -> Iterable[SensorReading]:
    try:
        fans = psutil.sensors_fans() or {}
    except (OSError, AttributeError, TypeError):
        return []

    readings: List[SensorReading] = []
    for group, entries in fans.items():
        for index, entry in enumerate(entries or []):
            current = _finite_float(getattr(entry, "current", None))
            if current is None:
                continue
            label = getattr(entry, "label", None) or "Fan"
            readings.append(
                SensorReading(
                    category="Fan",
                    name=humanize(label),
                    value=current,
                    unit="RPM",
                    source="psutil",
                    group=humanize(group),
                    identity=str(index),
                )
            )
    return readings


def _from_lm_sensors() -> Iterable[SensorReading]:
    if not shutil.which("sensors"):
        return []

    stdout = _run_command(["sensors", "-j"], timeout=2)
    if not stdout:
        return []

    try:
        payload = json.loads(sanitize_lm_sensors_json(stdout))
    except json.JSONDecodeError:
        return []
    return parse_lm_sensors_payload(payload)


def _looks_like_input(key: str, value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(float(value)):
        return False
    return key.endswith("_input")


def _finite_float(value: object) -> Optional[float]:
    try:
        current = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(current):
        return None
    return current


def _category_for_key(key: str) -> tuple[str, str]:
    if key.startswith("temp"):
        return "Temperature", "°C"
    if key.startswith("fan"):
        return "Fan", "RPM"
    if key.startswith("power"):
        return "Power", "W"
    if key.startswith("intrusion"):
        return "Sensor", ""
    if key.startswith("in"):
        return "Voltage", "V"
    if key.startswith("curr"):
        return "Current", "A"
    if key.startswith("humidity"):
        return "Humidity", "%"
    return "Sensor", ""


def _from_nvidia_smi() -> Iterable[SensorReading]:
    binary = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
    if not binary:
        return []
    stdout = _run_command(
        [
            binary,
            "--query-gpu=name,temperature.gpu,fan.speed",
            "--format=csv,noheader,nounits",
        ],
        timeout=2,
    )
    if not stdout:
        return []
    return parse_nvidia_smi_csv(stdout)


def _from_windows() -> Iterable[SensorReading]:
    if sys.platform != "win32":
        return []
    readings: List[SensorReading] = []
    readings.extend(parse_windows_acpi_temps(_powershell_json(_ACPI_TEMP_SCRIPT)))
    readings.extend(parse_ohm_sensors(_powershell_json(_OHM_SENSOR_SCRIPT)))
    readings.extend(parse_hp_bios_numeric(_powershell_json(_HP_WMI_SCRIPT)))
    return readings


def _from_hpasmcli() -> Iterable[SensorReading]:
    if not shutil.which("hpasmcli"):
        return []
    temps = parse_hpasmcli_temp(_run_command(["hpasmcli", "-s", "show temp"], timeout=2))
    fans = parse_hpasmcli_fans(_run_command(["hpasmcli", "-s", "show fans"], timeout=2))
    return [*temps, *fans]


def _from_ipmi() -> Iterable[SensorReading]:
    if not shutil.which("ipmitool"):
        return []
    temps = parse_ipmitool_sdr(
        _run_command(["ipmitool", "sdr", "type", "Temperature"], timeout=2)
    )
    fans = parse_ipmitool_sdr(
        _run_command(["ipmitool", "sdr", "type", "Fan"], timeout=2)
    )
    return [*temps, *fans]


_ACPI_TEMP_SCRIPT = (
    "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
    "-ErrorAction SilentlyContinue | "
    "ForEach-Object { @{ Name = $_.InstanceName; "
    "C = [math]::Round(($_.CurrentTemperature / 10) - 273.15, 1); "
    "InstanceName = $_.InstanceName } } | ConvertTo-Json -Compress"
)

_HP_WMI_SCRIPT = (
    "$out = $null; "
    "foreach ($ns in @('root/HP/InstrumentedBIOS',"
    "'root/HewlettPackard/InstrumentedManagement','root/HPQ')) { "
    "  try { "
    "    $out = Get-CimInstance -Namespace $ns -ClassName HP_BIOSNumericSensor "
    "      -ErrorAction Stop | Select-Object Name, CurrentReading, Description; "
    "    if ($out) { break } "
    "  } catch {} "
    "} "
    "if ($out) { $out | ConvertTo-Json -Compress }"
)

_OHM_SENSOR_SCRIPT = (
    "$out = $null; "
    "foreach ($ns in @('root/LibreHardwareMonitor','root/OpenHardwareMonitor')) { "
    "  try { "
    "    $out = Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction Stop | "
    "      Select-Object Name, SensorType, Value, Identifier; "
    "    if ($out) { break } "
    "  } catch {} "
    "} "
    "if ($out) { $out | ConvertTo-Json -Compress }"
)


def _run_command(argv: list[str], timeout: float = 2) -> str:
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "check": False,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(argv, **kwargs)
    except (subprocess.SubprocessError, OSError):
        return ""
    return (result.stdout or "").strip()


def _powershell_json(script: str) -> Any:
    raw = _run_command(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        timeout=2,
    )
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _as_item_list(payload: Any) -> list[dict]:
    if payload is None:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _dedupe(readings: List[SensorReading]) -> List[SensorReading]:
    seen = set()
    unique: List[SensorReading] = []
    for reading in readings:
        key = reading_key(reading)
        if key in seen:
            continue
        seen.add(key)
        unique.append(reading)
    return unique


def humanize(text: str) -> str:
    raw = "" if text is None else str(text)
    cleaned = re.sub(r"[_\\-]+", " ", raw).strip()
    if not cleaned:
        return raw.strip()
    return " ".join(word.capitalize() for word in cleaned.split())
