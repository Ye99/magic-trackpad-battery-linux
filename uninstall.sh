#!/usr/bin/env bash
# Remove everything install.sh set up.
set -euo pipefail
units="$HOME/.config/systemd/user"

systemctl --user disable --now trackpad-battery.timer || true
rm -f "$units/trackpad-battery.service" "$units/trackpad-battery.timer" \
      "$HOME/.local/bin/trackpad-battery"
systemctl --user daemon-reload

sudo rm -f /etc/udev/rules.d/70-magic-trackpad-battery.rules
sudo udevadm control --reload
