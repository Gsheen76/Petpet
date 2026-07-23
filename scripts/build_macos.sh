#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

python3 -m pip install -r requirements-macos.txt
python3 make_icons.py

ICONSET_DIR="$PROJECT_DIR/build/Petpet.iconset"
mkdir -p "$ICONSET_DIR"

cp icons/icon-16.png "$ICONSET_DIR/icon_16x16.png"
cp icons/icon-32.png "$ICONSET_DIR/icon_16x16@2x.png"
cp icons/icon-32.png "$ICONSET_DIR/icon_32x32.png"
cp icons/icon-64.png "$ICONSET_DIR/icon_32x32@2x.png"
cp icons/icon-128.png "$ICONSET_DIR/icon_128x128.png"
cp icons/icon-256.png "$ICONSET_DIR/icon_128x128@2x.png"
cp icons/icon-256.png "$ICONSET_DIR/icon_256x256.png"
cp icons/icon-512.png "$ICONSET_DIR/icon_256x256@2x.png"
cp icons/icon-512.png "$ICONSET_DIR/icon_512x512.png"
cp icons/icon-1024.png "$ICONSET_DIR/icon_512x512@2x.png"

iconutil -c icns "$ICONSET_DIR" -o "$PROJECT_DIR/build/Petpet.icns"
python3 -m PyInstaller --noconfirm --clean packaging/Petpet-mac.spec

echo "Built: $PROJECT_DIR/dist/Petpet.app"
