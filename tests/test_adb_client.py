"""Unit tests for RealAdbClient and MockAdbClient."""

import os
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from android_gemini_agent.adb.client import RealAdbClient
from android_gemini_agent.adb.mock_client import MockAdbClient
from android_gemini_agent.adb.models import DeviceInfo, DeviceState, ConnectionResult, PairingResult, ShellResult
from android_gemini_agent.adb.protocol import AdbClientProtocol


class TestRealAdbClientPathDiscovery(unittest.TestCase):
    """Test suite for ADB binary path discovery."""

    @patch("os.path.isfile")
    def test_explicit_path_discovery(self, mock_isfile):
        mock_isfile.side_effect = lambda p: p == "/custom/path/adb"
        path = RealAdbClient.discover_adb_path("/custom/path/adb")
        self.assertEqual(path, "/custom/path/adb")

    @patch.dict(os.environ, {"ADB_PATH": "/env/path/to/adb"})
    @patch("os.path.isfile")
    def test_env_var_path_discovery(self, mock_isfile):
        mock_isfile.side_effect = lambda p: p == "/env/path/to/adb"
        path = RealAdbClient.discover_adb_path()
        self.assertEqual(path, "/env/path/to/adb")

    @patch("platform.system", return_value="Windows")
    @patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Users\\Test\\AppData\\Local"})
    @patch("os.path.isfile")
    @patch("os.access", return_value=True)
    def test_windows_standard_sdk_path(self, mock_access, mock_isfile, mock_system):
        expected = os.path.join("C:\\Users\\Test\\AppData\\Local", "Android", "Sdk", "platform-tools", "adb.exe")
        mock_isfile.side_effect = lambda p: p == expected
        path = RealAdbClient.discover_adb_path()
        self.assertEqual(path, expected)

    @patch("platform.system", return_value="Darwin")
    @patch("os.path.isfile")
    @patch("os.access", return_value=True)
    def test_darwin_standard_sdk_path(self, mock_access, mock_isfile, mock_system):
        home = os.path.expanduser("~")
        expected = os.path.join(home, "Library", "Android", "sdk", "platform-tools", "adb")
        mock_isfile.side_effect = lambda p: p == expected
        path = RealAdbClient.discover_adb_path()
        self.assertEqual(path, expected)

    @patch("platform.system", return_value="Linux")
    @patch("os.path.isfile")
    @patch("os.access", return_value=True)
    def test_linux_standard_sdk_path(self, mock_access, mock_isfile, mock_system):
        expected = "/usr/bin/adb"
        mock_isfile.side_effect = lambda p: p == expected
        path = RealAdbClient.discover_adb_path()
        self.assertEqual(path, expected)

    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value="/usr/local/bin/adb")
    def test_shutil_which_fallback(self, mock_which, mock_isfile):
        path = RealAdbClient.discover_adb_path()
        self.assertEqual(path, "/usr/local/bin/adb")

    @patch("os.path.isfile", return_value=False)
    @patch("shutil.which", return_value=None)
    def test_default_fallback(self, mock_which, mock_isfile):
        path = RealAdbClient.discover_adb_path()
        self.assertEqual(path, "adb")


