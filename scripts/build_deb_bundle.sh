#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Self-contained amd64 .deb that ships a PyInstaller bundle (no system PyQt).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
VERSION="$(
  ROOT_DIR="$ROOT_DIR" python3 -c 'import os, sys
sys.path.insert(0, os.path.join(os.environ["ROOT_DIR"], "src"))
from hptemp import __version__
print(__version__)
'
)"
APP_NAME="HPTemp"
PKG_NAME="hptemp"
BUNDLE_DIR="$ROOT_DIR/dist/$APP_NAME"
STAGE_DIR="$ROOT_DIR/build/deb-bundle"

python3 -m PyInstaller --noconfirm --clean \
  --distpath "$ROOT_DIR/dist" \
  --workpath "$ROOT_DIR/build/pyinstaller" \
  "$ROOT_DIR/packaging/hptemp.spec"

if [[ ! -x "$BUNDLE_DIR/$APP_NAME" ]]; then
  echo "PyInstaller did not produce $BUNDLE_DIR/$APP_NAME" >&2
  exit 1
fi

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR/DEBIAN" \
  "$STAGE_DIR/opt/$APP_NAME" \
  "$STAGE_DIR/usr/bin" \
  "$STAGE_DIR/usr/share/applications" \
  "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps" \
  "$STAGE_DIR/usr/share/doc/$PKG_NAME"

cp -a "$BUNDLE_DIR/." "$STAGE_DIR/opt/$APP_NAME/"

cat > "$STAGE_DIR/usr/bin/$PKG_NAME" <<LAUNCHER
#!/usr/bin/env bash
exec "/opt/$APP_NAME/$APP_NAME" "\$@"
LAUNCHER
chmod 755 "$STAGE_DIR/usr/bin/$PKG_NAME"

install -m 644 "$ROOT_DIR/packaging/$PKG_NAME.desktop" \
  "$STAGE_DIR/usr/share/applications/$PKG_NAME.desktop"
install -m 644 "$ROOT_DIR/packaging/$PKG_NAME.svg" \
  "$STAGE_DIR/usr/share/icons/hicolor/scalable/apps/$PKG_NAME.svg"
install -m 644 "$ROOT_DIR/LICENSE" \
  "$STAGE_DIR/usr/share/doc/$PKG_NAME/copyright"

cat > "$STAGE_DIR/DEBIAN/control" <<CONTROL
Package: $PKG_NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Depends: libc6, libgl1, libglib2.0-0, libxkbcommon0, libdbus-1-3, libfontconfig1, libfreetype6, libxcb1
Recommends: lm-sensors, nvidia-smi, ipmitool, libxcb-cursor0
Maintainer: XRFlow <support@xrflows.com>
Description: Self-contained HP Z workstation temperature and fan monitor
 Bundled Qt dashboard and tray app. Does not require system Python or PyQt.
CONTROL

DEB_PATH="$ROOT_DIR/build/${PKG_NAME}_${VERSION}_amd64.deb"
dpkg-deb --build "$STAGE_DIR" "$DEB_PATH" >/dev/null
echo "Built $DEB_PATH"
