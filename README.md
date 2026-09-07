# HPTemp

HPTemp is an HP-oriented desktop monitor for CPU, GPU, chassis, and workstation sensors on Linux and Windows. It is built for HP Z-series workstations (including Z2) and other HP business-class machines.

Copyright (C) 2026 XRFlow. Contact: support@xrflows.com.

HPTemp is **not affiliated with, endorsed by, or a product of HP Inc.** “HP” and “Z” are trademarks of HP Inc.

## What it reads

On top of the usual `lm-sensors` / `nvidia-smi` / psutil sources, HPTemp looks for HP hardware paths:

| Source | Platform | Notes |
| --- | --- | --- |
| `lm-sensors` (including `hp-wmi-sensors`) | Linux | Load `hp-wmi-sensors` when the kernel provides it |
| `hpasmcli` (`show temp` / `show fans`) | Linux | HP System Management / hp-health, when installed |
| `ipmitool sdr` | Linux | BMC/IPMI on some Z and ProLiant systems |
| `nvidia-smi` | Linux and Windows | NVIDIA GPU temp and fan |
| ACPI thermal WMI | Windows | Built-in thermal zones |
| Libre / Open Hardware Monitor | Windows | Best CPU/fan coverage on Z2 |
| HP BIOS numeric WMI | Windows | HP Client Management namespaces, when present |

## Linux

```bash
sudo apt install python3-psutil python3-pyqt6 lm-sensors python3-pyqt6.qtcharts ipmitool
sudo sensors-detect --auto
# Optional: hpasmcli from HP System Management / hp-health packages
cd ~/projects/hptemp
PYTHONPATH=src python3 -m hptemp
```

Or `~/projects/hptemp/scripts/run.sh`.

User launcher:

```bash
~/projects/hptemp/scripts/install_user.sh
```

Settings: `~/.config/hptemp/settings.json`.

### .deb

```bash
./scripts/build_deb.sh
sudo dpkg -i build/hptemp_0.3.0_all.deb
```

## Windows (Z2 and other HP workstations)

For the fullest sensor list on a Z2, install **Libre Hardware Monitor** and NVIDIA drivers, then run HPTemp.

From source:

```powershell
pip install -r requirements.txt
$env:PYTHONPATH = "src"
python -m hptemp
```

Installers (built by GitHub Actions on `main`):

- `HPTemp-<version>-Setup.exe`
- `HPTemp-<version>.msi`
- `HPTemp-<version>-windows-portable.zip`

Local Windows build: `.\scripts\build_windows.ps1`

Settings: `%APPDATA%\HPTemp\settings.json`.

## Tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src python3 -m pytest tests
```

## License

GNU General Public License v3.0 or later. See [LICENSE](LICENSE).
