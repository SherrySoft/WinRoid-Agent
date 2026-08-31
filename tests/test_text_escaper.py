"""Unit tests for TextEscaper (space substitution, shell escaping, ASCII checks, edge cases)."""

import unittest
from android_gemini_agent.adb.text_escaper import TextEscaper


class TestTextEscaper(unittest.TestCase):
    """Comprehensive test suite for TextEscaper class."""

    def test_simple_text_without_spaces_or_special_chars(self):
        self.assertEqual(TextEscaper.escape_for_adb_input("HelloWorld"), "HelloWorld")
        self.assertEqual(TextEscaper.escape_for_adb_input("12345"), "12345")
        self.assertEqual(TextEscaper.escape_for_adb_input("abc_def-123.com"), "abc_def-123.com")

    def test_space_substitution(self):
        self.assertEqual(TextEscaper.escape_for_adb_input("Hello World"), "Hello%sWorld")
        self.assertEqual(TextEscaper.escape_for_adb_input("   "), "%s%s%s")
        self.assertEqual(TextEscaper.escape_for_adb_input(" android  gemini "), "%sandroid%s%sgemini%s")
        self.assertEqual(TextEscaper.escape_for_adb_input("Multiple   Spaces   In   Between"), "Multiple%s%s%sSpaces%s%s%sIn%s%s%sBetween")

    def test_shell_metacharacters_escaping(self):
        test_cases = [
            ("Hello World!", "Hello%sWorld\\!"),
            ('echo "test"', 'echo%s\\"test\\"'),
            ("user's phone", "user\\'s%sphone"),
            ("A & B", "A%s\\&%sB"),
            ("price is $100 & tax > 5%", "price%sis%s\\$100%s\\&%stax%s\\>%s5%"),
            ("cat file | grep text", "cat%sfile%s\\|%sgrep%stext"),
            ("(foo; bar)", "\\(foo\\;%sbar\\)"),
            ("path/to/file*?", "path/to/file\\*\\?"),
            ("~root#admin", "\\~root\\#admin"),
            ("{key: [val]}", "\\{key:%s\\[val\\]\\}"),
            ("calc 2^8", "calc%s2\\^8"),
            ("back\\slash", "back\\\\slash"),
            ("`command`", "\\`command\\`"),
            ("all-in-one: $&;|<>()\"'\\`*?~#!{}[]^", "all-in-one:%s\\$\\&\\;\\|\\<\\>\\(\\)\\\"\\'\\\\\\`\\*\\?\\~\\#\\!\\{\\}\\[\\]\\^"),
        ]
        for raw_input, expected in test_cases:
            with self.subTest(raw_input=raw_input):
                self.assertEqual(TextEscaper.escape_for_adb_input(raw_input), expected)

    def test_empty_string(self):
        self.assertEqual(TextEscaper.escape_for_adb_input(""), "")

    def test_long_string(self):
        long_str = "a b $ " * 100
        expected = "a%sb%s\\$%s" * 100
        self.assertEqual(TextEscaper.escape_for_adb_input(long_str), expected)

    def test_is_pure_ascii(self):
        # Valid ASCII
        self.assertTrue(TextEscaper.is_pure_ascii("Hello World 123!@#$%^&*()"))
        self.assertTrue(TextEscaper.is_pure_ascii("a\nb\tc"))
        self.assertTrue(TextEscaper.is_pure_ascii(""))
        self.assertTrue(TextEscaper.is_pure_ascii("~`!@#$%^&*()-_=+[{]}\\|;:'\",<.>/?"))

        # Non-ASCII: emojis, non-Latin scripts, accented characters, ZWJ sequences
        self.assertFalse(TextEscaper.is_pure_ascii("Hello 🌍"))
        self.assertFalse(TextEscaper.is_pure_ascii("café"))
        self.assertFalse(TextEscaper.is_pure_ascii("日本語"))
        self.assertFalse(TextEscaper.is_pure_ascii("مرحبا"))
        self.assertFalse(TextEscaper.is_pure_ascii("Привет"))
        self.assertFalse(TextEscaper.is_pure_ascii("👨‍👩‍👧‍👦"))
        self.assertFalse(TextEscaper.is_pure_ascii("🏳️‍🌈"))
        self.assertFalse(TextEscaper.is_pure_ascii("Übung macht den Meister"))

    def test_format_clipboard_command(self):
        clip_cmd = TextEscaper.format_clipboard_command("Hello World")
        self.assertEqual(clip_cmd, 'cmd clipboard set text "Hello World"')

        clip_cmd_special = TextEscaper.format_clipboard_command('He said "hello" & $price = 10')
        self.assertEqual(clip_cmd_special, 'cmd clipboard set text "He said \\"hello\\" & \\$price = 10"')

        clip_cmd_backticks = TextEscaper.format_clipboard_command('run `rm -rf /` and \\path')
        self.assertEqual(clip_cmd_backticks, 'cmd clipboard set text "run \\`rm -rf /\\` and \\\\path"')

    def test_generate_clear_keys(self):
        cmd = TextEscaper.generate_clear_keys(5)
        self.assertEqual(cmd, "input keyevent 123 67 67 67 67 67")

        cmd_default = TextEscaper.generate_clear_keys(3)
        self.assertTrue(cmd_default.startswith("input keyevent 123"))
        self.assertEqual(cmd_default.count("67"), 3)

        cmd_zero = TextEscaper.generate_clear_keys(0)
        self.assertEqual(cmd_zero, "input keyevent 123 ")


if __name__ == "__main__":
    unittest.main()
