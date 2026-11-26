#!/usr/bin/env python3
"""Read an Apple Magic Trackpad's battery level directly over Bluetooth."""
import argparse
import array
import errno
import fcntl
import glob
import os
import subprocess
import sys

HID_IDS = (  # Bluetooth, Apple vendor ID; keep in sync with 70-magic-trackpad-battery.rules
    "0005:0000004C:00000265",  # Magic Trackpad 2 (Lightning)
    "0005:0000004C:00000324",  # Magic Trackpad (USB-C)
)

# Errors meaning the trackpad disconnected or didn't answer. With --notify these are
# treated like "not connected", so the timer doesn't log a failure.
GONE_ERRNOS = {errno.ENOENT, errno.ENODEV, errno.ENXIO, errno.ETIMEDOUT,
               errno.EHOSTDOWN, errno.ENOTCONN}

REPORT_ID = 0x90
CHARGING_FLAG = 0x02


def parse_report(data):
    """Decode input report 0x90: [report id, flags, percent]."""
    if len(data) < 3 or data[0] != REPORT_ID:
        raise ValueError(f"unexpected report: {list(data)}")
    return data[2], bool(data[1] & CHARGING_FLAG)


def _hidraw_number(uevent):
    """Sort key: N of .../hidrawN/device/uevent, so hidraw10 comes after hidraw2."""
    suffix = uevent.split(os.sep)[-3][len("hidraw"):]
    return int(suffix) if suffix.isdigit() else -1


def find_trackpads(sys_root="/sys"):
    """Return [(/dev/hidrawN, label)] for every Bluetooth Magic Trackpad, in hidraw order.

    The label is the device name plus its Bluetooth address when the kernel reports one.
    """
    found = []
    uevents = glob.glob(os.path.join(sys_root, "class/hidraw/hidraw*/device/uevent"))
    for uevent in sorted(uevents, key=_hidraw_number):
        with open(uevent) as f:
            fields = dict(line.split("=", 1) for line in f.read().splitlines() if "=" in line)
        if fields.get("HID_ID") not in HID_IDS:
            continue
        label = fields.get("HID_NAME") or "Magic Trackpad"
        if fields.get("HID_UNIQ"):
            label += f" ({fields['HID_UNIQ']})"
        found.append(("/dev/" + uevent.split(os.sep)[-3], label))
    return found


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
    """Show a desktop notification. Return False, with a message on stderr, if it fails."""
    try:
        result = run(["notify-send", "-u", "critical", "-i", "battery-caution", title, body])
    except FileNotFoundError:
        print("notify-send not found; install it (libnotify-bin on Debian/Ubuntu, "
              "libnotify on Fedora/Arch)", file=sys.stderr)
        return False
    if result.returncode != 0:
        print(f"notify-send failed with exit status {result.returncode}", file=sys.stderr)
        return False
    return True


def main(argv=None, find=find_trackpads, read=read_report, notify=send_notification):
    parser = argparse.ArgumentParser(description="Print the Magic Trackpad battery level.")
    parser.add_argument("--notify", action="store_true",
                        help="send a desktop notification if at or below the threshold")
    parser.add_argument("--threshold", type=int, default=50,
                        help="notification threshold in percent (default: 50)")
    args = parser.parse_args(argv)

    trackpads = find()
    if not trackpads:
        if args.notify:
            return 0
        print("Magic Trackpad not connected over Bluetooth", file=sys.stderr)
        return 1

    status = 0
    for dev, label in trackpads:
        prefix = f"{label}: " if len(trackpads) > 1 else ""
        try:
            percent, charging = parse_report(read(dev))
        except (OSError, ValueError) as e:
            if args.notify and getattr(e, "errno", None) in GONE_ERRNOS:
                continue
            print(f"{dev}: {e}", file=sys.stderr)
            status = 1
            continue

        if args.notify:
            if percent <= args.threshold and not charging:
                if not notify("Magic Trackpad battery low", f"{prefix}{percent}% remaining"):
                    status = 1
        else:
            print(f"{prefix}{percent}%{' (charging)' if charging else ''}")
    return status

if __name__ == "__main__":
    sys.exit(main())
