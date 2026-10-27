#!/usr/bin/env bash
# Install the tray indicator as a systemd user service.
set -euo pipefail

TARGET="$HOME/.local/share/claude-limits"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT="$HOME/.config/systemd/user/claude-limits.service"

if ! /usr/bin/python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("AyatanaAppIndicator3","0.1")' 2>/dev/null; then
    echo "Missing dependencies. On Ubuntu/Debian:" >&2
    echo "  sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1" >&2
    exit 1
fi

if [ "$HERE" != "$TARGET" ]; then
    echo "Copying to $TARGET"
    mkdir -p "$TARGET"
    cp -r "$HERE/claude-limits-tray.py" "$HERE/make-icons.py" "$HERE/icons" "$TARGET/"
fi

mkdir -p "$(dirname "$UNIT")"
cp "$HERE/claude-limits.service" "$UNIT"
systemctl --user daemon-reload
systemctl --user enable --now claude-limits.service
systemctl --user --no-pager status claude-limits.service | head -5

echo
echo "If no icon appears, make sure the AppIndicator shell extension is enabled:"
echo "  gnome-extensions enable ubuntu-appindicators@ubuntu.com"
