#!/usr/bin/env bash
# Install the Magic Trackpad Bluetooth battery checker for the current user.
# The script and user units are symlinked from this checkout, so `git pull`
# (plus `systemctl --user daemon-reload` for unit changes) keeps them current.
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
bin="$HOME/.local/bin"
units="$HOME/.config/systemd/user"

mkdir -p "$bin" "$units"
ln -sfn "$dir/trackpad_battery.py" "$bin/trackpad-battery"
ln -sfn "$dir/trackpad-battery.service" "$units/trackpad-battery.service"
ln -sfn "$dir/trackpad-battery.timer" "$units/trackpad-battery.timer"
systemctl --user daemon-reload
systemctl --user enable --now trackpad-battery.timer

sudo install -m 0644 "$dir/70-magic-trackpad-battery.rules" /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw
