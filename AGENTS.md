# Repository Guidelines

## Overview
HPTemp is a PyQt6 desktop tray + dashboard aimed at HP Z workstations. Collectors: psutil, lm-sensors (including hp-wmi-sensors), hpasmcli, ipmitool, nvidia-smi, Windows ACPI/LHM, and HP BIOS WMI. Python sources live under `src/hptemp/`.

## Project Structure & Module Organization
- `src/hptemp/`: application source (`app.py` UI/tray, `sensors.py` collectors, `settings.py` persistence).
- `tests/`: unit tests mirroring `src/hptemp` modules (e.g. `tests/test_sensors.py`).
- `packaging/`: Linux desktop/SVG, Windows ICO, PyInstaller spec, Inno Setup script, WiX MSI sources.
- `LICENSE`: GNU GPL v3 (or later).
- `scripts/build_deb.sh`: Debian package builder.
- `scripts/build_windows.ps1`: Windows onedir + EXE installer + MSI (run on Windows).
- `.github/workflows/build.yml`: CI for `.deb`, Setup.exe, MSI, and portable zip.
- `assets/` (optional): static files such as images or data fixtures.

If you introduce a new top-level directory, document it here.

## Build, Test, and Development Commands
- `./scripts/run.sh` — run the dashboard from source (cwd-independent).
- `./scripts/install_user.sh` — install a user launcher (`~/.local/bin/hptemp`) so the app grid runs this tree.
- `PYTHONPATH=src python3 -m hptemp` — same, but must be run from the repo root.
- `PYTHONPATH=src python3 -m pytest tests` — run the unit test suite.
- `./scripts/build_deb.sh` — build `build/hptemp_<version>_all.deb`.
- `./scripts/build_windows.ps1` — Windows PyInstaller + Inno EXE + WiX MSI (Windows only).

## Coding Style & Naming Conventions
- Indentation: 2 spaces for web languages, 4 spaces for Python, and tabs only if the language standard requires it.
- Filenames: `lower_snake_case` for scripts, `kebab-case` for config files (e.g., `lint-config.yaml`).
- Modules/classes: prefer `PascalCase` for class names and `snake_case` for functions unless the language community standard differs.
- If you add a formatter or linter (e.g., `black`, `prettier`, `ruff`), document exact versions and commands.

## Testing Guidelines
- Place tests under `tests/` with names matching the target module (e.g., `tests/test_sensors.py`).
- Prefer deterministic, isolated tests; use fixtures in `tests/fixtures/` if needed.
- Tests should not require a display or live hardware; mock `psutil` and subprocess collectors.

## Commit & Pull Request Guidelines
- Use clear, imperative messages like `Harden sensor collection and settings persistence`.
- Pull requests should include: a short summary, rationale, test evidence (commands + results), and any screenshots for UI changes.
- Link related issues if they exist (e.g., `Fixes #12`).

## Security & Configuration Tips
- Do not commit secrets. Use `.env` or similar local config files and add them to `.gitignore`.
- User settings are stored in `~/.config/hptemp/settings.json`. Do not log that file in issues if it may contain machine-specific paths.
