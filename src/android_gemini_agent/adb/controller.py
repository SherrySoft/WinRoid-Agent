"""High-level DeviceController facade providing touch, gesture, text, and key interactions."""

import time
from typing import Dict, Optional, Tuple, Union

from .models import DeviceState
from .protocol import AdbClientProtocol
from .text_escaper import TextEscaper


class DeviceController:
    """
    High-level facade for interacting with an Android device.
    Manages gestures, input text escaping, keyevents, package launches,
    and automatic reconnection with exponential backoff.
    """

    KEYCODE_MAP: Dict[str, int] = {
        "HOME": 3,
        "BACK": 4,
        "CALL": 5,
        "ENDCALL": 6,
        "DPAD_UP": 19,
        "DPAD_DOWN": 20,
        "DPAD_LEFT": 21,
        "DPAD_RIGHT": 22,
        "DPAD_CENTER": 23,
        "VOLUME_UP": 24,
        "VOLUME_DOWN": 25,
        "POWER": 26,
        "CAMERA": 27,
        "CLEAR": 28,
        "TAB": 61,
        "SPACE": 62,
        "ENTER": 66,
        "SUBMIT": 66,
        "DEL": 67,
        "BACKSPACE": 67,
        "SEARCH": 84,
        "PAGE_UP": 92,
        "PAGE_DOWN": 93,
        "ESCAPE": 111,
        "MOVE_HOME": 122,
        "MOVE_END": 123,
        "APP_SWITCH": 187,
        "RECENTS": 187,
        "WAKEUP": 224,
        "PASTE": 279,
        "CUT": 277,
        "COPY": 278,
    }

    def __init__(
        self,
        adb_client: AdbClientProtocol,
        target_serial: str,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 3,
        base_backoff_sec: float = 0.5,
    ):
        self.adb = adb_client
        self.serial = target_serial
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_backoff_sec = base_backoff_sec
        self._screen_size: Optional[Tuple[int, int]] = None

    def ensure_connected(self) -> bool:
        """Verifies device connection and initiates auto-reconnect if needed."""
        state = self.adb.get_state(self.serial)
        if state == DeviceState.CONNECTED:
            return True

        if not self.auto_reconnect:
            return False

        return self.auto_reconnect_if_needed()

    def auto_reconnect_if_needed(self) -> bool:
        """Attempts exponential backoff reconnection for wireless endpoints."""
        if ":" not in self.serial:
            # Non-network device (USB serial)
            return self.adb.get_state(self.serial) == DeviceState.CONNECTED

        ip, port_str = self.serial.split(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return False

        for attempt in range(1, self.max_reconnect_attempts + 1):
            backoff = self.base_backoff_sec * (2 ** (attempt - 1))
            time.sleep(backoff)

            if attempt > 1:
                # Disconnect stale socket before retrying
                self.adb.disconnect(self.serial)

            result = self.adb.connect(ip, port)
            if result.success and self.adb.get_state(self.serial) == DeviceState.CONNECTED:
                return True

        return False

    def tap(self, x: Union[int, float], y: Union[int, float]) -> bool:
        """Injects a single tap event at pixel coordinates (x, y)."""
        self.ensure_connected()
        cmd = f"input tap {int(x)} {int(y)}"
        result = self.adb.execute_shell(self.serial, cmd)
        return result.exit_code == 0

    def swipe(
        self,
        x1: Union[int, float],
        y1: Union[int, float],
        x2: Union[int, float],
        y2: Union[int, float],
        duration_ms: int = 400,
    ) -> bool:
        """Injects a touch swipe/drag from (x1, y1) to (x2, y2)."""
        self.ensure_connected()
        cmd = f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}"
        result = self.adb.execute_shell(self.serial, cmd)
        return result.exit_code == 0

    def scroll(
        self,
        direction: str,
        distance_ratio: float = 0.5,
        duration_ms: int = 400,
    ) -> bool:
        """
        Executes a directional scroll relative to the screen dimensions.
        - 'down': scrolls view down (swipes up from 75% to 25% height)
        - 'up': scrolls view up (swipes down from 25% to 75% height)
        - 'left': scrolls view left (swipes right to left)
        - 'right': scrolls view right (swipes left to right)
        """
        w, h = self.get_screen_size()
        cx, cy = w // 2, h // 2
        dir_clean = direction.strip().lower()

        if dir_clean == "down":
            y_start = int(h * 0.75)
            y_end = int(h * 0.25)
            return self.swipe(cx, y_start, cx, y_end, duration_ms)
        elif dir_clean == "up":
            y_start = int(h * 0.25)
            y_end = int(h * 0.75)
            return self.swipe(cx, y_start, cx, y_end, duration_ms)
        elif dir_clean == "left":
            x_start = int(w * 0.85)
            x_end = int(w * 0.15)
            return self.swipe(x_start, cy, x_end, cy, duration_ms)
        elif dir_clean == "right":
            x_start = int(w * 0.15)
            x_end = int(w * 0.85)
            return self.swipe(x_start, cy, x_end, cy, duration_ms)
        else:
            raise ValueError(f"Unknown scroll direction '{direction}'. Must be 'up', 'down', 'left', or 'right'.")

    def press_key(self, key: Union[str, int]) -> bool:
        """
        Presses an Android hardware/software key.
        Accepts integer keycodes (e.g. 4) or named strings ('BACK', 'HOME', 'ENTER').
        """
        self.ensure_connected()
        if isinstance(key, int):
            keycode = key
        elif str(key).isdigit():
            keycode = int(key)
        else:
            key_name = str(key).strip().upper()
            keycode = self.KEYCODE_MAP.get(key_name)
            if keycode is None:
                raise ValueError(f"Unknown key name '{key}'.")

        cmd = f"input keyevent {keycode}"
        result = self.adb.execute_shell(self.serial, cmd)
        return result.exit_code == 0

    def type_text(
        self,
        text: str,
        clear_first: bool = False,
        press_enter: bool = False,
    ) -> bool:
        """
        Types text into the currently focused input field.
        Safely escapes spaces and shell metacharacters; uses clipboard fallback for non-ASCII.
        """
        self.ensure_connected()

        if clear_first:
            clear_cmd = TextEscaper.generate_clear_keys(50)
            self.adb.execute_shell(self.serial, clear_cmd)

        if not text:
            if press_enter:
                return self.press_key("ENTER")
            return True

        if TextEscaper.is_pure_ascii(text):
            escaped = TextEscaper.escape_for_adb_input(text)
            cmd = f'input text "{escaped}"'
            result = self.adb.execute_shell(self.serial, cmd)
        else:
            # Non-ASCII / Unicode / Emoji clipboard fallback
            clip_cmd = TextEscaper.format_clipboard_command(text)
            self.adb.execute_shell(self.serial, clip_cmd)
            result = self.adb.execute_shell(self.serial, f"input keyevent {self.KEYCODE_MAP['PASTE']}")

        if press_enter:
            self.press_key("ENTER")

        return result.exit_code == 0

    def launch_app(self, package_name: str) -> bool:
        """
        Launches an application by package name without needing the main activity name.
        Uses monkey launcher as primary with am start as fallback.
        """
        self.ensure_connected()
        pkg = package_name.strip()
        cmd = f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
        res = self.adb.execute_shell(self.serial, cmd)

        if "Events injected: 1" in res.stdout or res.exit_code == 0:
            return True

        # Fallback via am start
        fallback_cmd = f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p {pkg}"
        res_fb = self.adb.execute_shell(self.serial, fallback_cmd)
        return res_fb.exit_code == 0 and "Error" not in res_fb.stdout

    def get_ui_hierarchy(self) -> str:
        """Extracts the current screen UI hierarchy XML."""
        self.ensure_connected()
        return self.adb.dump_ui_hierarchy(self.serial)

    def get_screen_size(self) -> Tuple[int, int]:
        """Gets screen dimensions (width, height), caching result for subsequent calls."""
        if self._screen_size is None:
            self.ensure_connected()
            self._screen_size = self.adb.get_screen_size(self.serial)
        return self._screen_size

    def wait(self, seconds: float) -> None:
        """Pauses execution to allow animations/screens to settle."""
        time.sleep(max(0.0, float(seconds)))
