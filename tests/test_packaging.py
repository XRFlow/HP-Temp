# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_inno_script_outputs_versioned_setup_exe() -> None:
    text = (ROOT / "packaging" / "hptemp.iss").read_text(encoding="utf-8")
    assert "OutputBaseFilename=HPTemp-{#MyAppVersion}-Setup" in text
    assert r'Source: "dist\HPTemp\*"' in text
    assert "SourceDir={#SourceRoot}" in text
    assert "AppPublisherEmail" not in text
    assert "ArchitecturesAllowed=x64compatible" in text


def test_windows_build_script_finds_64bit_inno() -> None:
    text = (ROOT / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
    assert "Find-ISCC" in text
    assert "Inno Setup 6" in text
    assert "Inno Setup 7" in text
    assert r"$env:ProgramFiles" in text
    assert "windows-portable.zip" in text
    assert "GITHUB_ACTIONS" in text


def test_ci_windows_job_uses_build_script() -> None:
    text = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "scripts/build_windows.ps1" in text or r"scripts\build_windows.ps1" in text
    assert "tags:" in text
    assert "gh release create" in text