class TestRealAdbClientOperations(unittest.TestCase):
    """Test suite for RealAdbClient commands and output parsing."""

    def setUp(self):
        self.client = RealAdbClient(adb_path="mock_adb")

    @patch.object(RealAdbClient, "_run_adb")
    def test_connect_success(self, mock_run):
        mock_run.return_value = (0, "connected to 192.168.1.100:5555\n", "")
        res = self.client.connect("192.168.1.100", 5555)
        self.assertTrue(res.success)
        self.assertEqual(res.host, "192.168.1.100")
        self.assertEqual(res.port, 5555)
        self.assertIn("connected to 192.168.1.100:5555", res.message)

    @patch.object(RealAdbClient, "_run_adb")
    def test_connect_already_connected(self, mock_run):
        mock_run.return_value = (0, "already connected to 192.168.1.100:5555\n", "")
        res = self.client.connect("192.168.1.100", 5555)
        self.assertTrue(res.success)

    @patch.object(RealAdbClient, "_run_adb")
    def test_connect_exit_code_zero_anomaly_refused(self, mock_run):
        mock_run.return_value = (0, "cannot connect to 192.168.1.100:5555: No connection could be made because the target machine actively refused it. (10061)", "")
        res = self.client.connect("192.168.1.100", 5555)
        self.assertFalse(res.success)
        self.assertIn("Connection refused", res.error)

    @patch.object(RealAdbClient, "_run_adb")
    def test_connect_timeout(self, mock_run):
        mock_run.return_value = (1, "", "failed to connect to 192.168.1.100:5555: Connection timed out")
        res = self.client.connect("192.168.1.100", 5555)
        self.assertFalse(res.success)
        self.assertIn("timed out", res.error)

    @patch.object(RealAdbClient, "_run_adb")
    def test_connect_unauthorized(self, mock_run):
        mock_run.return_value = (0, "error: device unauthorized.", "")
        res = self.client.connect("192.168.1.100", 5555)
        self.assertFalse(res.success)
        self.assertIn("unauthorized", res.error)

    @patch.object(RealAdbClient, "_run_adb")
    def test_disconnect(self, mock_run):
        mock_run.return_value = (0, "disconnected 192.168.1.100:5555", "")
        self.assertTrue(self.client.disconnect("192.168.1.100:5555"))
        mock_run.assert_called_with(["disconnect", "192.168.1.100:5555"], timeout=5.0)

        mock_run.return_value = (0, "disconnected everything", "")
        self.assertTrue(self.client.disconnect())
        mock_run.assert_called_with(["disconnect"], timeout=5.0)

    @patch.object(RealAdbClient, "_run_adb")
    def test_pair_success(self, mock_run):
        mock_run.return_value = (0, "Successfully paired to 192.168.1.100:43215 [guid=adb-12345]", "")
        res = self.client.pair("192.168.1.100", 43215, "123456")
        self.assertTrue(res.success)
        self.assertEqual(res.host, "192.168.1.100")
        self.assertEqual(res.port, 43215)
        self.assertIn("Successfully paired", res.message)

    def test_pair_invalid_code(self):
        res1 = self.client.pair("192.168.1.100", 43215, "123")
        self.assertFalse(res1.success)
        self.assertIn("must be exactly 6 digits", res1.error)

        res2 = self.client.pair("192.168.1.100", 43215, "abcdef")
        self.assertFalse(res2.success)

        res3 = self.client.pair("192.168.1.100", 43215, "1234567")
        self.assertFalse(res3.success)

    @patch.object(RealAdbClient, "_run_adb")
    def test_pair_auth_failed(self, mock_run):
        mock_run.return_value = (1, "Failed: Authentication failed", "")
        res = self.client.pair("192.168.1.100", 43215, "123456")
        self.assertFalse(res.success)
        self.assertIn("authentication failed", res.error.lower())

    @patch.object(RealAdbClient, "_run_adb")
    def test_pair_protocol_fault(self, mock_run):
        mock_run.return_value = (1, "error: protocol fault (couldn't read status message)", "")
        res = self.client.pair("192.168.1.100", 43215, "123456")
        self.assertFalse(res.success)
        self.assertIn("protocol error", res.error.lower())

    @patch.object(RealAdbClient, "_run_adb")
    def test_list_devices(self, mock_run):
        raw_output = (
            "* daemon not running; starting now at tcp:5037\n"
            "* daemon started successfully\n"
            "List of devices attached\n"
            "192.168.1.100:5555     device product:panther model:Pixel_7 transport_id:1\n"
            "emulator-5554          offline product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 transport_id:2\n"
            "192.168.1.101:37849    unauthorized transport_id:3\n"
        )
        mock_run.return_value = (0, raw_output, "")
        devices = self.client.list_devices()
        self.assertEqual(len(devices), 3)

        self.assertEqual(devices[0].serial, "192.168.1.100:5555")
        self.assertEqual(devices[0].state, DeviceState.CONNECTED)
        self.assertEqual(devices[0].model, "Pixel_7")
        self.assertEqual(devices[0].product, "panther")
        self.assertEqual(devices[0].transport_id, "1")

        self.assertEqual(devices[1].serial, "emulator-5554")
        self.assertEqual(devices[1].state, DeviceState.OFFLINE)

        self.assertEqual(devices[2].serial, "192.168.1.101:37849")
        self.assertEqual(devices[2].state, DeviceState.UNAUTHORIZED)

    @patch.object(RealAdbClient, "_run_adb")
    def test_get_state(self, mock_run):
        mock_run.return_value = (0, "device\n", "")
        self.assertEqual(self.client.get_state("192.168.1.100:5555"), DeviceState.CONNECTED)

        mock_run.return_value = (0, "offline\n", "")
        self.assertEqual(self.client.get_state("192.168.1.100:5555"), DeviceState.OFFLINE)

        mock_run.return_value = (0, "unauthorized\n", "")
        self.assertEqual(self.client.get_state("192.168.1.100:5555"), DeviceState.UNAUTHORIZED)

        mock_run.return_value = (1, "", "error: device '192.168.1.100:5555' not found")
        self.assertEqual(self.client.get_state("192.168.1.100:5555"), DeviceState.DISCONNECTED)

    @patch.object(RealAdbClient, "_run_adb")
    def test_execute_shell(self, mock_run):
        mock_run.return_value = (0, "test stdout", "")
        res = self.client.execute_shell("192.168.1.100:5555", "echo test", timeout=5.0)
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.stdout, "test stdout")
        self.assertEqual(res.output, "test stdout")
        mock_run.assert_called_with(["-s", "192.168.1.100:5555", "shell", "echo test"], timeout=5.0)

    @patch("subprocess.run")
    def test_run_adb_timeout_expired(self, mock_sub):
        mock_sub.side_effect = subprocess.TimeoutExpired(cmd=["adb", "shell"], timeout=5.0)
        code, stdout, stderr = self.client._run_adb(["shell", "sleep 10"], timeout=5.0)
        self.assertEqual(code, 124)
        self.assertIn("timed out", stderr)

    @patch("subprocess.run")
    def test_run_adb_file_not_found(self, mock_sub):
        mock_sub.side_effect = FileNotFoundError()
        code, stdout, stderr = self.client._run_adb(["devices"])
        self.assertEqual(code, 127)
        self.assertIn("not found", stderr)

    @patch.object(RealAdbClient, "execute_shell")
    def test_dump_ui_hierarchy_primary_and_fallback(self, mock_shell):
        mock_shell.return_value = ShellResult(
            exit_code=0,
            stdout="UI hierchary dumped to: /data/local/tmp/window_dump.xml\n<hierarchy rotation=\"0\"><node text=\"Settings\"/></hierarchy>",
            stderr="",
        )
        xml = self.client.dump_ui_hierarchy("192.168.1.100:5555")
        self.assertEqual(xml, '<hierarchy rotation="0"><node text="Settings"/></hierarchy>')

        # Fallback test
        mock_shell.side_effect = [
            ShellResult(exit_code=1, stdout="", stderr="error: dump failed"),
            ShellResult(exit_code=0, stdout="<hierarchy><node text=\"Fallback\"/></hierarchy>", stderr=""),
        ]
        xml_fb = self.client.dump_ui_hierarchy("192.168.1.100:5555")
        self.assertEqual(xml_fb, '<hierarchy><node text="Fallback"/></hierarchy>')

    @patch.object(RealAdbClient, "execute_shell")
    def test_get_screen_size_physical_and_override(self, mock_shell):
        mock_shell.return_value = ShellResult(exit_code=0, stdout="Physical size: 1080x2400\n", stderr="")
        w, h = self.client.get_screen_size("192.168.1.100:5555")
        self.assertEqual((w, h), (1080, 2400))

        mock_shell.return_value = ShellResult(exit_code=0, stdout="Physical size: 1080x2400\nOverride size: 720x1600\n", stderr="")
        w, h = self.client.get_screen_size("192.168.1.100:5555")
        self.assertEqual((w, h), (720, 1600))

        # Fallback when output unparseable
        mock_shell.return_value = ShellResult(exit_code=1, stdout="Error", stderr="unknown")
        w_fb, h_fb = self.client.get_screen_size("192.168.1.100:5555")
        self.assertEqual((w_fb, h_fb), (1080, 2400))


