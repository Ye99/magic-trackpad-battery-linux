#!/usr/bin/env bash
# Install the Magic Trackpad Bluetooth battery checker for the current user.
# The script and user units are symlinked from this checkout, so `git pull`
# (plus `systemctl --user daemon-reload` for unit changes) keeps them current.
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
bin="$HOME/.local/bin"
units="$HOME/.config/systemd/user"

# The udev rule comes first: the timer's first run needs it, and if sudo is
# declined, nothing else has been set up yet.
sudo install -m 0644 "$dir/70-magic-trackpad-battery.rules" /etc/udev/rules.d/
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=hidraw

mkdir -p "$bin"
ln -sfn "$dir/trackpad_battery.py" "$bin/trackpad-battery"

if ! systemctl --user show-environment >/dev/null 2>&1; then
    echo "No systemd user session found, so the timer was not installed." >&2
    echo "For low-battery warnings, run 'trackpad-battery --notify' every few hours" >&2
    echo "from something that runs inside your desktop session, such as its autostart." >&2
    exit 0
fi

mkdir -p "$units"
ln -sfn "$dir/trackpad-battery.service" "$units/trackpad-battery.service"
ln -sfn "$dir/trackpad-battery.timer" "$units/trackpad-battery.timer"
systemctl --user daemon-reload
systemctl --user enable --now trackpad-battery.timer
