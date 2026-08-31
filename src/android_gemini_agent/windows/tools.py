"""
Windows Desktop Tool Definitions & Dispatcher for Gemini Decision Engine.
Uses explicit FunctionDeclarations to prevent client-side Automatic Function Calling (AFC).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple
from google.genai import types

from .controller import WindowsController

logger = logging.getLogger(__name__)


def get_windows_tools() -> List[types.Tool]:
    """
    Constructs the complete Google GenAI Tool declarations for Windows desktop automation.
    Equips the model with launch_app, click, type_text, hotkey, press_key, scroll, wait, and finish_task.
    """
    launch_app_func = types.FunctionDeclaration(
        name="launch_app",
        description="Launches an application or opens a program on Windows (e.g. 'notepad', 'calc', 'chrome', 'settings', 'explorer', 'cmd').",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "app_name": types.Schema(
                    type="STRING",
                    description="Name or alias of the application to launch (e.g. 'notepad', 'calc', 'chrome', 'explorer')",
                )
            },
            required=["app_name"],
        ),
    )

    click_func = types.FunctionDeclaration(
        name="click",
        description="Clicks or double-clicks at screen coordinates (x, y) on the Windows desktop.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "x": types.Schema(
                    type="INTEGER",
                    description="X pixel coordinate on screen",
                ),
                "y": types.Schema(
                    type="INTEGER",
                    description="Y pixel coordinate on screen",
                ),
                "button": types.Schema(
                    type="STRING",
                    description="Mouse button: 'left', 'right', or 'middle' (default: 'left')",
                    enum=["left", "right", "middle"],
                ),
                "double": types.Schema(
                    type="BOOLEAN",
                    description="If true, performs a double-click (default: false)",
                ),
            },
            required=["x", "y"],
        ),
    )

    type_text_func = types.FunctionDeclaration(
        name="type_text",
        description="Types text into the active focused Windows control.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "text": types.Schema(
                    type="STRING",
                    description="Text string to type into the focused field",
                ),
                "press_enter": types.Schema(
                    type="BOOLEAN",
                    description="If true, presses Enter after typing (default: false)",
                ),
                "clear_first": types.Schema(
                    type="BOOLEAN",
                    description="If true, clears existing text before typing (default: false)",
                ),
            },
            required=["text"],
        ),
    )

    hotkey_func = types.FunctionDeclaration(
        name="hotkey",
        description="Executes a keyboard shortcut combination on Windows (e.g. ['win', 'r'], ['ctrl', 'c'], ['ctrl', 'v'], ['alt', 'tab'], ['ctrl', 's']).",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "keys": types.Schema(
                    type="ARRAY",
                    items=types.Schema(type="STRING"),
                    description="List of key names to press together (e.g. ['win', 'r'] or ['ctrl', 'a'])",
                )
            },
            required=["keys"],
        ),
    )

    press_key_func = types.FunctionDeclaration(
        name="press_key",
        description="Presses an individual keyboard key on Windows (e.g. 'enter', 'esc', 'tab', 'win', 'space', 'backspace', 'delete', 'up', 'down').",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "key_name": types.Schema(
                    type="STRING",
                    description="Key identifier to press",
                )
            },
            required=["key_name"],
        ),
    )

    scroll_func = types.FunctionDeclaration(
        name="scroll",
        description="Scrolls the active window vertically up or down.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "direction": types.Schema(
                    type="STRING",
                    description="Scroll direction ('up' or 'down')",
                    enum=["up", "down"],
                ),
                "clicks": types.Schema(
                    type="INTEGER",
                    description="Number of scroll steps/clicks (default: 3)",
                ),
            },
            required=["direction"],
        ),
    )

    wait_func = types.FunctionDeclaration(
        name="wait",
        description="Pauses execution to allow UI animations, window loading, or processes to settle.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "seconds": types.Schema(
                    type="NUMBER",
                    description="Duration to wait in seconds (0.5 to 10.0)",
                )
            },
            required=["seconds"],
        ),
    )

    finish_task_func = types.FunctionDeclaration(
        name="finish_task",
        description="Completes the automation task and reports the outcome.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "status": types.Schema(
                    type="STRING",
                    description="Final status outcome: 'SUCCESS' or 'FAILURE'",
                    enum=["SUCCESS", "FAILURE"],
                ),
                "message": types.Schema(
                    type="STRING",
                    description="Detailed summary explaining the outcome or resolution",
                ),
            },
            required=["status", "message"],
        ),
    )

    return [
        types.Tool(
            function_declarations=[
                launch_app_func,
                click_func,
                type_text_func,
                hotkey_func,
                press_key_func,
                scroll_func,
                wait_func,
                finish_task_func,
            ]
        )
    ]


def execute_windows_tool(
    controller: WindowsController,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Executes a tool call against the WindowsController instance.
    Returns (success, result_message).
    """
    name = tool_name.lower().strip()
    try:
        if name in ("click", "tap"):
            x = int(tool_args.get("x", 0))
            y = int(tool_args.get("y", 0))
            button = str(tool_args.get("button", "left"))
            double = bool(tool_args.get("double", False))
            success = controller.click(x, y, button=button, double=double)
            return success, f"Clicked at ({x}, {y}) [button={button}, double={double}]"

        elif name == "type_text":
            text = str(tool_args.get("text", ""))
            press_enter = bool(tool_args.get("press_enter", False))
            clear_first = bool(tool_args.get("clear_first", False))
            success = controller.type_text(text, press_enter=press_enter, clear_first=clear_first)
            return success, f"Typed text '{text}'"

        elif name == "press_key":
            key_name = str(tool_args.get("key_name", tool_args.get("key", "")))
            success = controller.press_key(key_name)
            return success, f"Pressed key '{key_name}'"

        elif name == "hotkey":
            raw_keys = tool_args.get("keys", [])
            if isinstance(raw_keys, str):
                raw_keys = [k.strip() for k in raw_keys.split("+")]
            success = controller.hotkey(*raw_keys)
            return success, f"Executed hotkey: {'+'.join(raw_keys)}"

        elif name == "scroll":
            direction = str(tool_args.get("direction", "down"))
            clicks = int(tool_args.get("clicks", 3))
            success = controller.scroll(clicks=clicks, direction=direction)
            return success, f"Scrolled {direction} ({clicks} clicks)"

        elif name == "launch_app":
            app = str(tool_args.get("app_name", tool_args.get("package_name", "")))
            success = controller.launch_app(app)
            return success, f"Launched application: '{app}'"

        elif name == "wait":
            secs = float(tool_args.get("seconds", 1.0))
            controller.wait(secs)
            return True, f"Waited {secs}s"

        elif name == "finish_task":
            status = str(tool_args.get("status", "SUCCESS"))
            msg = str(tool_args.get("message", "Task finished"))
            return True, f"Finished: {msg} ({status})"

        else:
            return False, f"Unknown Windows tool: '{tool_name}'"

    except Exception as exc:
        return False, f"Tool '{tool_name}' execution error: {exc}"
