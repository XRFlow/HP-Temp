# SPDX-License-Identifier: GPL-3.0-or-later
import json

from hptemp.sensors import (
    SensorReading,
    collect_readings,
    celsius_to_fahrenheit,
    format_sensor_value,
    parse_lm_sensors_payload,
    parse_nvidia_smi_csv,
    parse_hp_bios_numeric,
    parse_hpasmcli_fans,
    parse_hpasmcli_temp,
    parse_ipmitool_sdr,
    parse_ohm_sensors,
    parse_windows_acpi_temps,
    reading_key,
    sanitize_lm_sensors_json,
)


def test_celsius_to_fahrenheit() -> None:
    assert celsius_to_fahrenheit(0) == 32
    assert celsius_to_fahrenheit(100) == 212
    assert round(celsius_to_fahrenheit(85), 1) == 185.0


def test_format_sensor_value_temp_and_integer() -> None:
    display, unit = format_sensor_value(45.0, "°C")
    assert display == "45.0 / 113.0"
    assert unit == "°C/°F"
    assert format_sensor_value(1200.0, "RPM") == ("1200", "RPM")
    assert format_sensor_value(1.5, "V") == ("1.5", "V")


def test_sanitize_lm_sensors_nan() -> None:
    raw = '{"chip": {"temp1": {"temp1_input": NaN, "temp1_max": Inf}}}'
    payload = json.loads(sanitize_lm_sensors_json(raw))
    assert payload["chip"]["temp1"]["temp1_input"] is None
    assert payload["chip"]["temp1"]["temp1_max"] is None


def test_sanitize_lm_sensors_signed_nan_keeps_siblings() -> None:
    raw = (
        '{"chip": {"temp1": {"temp1_input": -NaN, "temp1_max": -Inf},'
        ' "temp2": {"temp2_input": 41.0}}}'
    )
    payload = json.loads(sanitize_lm_sensors_json(raw))
    assert payload["chip"]["temp1"]["temp1_input"] is None
    assert payload["chip"]["temp1"]["temp1_max"] is None
    readings = parse_lm_sensors_payload(payload)
    assert len(readings) == 1
    assert readings[0].value == 41.0


def test_parse_skips_non_finite_values() -> None:
    payload = {
        "chip": {
            "temp1": {"temp1_input": float("nan")},
            "temp2": {"temp2_input": float("inf")},
            "temp3": {"temp3_input": 40.0},
        }
    }
    readings = parse_lm_sensors_payload(payload)
    assert len(readings) == 1
    assert readings[0].identity == "temp3_input"

    nvidia = parse_nvidia_smi_csv("GPU, inf, 30\nOther, 55, nan\n")
    assert len(nvidia) == 2
    assert nvidia[0].identity == "fan.speed"
    assert nvidia[0].value == 30.0
    assert nvidia[1].identity == "temperature.gpu"
    assert nvidia[1].value == 55.0


def test_parse_lm_sensors_keeps_unlabeled_siblings() -> None:
    payload = {
        "acpitz-acpi-0": {
            "Adapter": "ACPI interface",
            "temp1": {"temp1_input": 44.0},
            "temp2": {"temp2_input": 51.0},
        }
    }
    readings = parse_lm_sensors_payload(payload)
    assert len(readings) == 2
    keys = {reading_key(item) for item in readings}
    assert len(keys) == 2
    identities = {item.identity for item in readings}
    assert identities == {"temp1_input", "temp2_input"}


def test_parse_lm_sensors_skips_non_input_and_nulls() -> None:
    payload = {
        "coretemp-isa-0000": {
            "Package id 0": {
                "temp1_input": 45.0,
                "temp1_max": 100.0,
                "temp1_crit": None,
            }
        }
    }
    readings = parse_lm_sensors_payload(payload)
    assert len(readings) == 1
    assert readings[0].name == "Package Id 0"
    assert readings[0].value == 45.0


def test_parse_nvidia_smi_csv_handles_commas_in_name() -> None:
    text = "NVIDIA GeForce RTX 4090, 24GB, 70, 40\nGPU, N/A, N/A\n"
    readings = parse_nvidia_smi_csv(text)
    assert len(readings) == 2
    assert readings[0].name == "Nvidia Geforce Rtx 4090, 24gb"
    assert readings[0].value == 70.0
    assert readings[1].value == 40.0
    assert readings[1].unit == "%"


