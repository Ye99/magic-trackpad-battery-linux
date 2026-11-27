import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UNITS = ("trackpad-battery.service", "trackpad-battery.timer")
SYSTEMD_ANALYZE = shutil.which("systemd-analyze")
# CI sets this so a runner without systemd fails instead of quietly skipping.
REQUIRED = os.environ.get("REQUIRE_SYSTEMD_ANALYZE") == "1"


@unittest.skipUnless(SYSTEMD_ANALYZE or REQUIRED, "systemd-analyze not installed")
class SystemdUnitsTest(unittest.TestCase):
    """Checks the user service and timer with `systemd-analyze --user verify`."""

    def setUp(self):
        self.assertIsNotNone(SYSTEMD_ANALYZE, "systemd-analyze not installed")
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.runtime = os.path.join(self.tmp.name, "run")
        os.makedirs(os.path.join(self.home, ".local", "bin"))
        os.makedirs(self.runtime, mode=0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def install_script(self):
        # Where install.sh puts it, and where the service's ExecStart (%h/.local/bin) looks.
        os.symlink(os.path.join(REPO, "trackpad_battery.py"),
                   os.path.join(self.home, ".local", "bin", "trackpad-battery"))

    def verify(self):
        result = subprocess.run(
            [SYSTEMD_ANALYZE, "--user", "verify", *(os.path.join(REPO, u) for u in UNITS)],
            capture_output=True, text=True, check=False,
            env={**os.environ, "HOME": self.home, "XDG_RUNTIME_DIR": self.runtime})
        # The runner has no system bus; systemd-analyze says so but still verifies the units.
        problems = [line for line in (result.stdout + result.stderr).splitlines()
                    if line and "system bus" not in line]
        return result.returncode, problems

    def test_units_verify_cleanly(self):
        self.install_script()
        code, problems = self.verify()
        self.assertEqual((code, problems), (0, []))

    def test_verify_catches_a_missing_executable(self):
        # Guards the check itself: it must fail when the service's command is absent.
        code, problems = self.verify()
        self.assertNotEqual(code, 0)
        self.assertTrue(any("trackpad-battery" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
