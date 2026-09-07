# SPDX-License-Identifier: GPL-3.0-or-later
from hptemp.app import _autostart_command, _desktop_quote, ensure_autostart


def test_autostart_uses_installed_binary(monkeypatch, tmp_path) -> None:
    binary = tmp_path / "hptemp"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setattr("hptemp.app.sys.platform", "linux")
    monkeypatch.setattr("hptemp.app.shutil.which", lambda name: str(binary) if name == "hptemp" else None)
    assert _autostart_command() == str(binary)


def test_desktop_quote_uses_desktop_spec() -> None:
    assert _desktop_quote("/usr/bin/hptemp") == "/usr/bin/hptemp"
    assert _desktop_quote("/home/user/My Src") == '"/home/user/My Src"'
    assert _desktop_quote('/tmp/say"hi') == '"/tmp/say\\"hi"'


def test_autostart_quotes_paths_with_spaces(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr("hptemp.app.sys.platform", "linux")
    monkeypatch.setattr("hptemp.app.Path.home", lambda: home)
    monkeypatch.setattr(
        "hptemp.app.shutil.which",
        lambda name: "/opt/My Apps/hptemp" if name == "hptemp" else None,
    )
    ensure_autostart(True, minimized=True)
    text = (home / ".config" / "autostart" / "hptemp.desktop").read_text(
        encoding="utf-8"
    )
    assert 'Exec="/opt/My Apps/hptemp" --minimized' in text


def test_windows_autostart_writes_startup_bat(monkeypatch, tmp_path) -> None:
    from hptemp.app import _ensure_autostart_windows, _windows_startup_path

    roaming = tmp_path / "Roaming"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setattr("hptemp.app.sys.executable", str(tmp_path / "python.exe"))
    _ensure_autostart_windows(True, minimized=True)
    path = _windows_startup_path()
    text = path.read_text(encoding="utf-8")
    assert path.exists()
    assert "--minimized" in text
    _ensure_autostart_windows(False, minimized=True)
    assert not path.exists()


def test_ensure_autostart_honors_minimized(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    monkeypatch.setattr("hptemp.app.sys.platform", "linux")
    monkeypatch.setattr("hptemp.app.Path.home", lambda: home)
    monkeypatch.setattr("hptemp.app.shutil.which", lambda name: "/usr/bin/hptemp")

    ensure_autostart(True, minimized=True)
    path = home / ".config" / "autostart" / "hptemp.desktop"
    text = path.read_text(encoding="utf-8")
    assert "Exec=/usr/bin/hptemp --minimized" in text

    ensure_autostart(True, minimized=False)
    text = path.read_text(encoding="utf-8")
    assert "Exec=/usr/bin/hptemp\n" in text
    assert "--minimized" not in text

    ensure_autostart(False, minimized=True)
    assert not path.exists()
