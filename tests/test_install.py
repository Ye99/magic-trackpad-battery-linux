import os
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UNITS = (".config", "systemd", "user")
FAKE_COMMANDS = ("systemctl", "sudo", "udevadm")


class ScriptTestCase(unittest.TestCase):
    """Runs install.sh / uninstall.sh with a temporary HOME and fake system commands."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.bin = os.path.join(self.tmp.name, "bin")
        self.log = os.path.join(self.tmp.name, "commands.log")
        os.makedirs(self.home)
        os.makedirs(self.bin)
        for name in FAKE_COMMANDS:
            path = os.path.join(self.bin, name)
            with open(path, "w") as f:
                f.write(f'#!/bin/sh\necho "{name} $*" >> "$COMMAND_LOG"\n'
                        f'[ "{name} $1 $2" = "systemctl --user disable" ] && [ -n "$FAIL_DISABLE" ] && exit 1\n'
                        f'exit 0\n')
            os.chmod(path, 0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name, **env):
        result = subprocess.run(
            [os.path.join(REPO, name)], cwd=self.tmp.name, capture_output=True, text=True,
            env={**os.environ, "HOME": self.home, "COMMAND_LOG": self.log,
                 "PATH": self.bin + os.pathsep + os.environ["PATH"], **env})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def commands(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as f:
            return f.read().splitlines()

    def home_path(self, *parts):
        return os.path.join(self.home, *parts)

    def assert_links_to(self, link, target):
        self.assertTrue(os.path.islink(link), f"{link} is not a symlink")
        self.assertEqual(os.readlink(link), os.path.join(REPO, target))


class InstallTest(ScriptTestCase):
    def test_links_script_onto_path(self):
        self.run_script("install.sh")
        self.assert_links_to(self.home_path(".local", "bin", "trackpad-battery"),
                             "trackpad_battery.py")

    def test_links_user_units(self):
        self.run_script("install.sh")
        for unit in ("trackpad-battery.service", "trackpad-battery.timer"):
            self.assert_links_to(self.home_path(*UNITS, unit), unit)

    def test_enables_timer_after_reload(self):
        self.run_script("install.sh")
        commands = self.commands()
        self.assertIn("systemctl --user enable --now trackpad-battery.timer", commands)
        self.assertLess(commands.index("systemctl --user daemon-reload"),
                        commands.index("systemctl --user enable --now trackpad-battery.timer"))

    def test_installs_and_applies_udev_rule(self):
        self.run_script("install.sh")
        rule = os.path.join(REPO, "70-magic-trackpad-battery.rules")
        self.assertEqual(
            [c for c in self.commands() if c.startswith("sudo")],
            [f"sudo install -m 0644 {rule} /etc/udev/rules.d/",
             "sudo udevadm control --reload",
             "sudo udevadm trigger --subsystem-match=hidraw"])

    def test_running_twice_succeeds(self):
        self.run_script("install.sh")
        self.run_script("install.sh")
        self.assert_links_to(self.home_path(".local", "bin", "trackpad-battery"),
                             "trackpad_battery.py")


class UninstallTest(ScriptTestCase):
    def test_removes_links(self):
        self.run_script("install.sh")
        self.run_script("uninstall.sh")
        for path in (self.home_path(".local", "bin", "trackpad-battery"),
                     self.home_path(*UNITS, "trackpad-battery.service"),
                     self.home_path(*UNITS, "trackpad-battery.timer")):
            self.assertFalse(os.path.lexists(path), path)

    def test_disables_timer_and_removes_udev_rule(self):
        self.run_script("uninstall.sh")
        commands = self.commands()
        self.assertIn("systemctl --user disable --now trackpad-battery.timer", commands)
        self.assertIn("sudo rm -f /etc/udev/rules.d/70-magic-trackpad-battery.rules", commands)
        self.assertIn("sudo udevadm control --reload", commands)

    def test_succeeds_when_nothing_is_installed(self):
        self.run_script("uninstall.sh", FAIL_DISABLE="1")
        self.assertIn("systemctl --user daemon-reload", self.commands())


if __name__ == "__main__":
    unittest.main()
