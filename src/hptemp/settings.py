# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


DEFAULT_TOOLTIP_LIMIT = 3
DEFAULT_REFRESH_MS = 2000
DEFAULT_ALERT_TEMP_C = 85.0
DEFAULT_ALERT_COOLDOWN_SEC = 300
DEFAULT_LOG_INTERVAL_SEC = 10

REFRESH_MS_MIN = 500
REFRESH_MS_MAX = 10000
TOOLTIP_LIMIT_MIN = 1
TOOLTIP_LIMIT_MAX = 10
ALERT_TEMP_MIN = 40.0
ALERT_TEMP_MAX = 120.0
ALERT_COOLDOWN_MIN = 30
ALERT_COOLDOWN_MAX = 3600
LOG_INTERVAL_MIN = 1
LOG_INTERVAL_MAX = 60

VALID_TOOLTIP_MODES = {"hottest", "favorites"}
VALID_TEMP_UNITS = {"C", "F"}
VALID_ALERT_SCOPES = {"all", "favorites", "tray"}


@dataclass
class Settings:
    refresh_ms: int = DEFAULT_REFRESH_MS
    tooltip_limit: int = DEFAULT_TOOLTIP_LIMIT
    tooltip_mode: str = "hottest"
    favorites: set[str] = field(default_factory=set)
    tray_sensor_key: str = ""
    icon_temp_unit: str = "C"
    show_favorites_only: bool = False
    search_text: str = ""
    alert_temp_c: float = DEFAULT_ALERT_TEMP_C
    alert_cooldown_sec: int = DEFAULT_ALERT_COOLDOWN_SEC
    alerts_enabled: bool = True
    alert_scope: str = "all"
    logging_enabled: bool = False
    log_interval_sec: int = DEFAULT_LOG_INTERVAL_SEC
    start_minimized: bool = False
    autostart_enabled: bool = False

    def copy(self) -> "Settings":
        return replace(self, favorites=set(self.favorites))

    def clamp(self) -> "Settings":
        self.refresh_ms = _clamp_int(self.refresh_ms, REFRESH_MS_MIN, REFRESH_MS_MAX)
        self.tooltip_limit = _clamp_int(
            self.tooltip_limit, TOOLTIP_LIMIT_MIN, TOOLTIP_LIMIT_MAX
        )
        if self.tooltip_mode not in VALID_TOOLTIP_MODES:
            self.tooltip_mode = "hottest"
        unit = str(self.icon_temp_unit or "C").upper()
        self.icon_temp_unit = unit if unit in VALID_TEMP_UNITS else "C"
        self.alert_temp_c = _clamp_float(
            self.alert_temp_c, ALERT_TEMP_MIN, ALERT_TEMP_MAX
        )
        self.alert_cooldown_sec = _clamp_int(
            self.alert_cooldown_sec, ALERT_COOLDOWN_MIN, ALERT_COOLDOWN_MAX
        )
        if self.alert_scope not in VALID_ALERT_SCOPES:
            self.alert_scope = "all"
        self.log_interval_sec = _clamp_int(
            self.log_interval_sec, LOG_INTERVAL_MIN, LOG_INTERVAL_MAX
        )
        self.search_text = str(self.search_text or "")
        self.tray_sensor_key = str(self.tray_sensor_key or "")
        self.favorites = {str(item) for item in self.favorites}
        return self

    def to_json(self) -> dict:
        return {
            "refresh_ms": self.refresh_ms,
            "tooltip_limit": self.tooltip_limit,
            "tooltip_mode": self.tooltip_mode,
            "favorites": sorted(self.favorites),
            "tray_sensor_key": self.tray_sensor_key,
            "icon_temp_unit": self.icon_temp_unit,
            "show_favorites_only": self.show_favorites_only,
            "search_text": self.search_text,
            "alert_temp_c": self.alert_temp_c,
            "alert_cooldown_sec": self.alert_cooldown_sec,
            "alerts_enabled": self.alerts_enabled,
            "alert_scope": self.alert_scope,
            "logging_enabled": self.logging_enabled,
            "log_interval_sec": self.log_interval_sec,
            "start_minimized": self.start_minimized,
            "autostart_enabled": self.autostart_enabled,
        }

    @classmethod
    def from_json(cls, payload: Any) -> "Settings":
        settings = cls()
        if not isinstance(payload, dict):
            return settings
        settings.refresh_ms = _as_int(payload.get("refresh_ms"), settings.refresh_ms)
        settings.tooltip_limit = _as_int(
            payload.get("tooltip_limit"), settings.tooltip_limit
        )
        settings.tooltip_mode = _as_str(
            payload.get("tooltip_mode"), settings.tooltip_mode
        )
        settings.favorites = _as_str_set(payload.get("favorites"), settings.favorites)
        settings.tray_sensor_key = _as_str(
            payload.get("tray_sensor_key"), settings.tray_sensor_key
        )
        settings.icon_temp_unit = _as_str(
            payload.get("icon_temp_unit"), settings.icon_temp_unit
        )
        settings.show_favorites_only = _as_bool(
            payload.get("show_favorites_only"), settings.show_favorites_only
        )
        settings.search_text = _as_str(payload.get("search_text"), settings.search_text)
        settings.alert_temp_c = _as_float(
            payload.get("alert_temp_c"), settings.alert_temp_c
        )
        settings.alert_cooldown_sec = _as_int(
            payload.get("alert_cooldown_sec"), settings.alert_cooldown_sec
        )
        settings.alerts_enabled = _as_bool(
            payload.get("alerts_enabled"), settings.alerts_enabled
        )
        settings.alert_scope = _as_str(payload.get("alert_scope"), settings.alert_scope)
        settings.logging_enabled = _as_bool(
            payload.get("logging_enabled"), settings.logging_enabled
        )
        settings.log_interval_sec = _as_int(
            payload.get("log_interval_sec"), settings.log_interval_sec
        )
        settings.start_minimized = _as_bool(
            payload.get("start_minimized"), settings.start_minimized
        )
        settings.autostart_enabled = _as_bool(
            payload.get("autostart_enabled"), settings.autostart_enabled
        )
        return settings.clamp()


def _is_windows() -> bool:
    return os.name == "nt"


def config_path() -> Path:
    if _is_windows():
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        return base / "HPTemp" / "settings.json"
    return Path.home() / ".config" / "hptemp" / "settings.json"


def data_dir() -> Path:
    if _is_windows():
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "HPTemp"
    return Path.home() / ".local" / "share" / "hptemp"


def logs_dir() -> Path:
    return data_dir() / "logs"


def load_settings() -> Settings:
    path = config_path()
    if not path.exists():
        return Settings()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError, AttributeError):
        return Settings()
    try:
        return Settings.from_json(payload)
    except (TypeError, ValueError, AttributeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(settings.clamp().to_json(), indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix="settings.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _as_int(value: Any, default: int) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_str(value: Any, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return default
    return str(value)


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return default


def _as_str_set(value: Any, default: set[str]) -> set[str]:
    if value is None:
        return set(default)
    if not isinstance(value, list):
        return set(default)
    return {str(item) for item in value}
