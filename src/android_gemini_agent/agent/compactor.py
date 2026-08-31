"""
Context Compactor and System Prompt Builder.
Manages rolling action history compaction, token-bounded prompt generation, and screen state representation,
ensuring per-turn prompt token consumption remains well below 1,500 tokens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..parser.formatters import estimate_tokens

if TYPE_CHECKING:
    from ..parser.models import UIHierarchy

DEFAULT_SYSTEM_PROMPT = """You are an autonomous Android UI automation agent powered by Gemini.
Your objective is to complete the user's task on the Android device by inspecting visible UI elements and invoking tools.

Operational Guidelines:
1. Examine the current screen UI elements table carefully (Element IDs, element types, text/labels, resource IDs, and Center (X, Y) coordinates).
2. Choose from the available tools:
   - tap(x, y): Tap the exact center coordinates of the target interactive element.
   - type_text(text, clear_first, press_enter): Enter text into the focused input field.
   - press_key(key_name): Press navigation/hardware keys (BACK, HOME, APP_SWITCH, ENTER, etc.).
   - swipe(direction, distance): Swipe the screen to scroll ('up' to scroll down, 'down' to scroll up, 'left', 'right').
   - wait(seconds): Wait for loading or animation to settle (0.5 to 10.0 seconds).
   - finish_task(status, message): Terminate when the goal is accomplished (SUCCESS) or impossible (FAILURE).
3. Do not tap coordinates outside the target element's bounding center.
4. When the goal is completed or blocked, you MUST call finish_task.
5. CRITICAL: You MUST ALWAYS invoke one of the provided tools on every turn. Never return plain text without calling a tool."""

DEFAULT_WINDOWS_SYSTEM_PROMPT = """You are an autonomous Windows desktop UI automation agent powered by Gemini.
Your objective is to complete the user's task on Windows by inspecting visible UI elements and invoking tools.

Operational Guidelines:
1. If the target application is not currently open on screen, use launch_app(app_name="...") to open it (e.g. 'notepad', 'calc', 'chrome', 'settings', 'explorer', 'cmd').
2. Examine the current screen UI elements table carefully (Element IDs, element types, text/labels, and Center (X, Y) coordinates).
3. Choose from the available tools:
   - launch_app(app_name): Launch desktop app or Windows program.
   - click(x, y, button, double): Click or double-click at screen coordinates.
   - type_text(text, press_enter, clear_first): Enter text into the active focused control.
   - hotkey(keys): Execute Windows shortcut combinations (e.g. ['win', 'r'], ['ctrl', 'c'], ['alt', 'tab']).
   - press_key(key_name): Press individual keyboard keys (e.g. 'enter', 'esc', 'tab', 'win').
   - scroll(direction, clicks): Scroll vertically.
   - wait(seconds): Wait for windows or animations to open.
   - finish_task(status, message): Terminate when the goal is accomplished (SUCCESS) or impossible (FAILURE).
4. When the goal is completed or blocked, you MUST call finish_task.
5. CRITICAL: You MUST ALWAYS invoke one of the provided tools on every turn. Never return plain text without calling a tool."""


class HistoryCompactor:
    """
    Rolling action history compactor and turn prompt builder.
    Keeps a bounded window of recent steps formatted as single-line summaries to prevent token explosion.
    """

    def __init__(self, max_turns: int = 10):
        """
        Args:
            max_turns: Maximum number of recent actions to maintain in rolling memory.
        """
        self.max_turns = max_turns
        self.steps: List[Dict[str, Any]] = []

    def add_step(
        self,
        step_num: int,
        tool_name: str,
        tool_args: Dict[str, Any],
        result_summary: str,
    ) -> None:
        """Adds an executed step to the history and prunes oldest entries exceeding max_turns."""
        self.steps.append(
            {
                "step": step_num,
                "tool": tool_name,
                "args": dict(tool_args),
                "summary": result_summary,
            }
        )
        if len(self.steps) > self.max_turns:
            self.steps.pop(0)

    def format_history_prompt(self) -> str:
        """Formats recorded steps into a compact multi-line summary string."""
        if not self.steps:
            return "No previous actions recorded."
        lines: List[str] = []
        for s in self.steps:
            args_str = ", ".join(f"{k}={v}" for k, v in s["args"].items())
            lines.append(f"[Step {s['step']}] {s['tool']}({args_str}) -> {s['summary']}")
        return "\n".join(lines)

    def build_system_prompt(self, platform: str = "android") -> str:
        """Returns the base system prompt customized for the target platform."""
        if str(platform).lower() == "windows":
            return DEFAULT_WINDOWS_SYSTEM_PROMPT
        return DEFAULT_SYSTEM_PROMPT

    def build_turn_prompt(
        self,
        objective: str,
        ui_hierarchy: UIHierarchy,
        recovery_prompt: str = "",
        format_type: str = "markdown_table",
    ) -> str:
        """
        Builds the prompt payload for the current agent turn.

        Args:
            objective: User's high-level task goal.
            ui_hierarchy: Parsed UIHierarchy representing the current screen.
            recovery_prompt: Optional loop detector recovery injection warning.
            format_type: Format style for UI elements ('markdown_table' or 'line_dsl').

        Returns:
            Structured prompt text string.
        """
        history_text = self.format_history_prompt()
        compact_ui = ui_hierarchy.to_prompt_text(format_type)

        sections: List[str] = [
            f"User Objective: {objective}",
            f"Action History:\n{history_text}",
            f"Current Screen State (UI Elements):\n{compact_ui}",
        ]

        if recovery_prompt and recovery_prompt.strip():
            sections.append(f"Recovery Guidance:\n{recovery_prompt.strip()}")

        return "\n\n".join(sections)

    def estimate_prompt_tokens(self, prompt: str) -> int:
        """Estimates token count for the given prompt text."""
        return estimate_tokens(prompt)

    def reset(self) -> None:
        """Clears all historical steps."""
        self.steps.clear()


# Alias for backward and design document compatibility
ContextCompactor = HistoryCompactor
