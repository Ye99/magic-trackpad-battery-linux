# Magic Trackpad battery on Linux (over Bluetooth)

[![tests](https://github.com/Ye99/magic-trackpad-battery-linux/actions/workflows/tests.yml/badge.svg)](https://github.com/Ye99/magic-trackpad-battery-linux/actions/workflows/tests.yml)

On Linux, the Apple Magic Trackpad 2's battery level is often wrong when the trackpad is connected over Bluetooth. GNOME, `upower` and `/sys/class/power_supply` can show something like **0% or 3%, Discharging**, with a critical-battery warning, while the trackpad is actually full or on a charger. Plug it in over USB and the same system suddenly shows 100%.

This repo has a small script that asks the trackpad for its real battery level over Bluetooth, plus an optional systemd timer that warns you on the desktop when the battery is actually low.

```text
$ trackpad-battery
100%
```

## Why the reading is wrong

- **The trackpad reports its level correctly.** Asked over Bluetooth for HID input report `0x90`, it answers `[0x90, flags, percent]`, for example `[0x90, 0x00, 100]`.
- **Linux doesn't ask for it over Bluetooth.** The `hid_magicmouse` driver only polls the battery on a timer when the trackpad is connected over USB. Over Bluetooth the kernel waits for the trackpad to send a report on its own, which it rarely does, so the value from connection time sticks.
- **"Discharging" means nothing here.** Over Bluetooth the kernel doesn't get a charging flag, so it labels anything below 100% as Discharging.
- The report is an *input* report. A feature-report request (`HIDIOCGFEATURE`) for `0x90` fails with `EIO`, while an input-report request (`HIDIOCGINPUT`) works.
- The trackpad's report descriptor declares the level's range as 0–255 even though it sends 0–100. Anything that relies on the kernel's scaling would show a full battery as about 39%.

There's no module parameter or config setting for this. This project works around it without changing the kernel. It does **not** fix the number in your desktop's battery indicator. For that, trust `trackpad-battery` instead.

## What's included

| File | Purpose |
| --- | --- |
| `trackpad_battery.py` | Finds the trackpad's `hidraw` node and asks it for the battery level. Prints `NN%` or `NN% (charging)`. With `--notify`, shows a desktop notification when the level is at or below `--threshold`. |
| `70-magic-trackpad-battery.rules` | udev rule that lets the logged-in user read the trackpad's `hidraw` node (`TAG+="uaccess"`), so the script doesn't need root. |
| `trackpad-battery.service` | systemd **user** service that runs the script with `--notify --threshold 50`. |
| `trackpad-battery.timer` | Runs the service 2 minutes after login and then every 8 hours. |
| `install.sh` / `uninstall.sh` | Set everything up or remove it. |

## Requirements

- Linux with a systemd user session and udev (tested on Ubuntu with kernel 7.0)
- Python 3 (standard library only)
- `notify-send` (package `libnotify-bin` on Debian/Ubuntu) for `--notify`
- `sudo`, only to install the udev rule
- An Apple Magic Trackpad 2 **paired over Bluetooth**, with HID ID `0005:004C:0265`

Other models, such as the USB-C Magic Trackpad or a Magic Mouse, use a different product ID. They may use the same report and would then need only the ID changed in the script and the udev rule. This is untested; pull requests are welcome.

## Install

```bash
git clone https://github.com/Ye99/magic-trackpad-battery-linux.git
cd magic-trackpad-battery-linux
./install.sh
```

`install.sh`:

1. Symlinks the script to `~/.local/bin/trackpad-battery`.
2. Symlinks the service and timer into `~/.config/systemd/user/` and enables the timer.
3. Installs the udev rule to `/etc/udev/rules.d/` (this step uses `sudo`) and reapplies it to devices already connected.

The files are symlinks, so keep the clone where it is. After a `git pull`, run `systemctl --user daemon-reload` to pick up unit changes, and rerun `./install.sh` if the udev rule changed.

## Usage

```bash
trackpad-battery                              # print the level, e.g. "100%" or "72% (charging)"
trackpad-battery --notify --threshold 20      # notify only if at or below 20% and not charging
systemctl --user list-timers trackpad-battery.timer
journalctl --user -u trackpad-battery.service
```

If the trackpad isn't connected over Bluetooth, the plain command prints an error and exits with status 1. With `--notify` it does nothing and exits 0, so the timer doesn't log failures while the trackpad is away.

### Sleep and battery use

The timer never wakes a sleeping computer, so it won't drain a laptop's battery. It leaves `WakeSystem=` at its default of `no`.

The 8-hour interval (`OnUnitActiveSec=8h`) counts only time the computer is awake, because that clock stops during sleep. So a check runs after about 8 hours of awake time since the last one, plus 2 minutes after each login.

### Change the threshold or schedule

- **Threshold:** edit `--threshold 50` in `trackpad-battery.service`.
- **Schedule:** edit `OnUnitActiveSec=8h` in `trackpad-battery.timer`.

Then apply the change:

```bash
systemctl --user daemon-reload
systemctl --user restart trackpad-battery.timer
```

## Troubleshooting

- **`Permission denied` on `/dev/hidrawN`:** the udev rule isn't applied yet. Rerun `./install.sh`, or turn the trackpad off and on. `getfacl /dev/hidrawN` should list your user.
- **`Magic Trackpad not connected over Bluetooth`:** check `bluetoothctl devices Connected`. Over USB, the kernel already reports the battery correctly, so this script isn't needed.
- **Find the HID ID of a different device:** `grep -H HID_ID /sys/class/hidraw/*/device/uevent`.

## Tests

The tests use only the Python standard library and need no trackpad:

```bash
python3 -m unittest discover -s tests -v
```

- `tests/test_trackpad_battery.py` covers decoding the report, finding the device in a fake `/sys` tree, the exact `HIDIOCGINPUT` ioctl request, the command-line output and exit codes, and the notification rules (threshold, charging, not connected).
- `tests/test_install.py` runs `install.sh` and `uninstall.sh` with a temporary `HOME` and fake `systemctl`, `sudo` and `udevadm`, so it doesn't change your system.

The only part not covered is the real `ioctl` call on real hardware. Running `trackpad-battery` with the trackpad connected checks that.

## Uninstall

```bash
./uninstall.sh
```

## License

[MIT](LICENSE)
