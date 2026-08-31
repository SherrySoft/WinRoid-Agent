"""Text escaping and sanitization utilities for ADB input commands."""

import re
from typing import Set


class TextEscaper:
    """Utilities to safely escape and format text strings for ADB shell input."""

    # Set of characters with special meaning in Android /system/bin/sh
    SHELL_SPECIAL_CHARS: Set[str] = set(r'\"\'&$<>|;()`*?~#!{}[]^\\')

    @classmethod
    def escape_for_adb_input(cls, text: str) -> str:
        """
        Converts text to an ADB input text-safe format.
        - Space ' ' is converted to '%s'.
        - Shell metacharacters are escaped with a leading backslash.
        - Preserves regular alphanumeric and safe punctuation.
        """
        out = []
        for char in text:
            if char == ' ':
                out.append('%s')
            elif char in cls.SHELL_SPECIAL_CHARS:
                out.append(f"\\{char}")
            else:
                out.append(char)
        return "".join(out)

    @classmethod
    def is_pure_ascii(cls, text: str) -> bool:
        """
        Checks if the text consists strictly of ASCII characters (ord < 128).
        Non-ASCII text (e.g. emojis, non-Latin scripts) requires clipboard injection.
        """
        return all(ord(c) < 128 for c in text)

    @classmethod
    def format_clipboard_command(cls, text: str) -> str:
        """
        Formats text for Android 13+ clipboard service (`cmd clipboard set text ...`).
        Escapes internal quotes and backslashes.
        """
        escaped = text.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        return f'cmd clipboard set text "{escaped}"'

    @classmethod
    def generate_clear_keys(cls, count: int = 50) -> str:
        """
        Generates ADB keyevent sequence to move to end and delete up to `count` characters.
        Keycode 123 is KEYCODE_MOVE_END, 67 is KEYCODE_DEL.
        """
        dels = " ".join(["67"] * count)
        return f"input keyevent 123 {dels}"
