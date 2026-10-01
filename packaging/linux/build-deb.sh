#!/usr/bin/env bash
set -euo pipefail
version=1.0.1
arch=amd64
root="build/deb/thrust-measure_${version}_${arch}"
mkdir -p "$root/DEBIAN" "$root/opt/thrust-measure" "$root/usr/share/applications" "$root/usr/share/icons/hicolor/256x256/apps" release
cp -a dist/THRUST-measure/. "$root/opt/thrust-measure/"
cp LICENSE EULA.txt "$root/opt/thrust-measure/"
cp packaging/linux/thrust-measure.desktop "$root/usr/share/applications/"
cp build/thrust-measure.png "$root/usr/share/icons/hicolor/256x256/apps/thrust-measure.png"
cat > "$root/DEBIAN/control" <<EOF
Package: thrust-measure
Version: ${version}
Section: science
Priority: optional
Architecture: ${arch}
Maintainer: Zoltán Szőke <szokezoltan95@users.noreply.github.com>
Depends: libc6, libegl1, libgl1, libdbus-1-3, libxkbcommon-x11-0, libxcb-cursor0
Description: THRUST UAV pilot measurement client
 Bundled Python, PyQt6, Pygame, and measurement modules.
EOF
chmod 755 "$root/opt/thrust-measure/THRUST-measure"
dpkg-deb --build --root-owner-group "$root" "release/THRUST-measure-${version}-linux-${arch}.deb"
