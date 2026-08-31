"""
Windows Desktop Controller facade providing native mouse, keyboard, app launching,
and UIAutomation hierarchy extraction.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import pyautogui
    import pyperclip
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

from ..parser.models import UIHierarchy
from .parser import WindowsUIParser

logger = logging.getLogger(__name__)


class WindowsController:
    """Controls Windows desktop UI interactions, gestures, typing, and app management."""

    def __init__(self, ui_parser: Optional[WindowsUIParser] = None):
        self.parser = ui_parser or WindowsUIParser()
        if HAS_PYAUTOGUI:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1

    def get_screen_size(self) -> Tuple[int, int]:
        """Gets primary desktop resolution (width, height)."""
        if HAS_PYAUTOGUI:
            size = pyautogui.size()
            return int(size.width), int(size.height)
        return (1920, 1080)

    def get_ui_hierarchy(self) -> UIHierarchy:
        """Extracts the compact UI hierarchy of the active window or desktop."""
        return self.parser.extract_hierarchy()

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> bool:
        """Clicks or double-clicks at screen coordinates (x, y)."""
        if not HAS_PYAUTOGUI:
            logger.warning("pyautogui is required for native mouse click.")
            return False

        try:
            if double:
                pyautogui.doubleClick(x, y, button=button)
            else:
                pyautogui.click(x, y, button=button)
            return True
        except Exception as exc:
            logger.error(f"Failed to click at ({x}, {y}): {exc}")
            return False

    def right_click(self, x: int, y: int) -> bool:
        """Right-clicks at screen coordinates (x, y)."""
        return self.click(x, y, button="right")

    def double_click(self, x: int, y: int) -> bool:
        """Double-clicks at screen coordinates (x, y)."""
        return self.click(x, y, button="left", double=True)

    def type_text(
        self,
        text: str,
        press_enter: bool = False,
        clear_first: bool = False,
    ) -> bool:
        """
        Types text into the active focused field.
        Uses clipboard paste fallback for complex Unicode / emojis.
        """
        if not HAS_PYAUTOGUI:
            return False

        try:
            if clear_first:
                pyautogui.hotkey("ctrl", "a")
                pyautogui.press("backspace")
                time.sleep(0.05)

            if not text:
                if press_enter:
                    pyautogui.press("enter")
                return True

            # Use clipboard for reliable Unicode & fast typing
            try:
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                pyautogui.write(text, interval=0.01)

            if press_enter:
                time.sleep(0.05)
                pyautogui.press("enter")
            return True
        except Exception as exc:
            logger.error(f"Failed to type text: {exc}")
            return False

    def press_key(self, key_name: str) -> bool:
        """Presses a single keyboard key (e.g. 'enter', 'esc', 'tab', 'win', 'space')."""
        if not HAS_PYAUTOGUI:
            return False

        clean_key = key_name.lower().strip()
        key_map = {
            "return": "enter",
            "windows": "win",
            "escape": "esc",
            "delete": "del",
        }
        target_key = key_map.get(clean_key, clean_key)

        try:
            pyautogui.press(target_key)
            return True
        except Exception as exc:
            logger.error(f"Failed to press key '{key_name}': {exc}")
            return False

    def hotkey(self, *keys: str) -> bool:
        """Executes a keyboard shortcut combination (e.g. hotkey('win', 'r'), hotkey('ctrl', 'c'))."""
        if not HAS_PYAUTOGUI or not keys:
            return False

        clean_keys = [k.lower().strip() for k in keys]
        try:
            pyautogui.hotkey(*clean_keys)
            return True
        except Exception as exc:
            logger.error(f"Failed to execute hotkey {keys}: {exc}")
            return False

    def scroll(self, clicks: int = 3, direction: str = "down", x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Scrolls vertically up or down at optional (x, y) coordinates."""
        if not HAS_PYAUTOGUI:
            return False

        amount = -abs(clicks) * 100 if direction.lower() == "down" else abs(clicks) * 100
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            pyautogui.scroll(amount)
            return True
        except Exception as exc:
            logger.error(f"Failed to scroll: {exc}")
            return False

    def launch_app(self, app_name_or_path: str) -> bool:
        """
        Launches an application or URI on Windows.
        Tries os.startfile first, then subprocess.Popen, then Win+R launcher.
        """
        app = app_name_or_path.strip()
        if not app:
            return False

        # Known common aliases
        aliases = {
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "notepad": "notepad.exe",
            "settings": "ms-settings:",
            "browser": "https://www.google.com",
            "chrome": "chrome.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
        }
        target = aliases.get(app.lower(), app)

        try:
            os.startfile(target)
            return True
        except Exception:
            pass

        try:
            subprocess.Popen(target, shell=True)
            return True
        except Exception:
            pass

        # Fallback via Win+R runner
        if HAS_PYAUTOGUI:
            pyautogui.hotkey("win", "r")
            time.sleep(0.3)
            pyautogui.write(target, interval=0.01)
            pyautogui.press("enter")
            return True

        return False

    def wait(self, seconds: float) -> None:
        """Pauses execution to allow UI animations/windows to load."""
        time.sleep(max(0.0, float(seconds)))
