# SPDX-License-Identifier: GPL-3.0-or-later
import json

from hptemp.settings import (
    DEFAULT_ALERT_TEMP_C,
    DEFAULT_REFRESH_MS,
    REFRESH_MS_MIN,
    Settings,
    load_settings,
    save_settings,
)


def test_from_json_rejects_non_object() -> None:
    settings = Settings.from_json(["not", "a", "dict"])
    assert settings.refresh_ms == DEFAULT_REFRESH_MS
    assert settings.favorites == set()


def test_from_json_skips_bad_fields_and_clamps() -> None:
    settings = Settings.from_json(
        {
            "refresh_ms": "fast",
            "alert_temp_c": None,
            "favorites": {"nope": 1},
            "tooltip_mode": "mystery",
            "icon_temp_unit": "K",
            "log_interval_sec": 1,
            "alerts_enabled": False,
            "alert_scope": "favorites",
        }
    )
    assert settings.refresh_ms == DEFAULT_REFRESH_MS
    assert settings.alert_temp_c == DEFAULT_ALERT_TEMP_C
    assert settings.favorites == set()
    assert settings.tooltip_mode == "hottest"
    assert settings.icon_temp_unit == "C"
    assert settings.log_interval_sec == 1
    assert settings.alerts_enabled is False
    assert settings.alert_scope == "favorites"

    clamped = Settings.from_json({"refresh_ms": 1, "alert_temp_c": 999})
    assert clamped.refresh_ms == REFRESH_MS_MIN
    assert clamped.alert_temp_c == 120.0


def test_from_json_accepts_favorites_list() -> None:
    settings = Settings.from_json({"favorites": ["a", "b"]})
    assert settings.favorites == {"a", "b"}


def test_load_settings_invalid_json(tmp_path, monkeypatch) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr("hptemp.settings.config_path", lambda: path)
    settings = load_settings()
    assert settings.refresh_ms == DEFAULT_REFRESH_MS


def test_load_settings_bad_types_do_not_crash(tmp_path, monkeypatch) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"refresh_ms": "fast", "favorites": {}, "alert_temp_c": "hot"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("hptemp.settings.config_path", lambda: path)
    settings = load_settings()
    assert settings.refresh_ms == DEFAULT_REFRESH_MS
    assert settings.favorites == set()


def test_save_settings_atomic_round_trip(tmp_path, monkeypatch) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setattr("hptemp.settings.config_path", lambda: path)
    original = Settings(refresh_ms=1500, favorites={"one"}, alerts_enabled=False)
    save_settings(original)
    assert path.exists()
    assert list(tmp_path.glob("settings.*.tmp")) == []
    loaded = load_settings()
    assert loaded.refresh_ms == 1500
    assert loaded.favorites == {"one"}
    assert loaded.alerts_enabled is False


def test_copy_isolates_favorites() -> None:
    settings = Settings(favorites={"a"})
    clone = settings.copy()
    clone.favorites.add("b")
    assert settings.favorites == {"a"}


def test_windows_config_paths(tmp_path, monkeypatch) -> None:
    from hptemp import settings as settings_mod

    monkeypatch.setattr(settings_mod, "_is_windows", lambda: True)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert settings_mod.config_path() == tmp_path / "Roaming" / "HPTemp" / "settings.json"
    assert settings_mod.data_dir() == tmp_path / "Local" / "HPTemp"
    assert settings_mod.logs_dir() == tmp_path / "Local" / "HPTemp" / "logs"