class TestMockAdbClient(unittest.TestCase):
    """Test suite for MockAdbClient simulator."""

    def setUp(self):
        self.mock_adb = MockAdbClient()

    def test_protocol_conformance(self):
        self.assertIsInstance(self.mock_adb, AdbClientProtocol)

    def test_mock_connect_and_disconnect(self):
        res = self.mock_adb.connect("192.168.1.100", 5555)
        self.assertTrue(res.success)
        self.assertEqual(self.mock_adb.get_state("192.168.1.100:5555"), DeviceState.CONNECTED)

        devices = self.mock_adb.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].serial, "192.168.1.100:5555")

        self.mock_adb.disconnect("192.168.1.100:5555")
        self.assertEqual(self.mock_adb.get_state("192.168.1.100:5555"), DeviceState.DISCONNECTED)
        self.assertEqual(len(self.mock_adb.list_devices()), 0)

    def test_mock_pairing_workflow(self):
        res_fail = self.mock_adb.pair("192.168.1.100", 43215, "123")
        self.assertFalse(res_fail.success)

        res_ok = self.mock_adb.pair("192.168.1.100", 43215, "829471")
        self.assertTrue(res_ok.success)
        self.assertIn("Successfully paired", res_ok.message)

    def test_mock_execute_shell_and_history(self):
        self.mock_adb.connect("192.168.1.100", 5555)
        res_tap = self.mock_adb.execute_shell("192.168.1.100:5555", "input tap 100 200")
        self.assertEqual(res_tap.exit_code, 0)

        res_monkey = self.mock_adb.execute_shell("192.168.1.100:5555", "monkey -p com.android.settings -c android.intent.category.LAUNCHER 1")
        self.assertIn("Events injected: 1", res_monkey.stdout)

        history = self.mock_adb.history
        self.assertEqual(len(history), 3)  # connect, tap, monkey

    def test_mock_xml_fixtures(self):
        self.mock_adb.connect("192.168.1.100", 5555)
        default_xml = self.mock_adb.dump_ui_hierarchy("192.168.1.100:5555")
        self.assertIn("<hierarchy", default_xml)
        self.assertIn("Settings", default_xml)

        custom_xml = "<hierarchy><node text=\"CustomScreen\"/></hierarchy>"
        self.mock_adb.set_fixture("custom", custom_xml)
        self.mock_adb.switch_fixture("custom")
        self.assertEqual(self.mock_adb.dump_ui_hierarchy("192.168.1.100:5555"), custom_xml)

    def test_mock_configurable_failure_and_disconnect(self):
        self.mock_adb.fail_next_command = "connect"
        res = self.mock_adb.connect("192.168.1.100", 5555)
        self.assertFalse(res.success)

        # Reconnect
        self.mock_adb.connect("192.168.1.100", 5555)
        self.mock_adb.simulate_disconnect_after_actions = 2

        res1 = self.mock_adb.execute_shell("192.168.1.100:5555", "input tap 10 10")
        self.assertEqual(res1.exit_code, 0)

        # Action 2 triggers simulated disconnect
        res2 = self.mock_adb.execute_shell("192.168.1.100:5555", "input tap 20 20")
        self.assertNotEqual(res2.exit_code, 0)
        self.assertEqual(self.mock_adb.get_state("192.168.1.100:5555"), DeviceState.DISCONNECTED)

    def test_mock_helper_methods(self):
        self.mock_adb.set_device_state("test-dev", DeviceState.UNAUTHORIZED)
        self.assertEqual(self.mock_adb.get_state("test-dev"), DeviceState.UNAUTHORIZED)
        self.mock_adb.clear_history()
        self.assertEqual(len(self.mock_adb.history), 0)
        self.mock_adb.reset()
        self.assertEqual(len(self.mock_adb.devices), 0)


if __name__ == "__main__":
    unittest.main()
