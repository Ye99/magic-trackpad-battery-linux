#!/usr/bin/env bash
# Remove everything install.sh set up.
set -euo pipefail
systemctl --user disable --now trackpad-battery.timer 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/trackpad-battery.service" \
      "$HOME/.config/systemd/user/trackpad-battery.timer" \
      "$HOME/.local/bin/trackpad-battery"
systemctl --user daemon-reload
sudo rm -f /etc/udev/rules.d/70-magic-trackpad-battery.rules
sudo udevadm control --reload
