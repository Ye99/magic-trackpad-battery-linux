# Magic Trackpad battery on Linux (over Bluetooth)

[![tests](https://github.com/Ye99/magic-trackpad-battery-linux/actions/workflows/tests.yml/badge.svg)](https://github.com/Ye99/magic-trackpad-battery-linux/actions/workflows/tests.yml)

Read the real battery level of an Apple Magic Trackpad connected over Bluetooth, and get a desktop warning when it's actually low.

```text
$ trackpad-battery
100%
```

Over Bluetooth, GNOME, `upower` and `/sys/class/power_supply` often show the trackpad at something like **0% or 3%, Discharging**, even when it's full or charging. This tool asks the trackpad directly, so you get the right number. It doesn't change the kernel or fix your desktop's battery indicator.

## Requirements

- Linux 5.11 or newer, with udev (tested on Ubuntu, kernel 7.0)
- Python 3, standard library only
- An Apple Magic Trackpad **paired over Bluetooth**: the Magic Trackpad 2 (HID ID `0005:004C:0265`) or the USB-C Magic Trackpad (`0005:004C:0324`)
- A systemd user session for the low-battery timer (optional)
- `notify-send` for warnings (`libnotify-bin` on Debian/Ubuntu, `libnotify` on Fedora and Arch)
- `sudo`, only to install the udev rule

Other devices, such as a Magic Mouse, are untested. If one sends the same report, adding its ID to `HID_IDS` in `trackpad_battery.py` and to the udev rule may be enough. Pull requests are welcome.

## Install

```bash
git clone https://github.com/Ye99/magic-trackpad-battery-linux.git
cd magic-trackpad-battery-linux
./install.sh
```

`install.sh` does three things:

1. Copies the udev rule to `/etc/udev/rules.d/` with `sudo` and applies it to devices already connected, so you can read the trackpad without root.
2. Links the script to `~/.local/bin/trackpad-battery`.
3. Links the systemd user service and timer into `~/.config/systemd/user/` and enables the timer.

Without a systemd user session, it skips step 3 and says so. For warnings there, run `trackpad-battery --notify` every few hours from something inside your desktop session, such as its autostart.

Everything except the udev rule is a symlink into the clone, so keep the clone where it is. If `trackpad-battery` isn't found, add `~/.local/bin` to your `PATH` (the timer doesn't need it).

To update, run `git pull`, then `systemctl --user daemon-reload`. Rerun `./install.sh` if the udev rule changed.

## Usage

```bash
trackpad-battery
```

It prints the level, with `(charging)` when the trackpad is on a charger:

```text
72% (charging)
```

With more than one trackpad connected, each line starts with the trackpad's name and Bluetooth address:

```text
Magic Trackpad (aa:bb:cc:dd:ee:ff): 85%
```

If no trackpad is connected over Bluetooth, it prints `Magic Trackpad not connected over Bluetooth` and exits with status 1. If any trackpad can't be read, it prints the error and exits with status 1.

### Low-battery warnings

```bash
trackpad-battery --notify --threshold 20
```

With `--notify`, nothing is printed. It shows a critical desktop notification only when the level is at or below `--threshold` (default 50) and the trackpad isn't charging. If the trackpad isn't connected, disconnects or doesn't answer, it exits 0 quietly, so the timer doesn't log failures while it's away. Other read errors, or a notification that fails, exit with status 1.

The installed timer runs this check with `--threshold 50` two minutes after you log in, then every 8 hours of awake time. It never wakes a sleeping computer, and the 8-hour clock pauses during sleep.

```bash
systemctl --user list-timers trackpad-battery.timer   # next run
journalctl --user -u trackpad-battery.service          # past runs and errors
```

To change the threshold, edit `--threshold 50` in `trackpad-battery.service`. To change the interval, edit `OnUnitActiveSec=8h` in `trackpad-battery.timer`. Then reload:

```bash
systemctl --user daemon-reload
systemctl --user restart trackpad-battery.timer
```

## How it works

The trackpad answers a request for HID input report `0x90` with `[0x90, flags, percent]`, where flag `0x02` means charging. The script finds each trackpad's `/dev/hidrawN` node by matching its HID ID under `/sys/class/hidraw/`, then reads that report with the `HIDIOCGINPUT` ioctl, which needs Linux 5.11 or newer.

Linux gets this wrong for a few reasons:

- The `hid_magicmouse` driver polls the battery only over USB. Over Bluetooth it waits for the trackpad to send a report on its own, which it rarely does, so the value from connection time sticks.
- Over Bluetooth the kernel gets no charging flag, so anything below 100% shows as Discharging.
- The report descriptor declares the range as 0 to 255, though the trackpad sends 0 to 100, so kernel scaling would show a full battery as about 39%.
- Asking for `0x90` as a feature report (`HIDIOCGFEATURE`) fails with `EIO`. It must be requested as an input report.

There's no module parameter or config setting that fixes this, which is why this tool reads the report itself.

## Troubleshooting

- **`Magic Trackpad not connected over Bluetooth`:** the trackpad is off, asleep or connected over USB. Click or touch it to wake it, then check `bluetoothctl devices Connected`. Over USB the kernel already reports the battery correctly, so you don't need this tool.
- **`/dev/hidrawN: ... Permission denied`:** the udev rule isn't applied. Rerun `./install.sh`, or turn the trackpad off and on. `getfacl /dev/hidrawN` should list your user.
- **`the kernel rejected HIDIOCGINPUT ... needs Linux 5.11 or newer`:** your kernel is too old. Upgrade it.
- **Another error from `/dev/hidrawN`:** the trackpad may have gone to sleep or dropped the connection during the read. Wake it and try again. With `--notify`, these errors are ignored.
- **No warning when the battery is low:** look at `journalctl --user -u trackpad-battery.service`. `notify-send not found` means you need to install it. To test a notification, run `trackpad-battery --notify --threshold 100` while the trackpad isn't charging.
- **Finding a different device's HID ID:** `grep -H HID_ID /sys/class/hidraw/*/device/uevent`.

## Tests

The tests use only the standard library and need no trackpad:

```bash
python3 -m unittest discover -s tests -v
```

They cover report decoding, finding trackpads in a fake `/sys` tree, the ioctl request, output and exit codes, the notification rules, and `install.sh` / `uninstall.sh` run against a temporary `HOME` with fake `systemctl`, `sudo` and `udevadm`. The real ioctl on real hardware isn't covered. Running `trackpad-battery` with the trackpad connected checks that.

## Uninstall

```bash
./uninstall.sh
```

This disables the timer, removes the links from `~/.local/bin` and `~/.config/systemd/user/`, and removes the udev rule with `sudo` and reapplies the rules to connected devices. You can then delete the clone.

## License

[MIT](LICENSE)
