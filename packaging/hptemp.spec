# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

root = Path(SPECPATH).resolve().parent.parent
src = root / "src"

a = Analysis(
    [str(root / "packaging" / "windows_entry.py")],
    pathex=[str(src)],
    binaries=[],
    datas=[
        (str(root / "packaging" / "hptemp.svg"), "packaging"),
        (str(root / "packaging" / "hptemp.ico"), "packaging"),
        (str(root / "LICENSE"), "."),
    ],
    hiddenimports=[
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
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HPTemp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(root / "packaging" / "hptemp.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="HPTemp",
)
