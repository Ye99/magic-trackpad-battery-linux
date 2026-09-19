import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import trackpad_battery as tb  # noqa: E402


class ParseReportTest(unittest.TestCase):
    def test_returns_percent_and_not_charging(self):
        self.assertEqual(tb.parse_report(bytes([0x90, 0x00, 100])), (100, False))

    def test_charging_flag_is_bit_1(self):
        self.assertEqual(tb.parse_report(bytes([0x90, 0x02, 72])), (72, True))

    def test_other_flag_bits_do_not_mean_charging(self):
        self.assertEqual(tb.parse_report(bytes([0x90, 0x05, 40])), (40, False))

    def test_rejects_wrong_report_id(self):
        with self.assertRaises(ValueError):
            tb.parse_report(bytes([0x91, 0x00, 100]))

    def test_rejects_short_report(self):
        with self.assertRaises(ValueError):
            tb.parse_report(bytes([0x90, 0x00]))


def make_hidraw(sys_root, name, hid_id):
    device = os.path.join(sys_root, "class", "hidraw", name, "device")
    os.makedirs(device)
    with open(os.path.join(device, "uevent"), "w") as f:
        f.write(f"DRIVER=magicmouse\nHID_ID={hid_id}\nHID_NAME=Magic Trackpad\n")


class FindHidrawTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sys_root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_bluetooth_trackpad_among_other_devices(self):
        make_hidraw(self.sys_root, "hidraw2", "0003:0000046D:0000C52B")
        make_hidraw(self.sys_root, "hidraw8", "0005:0000004C:00000265")
        self.assertEqual(tb.find_hidraw(self.sys_root), "/dev/hidraw8")

    def test_ignores_trackpad_connected_over_usb(self):
        make_hidraw(self.sys_root, "hidraw3", "0003:000005AC:00000265")
        self.assertIsNone(tb.find_hidraw(self.sys_root))

    def test_returns_none_when_no_hidraw_devices(self):
        self.assertIsNone(tb.find_hidraw(self.sys_root))


class CliTestCase(unittest.TestCase):
    def run_main(self, argv, report=None, device="/dev/hidraw8", read_error=None):
        self.notifications = []
        self.read_from = []

        def read(dev):
            self.read_from.append(dev)
            if read_error:
                raise read_error
            return report

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = tb.main(argv, find=lambda: device, read=read,
                           notify=lambda *msg: self.notifications.append(msg))
        return code, out.getvalue(), err.getvalue()


class MainTest(CliTestCase):
    def test_prints_level(self):
        code, out, _ = self.run_main([], report=bytes([0x90, 0, 100]))
        self.assertEqual((code, out), (0, "100%\n"))

    def test_reads_from_the_found_device(self):
        self.run_main([], report=bytes([0x90, 0, 100]), device="/dev/hidraw5")
        self.assertEqual(self.read_from, ["/dev/hidraw5"])

    def test_prints_charging(self):
        code, out, _ = self.run_main([], report=bytes([0x90, 0x02, 72]))
        self.assertEqual((code, out), (0, "72% (charging)\n"))

    def test_not_connected_is_an_error(self):
        code, out, err = self.run_main([], device=None)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("not connected", err)

    def test_read_failure_is_an_error(self):
        code, _, err = self.run_main([], read_error=OSError(5, "Input/output error"))
        self.assertEqual(code, 1)
        self.assertIn("/dev/hidraw8", err)
        self.assertIn("Input/output error", err)

    def test_malformed_report_is_an_error(self):
        code, _, err = self.run_main([], report=bytes([0x91, 0, 100]))
        self.assertEqual(code, 1)
        self.assertIn("unexpected report", err)


class NotifyTest(CliTestCase):
    def test_notifies_at_threshold(self):
        code, out, _ = self.run_main(["--notify", "--threshold", "20"],
                                     report=bytes([0x90, 0, 20]))
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("20%", " ".join(self.notifications[0]))

    def test_silent_above_threshold(self):
        code, out, _ = self.run_main(["--notify", "--threshold", "20"],
                                     report=bytes([0x90, 0, 21]))
        self.assertEqual((code, out, self.notifications), (0, "", []))

    def test_silent_when_low_but_charging(self):
        self.run_main(["--notify", "--threshold", "20"], report=bytes([0x90, 0x02, 5]))
        self.assertEqual(self.notifications, [])

    def test_default_threshold_is_50(self):
        self.run_main(["--notify"], report=bytes([0x90, 0, 50]))
        self.assertEqual(len(self.notifications), 1)
        self.run_main(["--notify"], report=bytes([0x90, 0, 51]))
        self.assertEqual(self.notifications, [])

    def test_not_connected_is_silent_success(self):
        code, out, err = self.run_main(["--notify"], device=None)
        self.assertEqual((code, out, err, self.notifications), (0, "", "", []))

    def test_read_failure_is_still_an_error(self):
        code, _, err = self.run_main(["--notify"], read_error=OSError(5, "Input/output error"))
        self.assertEqual((code, self.notifications), (1, []))
        self.assertIn("Input/output error", err)


class ReadReportTest(unittest.TestCase):
    def test_requests_input_report_0x90_with_hidiocginput(self):
        calls = []

        def fake_ioctl(fd, request, buf, mutate):
            calls.append((request, bytes(buf), mutate))
            buf[1], buf[2] = 0x02, 64
            return 3

        with tempfile.NamedTemporaryFile() as dev:
            data = tb.read_report(dev.name, ioctl=fake_ioctl)

        # HIDIOCGINPUT(8) = _IOC(_IOC_READ|_IOC_WRITE, 'H', 0x0A, 8)
        self.assertEqual(calls, [(0xC008480A, bytes([0x90, 0, 0, 0, 0, 0, 0, 0]), True)])
        self.assertEqual(data, bytes([0x90, 0x02, 64]))

    def test_missing_device_raises_oserror(self):
        with self.assertRaises(OSError):
            tb.read_report("/nonexistent/hidraw99")


class SendNotificationTest(unittest.TestCase):
    def test_runs_notify_send_as_critical(self):
        commands = []
        tb.send_notification("Title", "Body", run=lambda cmd: commands.append(cmd))
        self.assertEqual(commands, [["notify-send", "-u", "critical", "-i", "battery-caution",
                                     "Title", "Body"]])


if __name__ == "__main__":
    unittest.main()
