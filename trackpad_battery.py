#!/usr/bin/env python3
"""Read the Apple Magic Trackpad 2 battery level directly over Bluetooth.

The kernel only polls this trackpad's battery over USB, so over Bluetooth
upower shows a stale value. This asks the device for HID input report 0x90
(flags, percent) through hidraw instead.

Usage: trackpad-battery [--notify] [--threshold N]
"""
import argparse, array, fcntl, glob, os, subprocess, sys

HID_ID = "0005:0000004C:00000265"  # Bluetooth, Apple, Magic Trackpad 2
REPORT_ID = 0x90


def find_hidraw():
    for uevent in glob.glob("/sys/class/hidraw/hidraw*/device/uevent"):
        with open(uevent) as f:
            if f"HID_ID={HID_ID}" in f.read():
                return "/dev/" + uevent.split("/")[4]
    return None


def read_battery(dev):
    # HIDIOCGINPUT(len) = _IOC(_IOC_READ|_IOC_WRITE, 'H', 0x0A, len)
    buf = array.array("B", [REPORT_ID] + [0] * 7)
    req = (3 << 30) | (len(buf) << 16) | (ord("H") << 8) | 0x0A
    fd = os.open(dev, os.O_RDWR)
    try:
        n = fcntl.ioctl(fd, req, buf, True)
    finally:
        os.close(fd)
    if n < 3 or buf[0] != REPORT_ID:
        raise OSError(f"unexpected report: {list(buf[:n])}")
    charging = bool(buf[1] & 0x02)
    return buf[2], charging


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notify", action="store_true",
                    help="send a desktop notification if at or below threshold")
    ap.add_argument("--threshold", type=int, default=50)
    args = ap.parse_args()

    dev = find_hidraw()
    if not dev:
        if not args.notify:
            print("Magic Trackpad not connected over Bluetooth", file=sys.stderr)
        return 0 if args.notify else 1
    try:
        pct, charging = read_battery(dev)
    except OSError as e:
        print(f"{dev}: {e}", file=sys.stderr)
        return 1

    if args.notify:
        if pct <= args.threshold and not charging:
            subprocess.run(["notify-send", "-u", "critical", "-i", "battery-caution",
                            "Magic Trackpad battery low", f"{pct}% remaining"])
    else:
        print(f"{pct}%{' (charging)' if charging else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
