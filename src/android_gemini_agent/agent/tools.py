"""
Gemini Structured Tool Definitions and Execution Dispatcher.
Defines Google GenAI FunctionDeclarations for Android automation actions and dispatches
tool calls directly to DeviceController.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from google.genai import types

if TYPE_CHECKING:
    from ..adb.controller import DeviceController


def get_agent_tools() -> List[types.Tool]:
    """
    Constructs the complete Google GenAI Tool declarations for Android automation.
    Equips the model with tap, type_text, press_key, swipe, wait, and finish_task.
    """
    tap_func = types.FunctionDeclaration(
        name="tap",
        description="Taps at specific pixel coordinates (x, y) on the screen. Must use the exact center coordinates of the target UI element.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "x": types.Schema(
                    type="INTEGER",
                    description="X pixel coordinate (horizontal) on screen",
                ),
                "y": types.Schema(
                    type="INTEGER",
                    description="Y pixel coordinate (vertical) on screen",
                ),
            },
            required=["x", "y"],
        ),
    )

    type_text_func = types.FunctionDeclaration(
        name="type_text",
        description="Types the specified text string into the currently focused editable input field.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "text": types.Schema(
                    type="STRING",
                    description="Text string to enter into the focused field",
                ),
                "clear_first": types.Schema(
                    type="BOOLEAN",
                    description="If true, clears existing text in the field before typing (default: false)",
                ),
                "press_enter": types.Schema(
                    type="BOOLEAN",
                    description="If true, presses the ENTER key after typing text (default: false)",
                ),
            },
            required=["text"],
        ),
    )

    press_key_func = types.FunctionDeclaration(
        name="press_key",
        description="Presses a physical or navigation key on the Android device.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "key_name": types.Schema(
                    type="STRING",
                    description="Name of the key to press",
                    enum=[
                        "BACK",
                        "HOME",
                        "APP_SWITCH",
                        "ENTER",
                        "TAB",
                        "DELETE",
                        "VOLUME_UP",
                        "VOLUME_DOWN",
                        "POWER",
                        "CAMERA",
                    ],
                )
            },
            required=["key_name"],
        ),
    )

    swipe_func = types.FunctionDeclaration(
        name="swipe",
        description="Performs a swipe gesture across the screen to scroll or paginate content.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "direction": types.Schema(
                    type="STRING",
                    description="Direction to swipe: 'up' (scroll down), 'down' (scroll up), 'left' (scroll right), 'right' (scroll left)",
                    enum=["up", "down", "left", "right"],
                ),
                "distance": types.Schema(
                    type="STRING",
                    description="Swipe travel distance: 'short' (25% screen), 'normal' (50% screen), 'long' (75% screen)",
                    enum=["short", "normal", "long"],
                ),
            },
            required=["direction"],
        ),
    )

    wait_func = types.FunctionDeclaration(
        name="wait",
        description="Pauses execution for a duration to allow UI animations, screen transitions, or network loading to settle.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "seconds": types.Schema(
                    type="NUMBER",
                    description="Wait time in seconds (e.g. 0.5 to 10.0)",
                )
            },
            required=["seconds"],
        ),
    )

    finish_task_func = types.FunctionDeclaration(
        name="finish_task",
        description="Terminates the automation agent when the user's objective is completed or if it is unachievable/blocked.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "status": types.Schema(
                    type="STRING",
                    description="Outcome status",
                    enum=["SUCCESS", "FAILURE"],
                ),
                "message": types.Schema(
                    type="STRING",
                    description="Detailed explanation of what was achieved or why the task failed",
                ),
            },
            required=["status", "message"],
        ),
    )

    return [
        types.Tool(
            function_declarations=[
                tap_func,
                type_text_func,
                press_key_func,
                swipe_func,
                wait_func,
                finish_task_func,
            ]
        )
    ]


def execute_tool(
    controller: DeviceController,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Executes a structured tool call by mapping it to appropriate DeviceController methods.

    Args:
        controller: Target DeviceController instance.
        tool_name: Name of the tool to execute.
        tool_args: Dictionary of arguments for the tool.

    Returns:
        Tuple of (success: bool, result_summary: str).
    """
    try:
        if tool_name == "tap":
            x = int(tool_args["x"])
            y = int(tool_args["y"])
            ok = controller.tap(x, y)
            if ok:
                return True, f"Tapped at ({x}, {y})"
            return False, f"Failed to tap at ({x}, {y})"

        elif tool_name == "type_text":
            text = str(tool_args.get("text", ""))
            clear_first = bool(tool_args.get("clear_first", False))
            press_enter = bool(tool_args.get("press_enter", False))
            ok = controller.type_text(
                text, clear_first=clear_first, press_enter=press_enter
            )
            if ok:
                flags = []
                if clear_first:
                    flags.append("cleared")
                if press_enter:
                    flags.append("enter")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                return True, f"Typed '{text}'{flag_str}"
            return False, f"Failed to type text '{text}'"

        elif tool_name == "press_key":
            key_name = str(tool_args["key_name"]).strip()
            # Normalize DELETE key name to DEL for keycode compatibility
            target_key = "DEL" if key_name.upper() == "DELETE" else key_name
            ok = controller.press_key(target_key)
            if ok:
                return True, f"Pressed key {key_name}"
            return False, f"Failed to press key {key_name}"

        elif tool_name == "swipe":
            direction = str(tool_args["direction"]).strip().lower()
            distance = str(tool_args.get("distance", "normal")).strip().lower()
            ratio_map = {"short": 0.25, "normal": 0.5, "long": 0.75}
            ratio = ratio_map.get(distance, 0.5)
            ok = controller.scroll(direction, distance_ratio=ratio)
            if ok:
                return True, f"Swiped {direction} ({distance})"
            return False, f"Failed to swipe {direction}"

        elif tool_name == "wait":
            seconds = float(tool_args.get("seconds", 1.0))
            controller.wait(seconds)
            return True, f"Waited {seconds:.1f}s"

        elif tool_name == "finish_task":
            status = str(tool_args.get("status", "SUCCESS")).upper()
            message = str(tool_args.get("message", "Task completed"))
            return True, f"Finished task with {status}: {message}"

        else:
            return False, f"Unknown tool '{tool_name}'"

    except Exception as e:
        return False, f"Exception executing '{tool_name}': {type(e).__name__}: {str(e)}"
