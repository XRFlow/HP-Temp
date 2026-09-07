# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).resolve().parent
src = root / "src"
icon = root / "packaging" / "hptemp.ico"

qt_datas, qt_binaries, qt_hidden = collect_all("PyQt6")
extra_datas = [
    (str(root / "packaging" / "hptemp.svg"), "packaging"),
    (str(root / "LICENSE"), "."),
]
if icon.exists():
    extra_datas.append((str(icon), "packaging"))

a = Analysis(
    [str(root / "packaging" / "windows_entry.py")],
    pathex=[str(src)],
    binaries=qt_binaries,
    datas=qt_datas + extra_datas,
    hiddenimports=qt_hidden
    + [
        "hptemp",
        "hptemp.app",
        "hptemp.sensors",
        "hptemp.settings",
        "hptemp.ui",
        "PyQt6.QtCharts",
        "PyQt6.QtSvg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe_kwargs = dict(
    exclude_binaries=True,
    name="HPTemp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
if icon.exists():
    exe_kwargs["icon"] = str(icon)
exe = EXE(pyz, a.scripts, [], **exe_kwargs)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="HPTemp",
)
