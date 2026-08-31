"""Unit tests for DeviceController (gestures, keys, text typing, auto-reconnect, edge cases)."""

import time
import unittest
from unittest.mock import MagicMock, patch

from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.adb.mock_client import MockAdbClient
from android_gemini_agent.adb.models import DeviceState, ShellResult


class TestDeviceController(unittest.TestCase):
    """Test suite for DeviceController functionality."""

    def setUp(self):
        self.mock_adb = MockAdbClient()
        self.serial = "192.168.1.100:5555"
        self.mock_adb.connect("192.168.1.100", 5555)
        self.controller = DeviceController(
            adb_client=self.mock_adb,
            target_serial=self.serial,
            auto_reconnect=True,
            base_backoff_sec=0.01,
        )

    def test_tap(self):
        result = self.controller.tap(540, 960)
        self.assertTrue(result)

        last_cmd = self.mock_adb.history[-1]
        self.assertEqual(last_cmd["action"], "shell")
        self.assertEqual(last_cmd["command"], "input tap 540 960")

    def test_tap_float_coordinates(self):
        result = self.controller.tap(123.7, 456.2)
        self.assertTrue(result)
        self.assertEqual(self.mock_adb.history[-1]["command"], "input tap 123 456")

    def test_swipe(self):
        result = self.controller.swipe(100, 200, 300, 400, duration_ms=500)
        self.assertTrue(result)

        last_cmd = self.mock_adb.history[-1]
        self.assertEqual(last_cmd["action"], "shell")
        self.assertEqual(last_cmd["command"], "input swipe 100 200 300 400 500")

    def test_scroll_directions(self):
        # Default screen size is (1080, 2400)
        # Scroll Down -> Swipe Up from 75% height (1800) to 25% height (600)
        self.controller.scroll("down")
        cmd_down = self.mock_adb.history[-1]["command"]
        self.assertEqual(cmd_down, "input swipe 540 1800 540 600 400")

        # Scroll Up -> Swipe Down from 25% height (600) to 75% height (1800)
        self.controller.scroll("up")
        cmd_up = self.mock_adb.history[-1]["command"]
        self.assertEqual(cmd_up, "input swipe 540 600 540 1800 400")

        # Scroll Left -> Swipe from 85% width (918) to 15% width (162)
        self.controller.scroll("left")
        cmd_left = self.mock_adb.history[-1]["command"]
        self.assertEqual(cmd_left, "input swipe 918 1200 162 1200 400")

        # Scroll Right -> Swipe from 15% width (162) to 85% width (918)
        self.controller.scroll("right")
        cmd_right = self.mock_adb.history[-1]["command"]
        self.assertEqual(cmd_right, "input swipe 162 1200 918 1200 400")

    def test_scroll_case_insensitivity(self):
        self.controller.scroll("DOWN")
        self.assertEqual(self.mock_adb.history[-1]["command"], "input swipe 540 1800 540 600 400")

    def test_scroll_invalid_direction(self):
        with self.assertRaises(ValueError):
            self.controller.scroll("diagonal")

    def test_press_key_named_and_numeric(self):
        key_checks = [
            ("HOME", 3),
            ("BACK", 4),
            ("ENTER", 66),
            ("SUBMIT", 66),
            ("APP_SWITCH", 187),
            ("RECENTS", 187),
            ("DEL", 67),
            ("BACKSPACE", 67),
            ("TAB", 61),
            ("POWER", 26),
            ("WAKEUP", 224),
            ("VOLUME_UP", 24),
            ("VOLUME_DOWN", 25),
            ("PASTE", 279),
            ("SEARCH", 84),
        ]
        for key_name, expected_code in key_checks:
            with self.subTest(key_name=key_name):
                self.controller.press_key(key_name)
                self.assertEqual(self.mock_adb.history[-1]["command"], f"input keyevent {expected_code}")

        # Lowercase key name
        self.controller.press_key("home")
        self.assertEqual(self.mock_adb.history[-1]["command"], "input keyevent 3")

        # Numeric keycode directly
        self.controller.press_key(26)
        self.assertEqual(self.mock_adb.history[-1]["command"], "input keyevent 26")

        # String numeric keycode
        self.controller.press_key("67")
        self.assertEqual(self.mock_adb.history[-1]["command"], "input keyevent 67")

    def test_press_key_invalid_name(self):
        with self.assertRaises(ValueError):
            self.controller.press_key("INVALID_KEY_NAME_XYZ")

    def test_type_text_ascii(self):
        self.controller.type_text("Hello World!")
        self.assertEqual(self.mock_adb.history[-1]["command"], 'input text "Hello%sWorld\\!"')

    def test_type_text_with_clear_and_enter(self):
        self.controller.type_text("Search Query", clear_first=True, press_enter=True)
        history_cmds = [h["command"] for h in self.mock_adb.history if h["action"] == "shell"]
        self.assertTrue(any("input keyevent 123" in c for c in history_cmds))
        self.assertIn('input text "Search%sQuery"', history_cmds)
        self.assertEqual(history_cmds[-1], "input keyevent 66")

    def test_type_text_empty_with_enter(self):
        self.controller.type_text("", press_enter=True)
        self.assertEqual(self.mock_adb.history[-1]["command"], "input keyevent 66")

    def test_type_text_unicode_clipboard_fallback(self):
        self.controller.type_text("Café ☕")
        history_cmds = [h["command"] for h in self.mock_adb.history if h["action"] == "shell"]
        self.assertTrue(any("cmd clipboard set text" in c for c in history_cmds))
        self.assertTrue(any("input keyevent 279" in c for c in history_cmds))

    def test_launch_app_primary(self):
        success = self.controller.launch_app("com.android.settings")
        self.assertTrue(success)
        last_cmd = self.mock_adb.history[-1]["command"]
        self.assertEqual(last_cmd, "monkey -p com.android.settings -c android.intent.category.LAUNCHER 1")

    def test_launch_app_fallback(self):
        success = self.controller.launch_app("nonexistent.package")
        self.assertTrue(success)
        history_cmds = [h["command"] for h in self.mock_adb.history if h["action"] == "shell"]
        self.assertTrue(any("monkey -p nonexistent.package" in c for c in history_cmds))
        self.assertTrue(any("am start -a android.intent.action.MAIN" in c for c in history_cmds))

    def test_get_ui_hierarchy(self):
        xml = self.controller.get_ui_hierarchy()
        self.assertIn("<hierarchy", xml)
        self.assertIn("Settings", xml)

    def test_get_screen_size_caching(self):
        size1 = self.controller.get_screen_size()
        self.assertEqual(size1, (1080, 2400))
        self.mock_adb.screen_size = (720, 1280)
        size2 = self.controller.get_screen_size()
        self.assertEqual(size2, (1080, 2400))

    def test_auto_reconnect_success_on_drop(self):
        self.mock_adb.disconnect(self.serial)
        self.assertEqual(self.mock_adb.get_state(self.serial), DeviceState.DISCONNECTED)

        res = self.controller.tap(100, 200)
        self.assertTrue(res)
        self.assertEqual(self.mock_adb.get_state(self.serial), DeviceState.CONNECTED)

    def test_auto_reconnect_disabled(self):
        controller_no_reconnect = DeviceController(
            adb_client=self.mock_adb,
            target_serial=self.serial,
            auto_reconnect=False,
        )
        self.mock_adb.disconnect(self.serial)
        self.assertFalse(controller_no_reconnect.ensure_connected())

    def test_auto_reconnect_exhausted_retries(self):
        self.mock_adb.disconnect(self.serial)
        self.mock_adb.fail_next_command = "connect"
        with patch.object(self.mock_adb, "connect") as mock_conn:
            mock_conn.return_value = MagicMock(success=False)
            reconnected = self.controller.auto_reconnect_if_needed()
            self.assertFalse(reconnected)

    def test_auto_reconnect_non_network_serial(self):
        usb_controller = DeviceController(
            adb_client=self.mock_adb,
            target_serial="emulator-5554",
            auto_reconnect=True,
            base_backoff_sec=0.01,
        )
        self.assertFalse(usb_controller.ensure_connected())

    def test_wait(self):
        start = time.time()
        self.controller.wait(0.01)
        self.assertGreaterEqual(time.time() - start, 0.009)


if __name__ == "__main__":
    unittest.main()
