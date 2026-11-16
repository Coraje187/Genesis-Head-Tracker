#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/.local/share/genesis-head-tracker"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR"
cp -r "$SCRIPT_DIR/GenesisHeadTracker"/* "$APP_DIR/"
chmod +x "$APP_DIR/GenesisHeadTracker"
ln -sf "$APP_DIR/GenesisHeadTracker" "$BIN_DIR/genesis-head-tracker"

cat > "$DESKTOP_DIR/genesis-head-tracker.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Genesis Head Tracker
Comment=6-DOF MediaPipe Head Tracker (200 Hz OpenTrack UDP)
Exec=$APP_DIR/GenesisHeadTracker
Icon=$APP_DIR/assets/icon.png
Terminal=false
Categories=Game;Utility;
EOF

echo "Installed Genesis Head Tracker!"
echo "Launch from your app menu or run: genesis-head-tracker"
