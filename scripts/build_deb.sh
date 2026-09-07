#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(
  ROOT_DIR="$ROOT_DIR" python3 -c 'import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT_DIR"], "src"))
from hptemp import __version__
print(__version__)
'
)"
STAGE_DIR="$ROOT_DIR/build/deb-root"

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR/DEBIAN" \
  "$STAGE_DIR/usr/bin" \
  "$STAGE_DIR/usr/lib/hptemp" \
  "$STAGE_DIR/usr/share/applications" \
  "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE_DIR/usr/share/doc/hptemp"

cat > "$STAGE_DIR/DEBIAN/control" <<CONTROL
Package: hptemp
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3, python3-psutil, python3-pyqt6, lm-sensors
Recommends: nvidia-smi, python3-pyqt6.qtcharts, ipmitool
Maintainer: XRFlow <support@xrflows.com>
Description: Desktop monitor for CPU/GPU temperatures and fan speeds
 A lightweight Qt dashboard and tray app for monitoring hardware sensors.
CONTROL

cat > "$STAGE_DIR/usr/bin/hptemp" <<'LAUNCHER'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/hptemp"
exec /usr/bin/python3 -m hptemp "$@"
LAUNCHER
chmod 755 "$STAGE_DIR/usr/bin/hptemp"

python3 - "$ROOT_DIR/src/hptemp" "$STAGE_DIR/usr/lib/hptemp/hptemp" <<'PY'
import shutil
import sys
from pathlib import Path

src, dest = Path(sys.argv[1]), Path(sys.argv[2])
if dest.exists():
    shutil.rmtree(dest)
shutil.copytree(
    src,
    dest,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
)
PY

install -m 644 "$ROOT_DIR/packaging/hptemp.desktop" \
  "$STAGE_DIR/usr/share/applications/hptemp.desktop"
install -m 644 "$ROOT_DIR/packaging/hptemp.svg" \
  "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps/hptemp.svg"
install -m 644 "$ROOT_DIR/LICENSE" \
  "$STAGE_DIR/usr/share/doc/hptemp/copyright"
install -m 644 "$ROOT_DIR/packaging/copyright" \
  "$STAGE_DIR/usr/share/doc/hptemp/copyright.debian"

OUTPUT_DIR="$ROOT_DIR/build"
mkdir -p "$OUTPUT_DIR"

DEB_PATH="$OUTPUT_DIR/hptemp_${VERSION}_all.deb"
dpkg-deb --build "$STAGE_DIR" "$DEB_PATH" > /dev/null

echo "Built $DEB_PATH"
