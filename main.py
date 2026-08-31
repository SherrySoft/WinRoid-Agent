import os
import sys

# Enable ANSI colors on Windows console
if sys.platform == "win32":
    os.system("")
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        # ENABLE_PROCESSED_OUTPUT = 0x0001
        # ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
        mode = ctypes.c_ulong()
        hOut = kernel32.GetStdHandle(-11)
        if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
            kernel32.SetConsoleMode(hOut, mode.value | 0x0004 | 0x0001 | 0x0002)
    except Exception:
        pass

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from android_gemini_agent.cli.app import main

if __name__ == "__main__":
    sys.exit(main())
