#!/usr/bin/env bash
# Remove everything install.sh set up.
set -euo pipefail
units="$HOME/.config/systemd/user"

if systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user disable --now trackpad-battery.timer || true
fi
rm -f "$units/trackpad-battery.service" "$units/trackpad-battery.timer" \
      "$HOME/.local/bin/trackpad-battery"
if systemctl --user show-environment >/dev/null 2>&1; then
    systemctl --user daemon-reload
fi

sudo rm -f /etc/udev/rules.d/70-magic-trackpad-battery.rules
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw
