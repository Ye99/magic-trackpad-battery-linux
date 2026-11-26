#!/usr/bin/env python3
"""Read the Apple Magic Trackpad 2 battery level directly over Bluetooth."""
import argparse
import array
import errno
import fcntl
import glob
import os
import subprocess
import sys

HID_ID = "0005:0000004C:00000265"  # Bluetooth, Apple, Magic Trackpad 2

REPORT_ID = 0x90
CHARGING_FLAG = 0x02


def parse_report(data):
    """Decode input report 0x90: [report id, flags, percent]."""
    if len(data) < 3 or data[0] != REPORT_ID:
        raise ValueError(f"unexpected report: {list(data)}")
    return data[2], bool(data[1] & CHARGING_FLAG)


def find_hidraw(sys_root="/sys"):
    """Return the /dev/hidrawN path of the Bluetooth trackpad, or None."""
    for uevent in sorted(glob.glob(os.path.join(sys_root, "class/hidraw/hidraw*/device/uevent"))):
        with open(uevent) as f:
            if f"HID_ID={HID_ID}" in f.read().splitlines():
                return "/dev/" + uevent.split(os.sep)[-3]
    return None


def read_report(dev, ioctl=fcntl.ioctl):
    """Ask the device for input report 0x90 via HIDIOCGINPUT.

    The report is an input report; requesting it as a feature report fails with EIO.
    """
    buf = array.array("B", [REPORT_ID] + [0] * 7)
    request = (3 << 30) | (len(buf) << 16) | (ord("H") << 8) | 0x0A  # HIDIOCGINPUT(len)
    fd = os.open(dev, os.O_RDWR)
    try:
        n = ioctl(fd, request, buf, True)
    except OSError as e:
        if e.errno in (errno.EINVAL, errno.ENOTTY):
            raise OSError(e.errno, f"the kernel rejected HIDIOCGINPUT ({e.strerror}); "
                          f"this tool needs Linux 5.11 or newer, running {os.uname().release}") from e
        raise
    finally:
        os.close(fd)
    return bytes(buf[:n])


def send_notification(title, body, run=subprocess.run):
    run(["notify-send", "-u", "critical", "-i", "battery-caution", title, body])


def main(argv=None, find=find_hidraw, read=read_report, notify=send_notification):
    parser = argparse.ArgumentParser(description="Print the Magic Trackpad battery level.")
    parser.add_argument("--notify", action="store_true",
                        help="send a desktop notification if at or below the threshold")
    parser.add_argument("--threshold", type=int, default=50,
                        help="notification threshold in percent (default: 50)")
    args = parser.parse_args(argv)

    dev = find()
    if not dev:
        if args.notify:
            return 0
        print("Magic Trackpad not connected over Bluetooth", file=sys.stderr)
        return 1
    try:
        percent, charging = parse_report(read(dev))
    except (OSError, ValueError) as e:
        print(f"{dev}: {e}", file=sys.stderr)
        return 1

    if args.notify:
        if percent <= args.threshold and not charging:
            notify("Magic Trackpad battery low", f"{percent}% remaining")
    else:
        print(f"{percent}%{' (charging)' if charging else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