def test_collect_readings_prefers_lm_sensors(monkeypatch) -> None:
    psutil_temp = [
        SensorReading(
            category="Temperature",
            name="Package",
            value=40.0,
            unit="°C",
            source="psutil",
            group="Coretemp",
            identity="0",
        )
    ]
    lm_temp = [
        SensorReading(
            category="Temperature",
            name="Package",
            value=41.0,
            unit="°C",
            source="lm-sensors",
            group="Coretemp Isa 0000",
            identity="temp1_input",
        )
    ]
    monkeypatch.setattr("hptemp.sensors._from_psutil_temps", lambda: psutil_temp)
    monkeypatch.setattr("hptemp.sensors._from_psutil_fans", lambda: [])
    monkeypatch.setattr("hptemp.sensors._from_lm_sensors", lambda: lm_temp)
    monkeypatch.setattr("hptemp.sensors._from_nvidia_smi", lambda: [])
    readings = collect_readings()
    assert [item.source for item in readings] == ["lm-sensors"]


def test_collect_readings_isolates_collector_failure(monkeypatch) -> None:
    def boom() -> list:
        raise OSError("sysfs missing")

    nvidia = [
        SensorReading(
            category="GPU Temperature",
            name="Gpu",
            value=60.0,
            unit="°C",
            source="nvidia-smi",
            group="GPU 0",
            identity="temperature.gpu",
        )
    ]
    monkeypatch.setattr("hptemp.sensors._from_psutil_temps", boom)
    monkeypatch.setattr("hptemp.sensors._from_psutil_fans", boom)
    monkeypatch.setattr("hptemp.sensors._from_lm_sensors", boom)
    monkeypatch.setattr("hptemp.sensors._from_nvidia_smi", lambda: nvidia)
    readings = collect_readings()
    assert len(readings) == 1
    assert readings[0].source == "nvidia-smi"


def test_parse_windows_acpi_temps() -> None:
    payload = [
        {"Name": "ACPI\\ThermalZone\\TZ01", "C": 47.5, "InstanceName": "TZ01"},
        {"InstanceName": "TZ02", "CurrentTemperature": 3100},
    ]
    readings = parse_windows_acpi_temps(payload)
    assert len(readings) == 2
    assert readings[0].value == 47.5
    assert readings[0].source == "wmi"
    assert round(readings[1].value, 1) == 36.9


def test_parse_ohm_sensors() -> None:
    payload = {
        "Name": "CPU Package",
        "SensorType": "Temperature",
        "Value": 62.0,
        "Identifier": "/intelcpu/0/temperature/0",
    }
    readings = parse_ohm_sensors(payload)
    assert len(readings) == 1
    assert readings[0].source == "lhm"
    assert readings[0].unit == "°C"


def test_parse_hpasmcli_temp_and_fans() -> None:
    temps = parse_hpasmcli_temp(
        "Sensor   Location              Temp       Threshold\n"
        "#1        AMBIENT              23C/73F    42C/107F\n"
        "#2        CPU#1                40C/104F   82C/179F\n"
        "#3        MEMORY_BD             -         87C/188F\n"
    )
    assert [item.name for item in temps] == ["Ambient", "Cpu#1"]
    assert temps[0].value == 23.0
    assert temps[0].source == "hpasmcli"
    fans = parse_hpasmcli_fans(
        "#1   CPU             Yes     47%       Normal\n"
        "#2   SYSTEM          Yes     2100RPM   Normal\n"
    )
    assert len(fans) == 2
    assert fans[0].unit == "%"
    assert fans[0].value == 47.0
    assert fans[1].unit == "RPM"
    assert fans[1].value == 2100.0


def test_parse_ipmitool_sdr() -> None:
    text = (
        "CPU Temp         | 45 degrees C      | ok\n"
        "Fan 1            | 4200 RPM          | ok\n"
        "Inlet            | disabled          | ns\n"
    )
    readings = parse_ipmitool_sdr(text)
    assert len(readings) == 2
    assert readings[0].source == "ipmi"
    assert readings[0].value == 45.0
    assert readings[1].unit == "RPM"


def test_parse_hp_bios_numeric() -> None:
    payload = {"Name": "CPU Temperature", "CurrentReading": 51.0}
    readings = parse_hp_bios_numeric(payload)
    assert len(readings) == 1
    assert readings[0].source == "hp-wmi"
    assert readings[0].category == "Temperature"
