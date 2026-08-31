#!/usr/bin/env python3
"""
Windows Desktop Automation Demo
===============================
Demonstrates native Windows UIAutomation tree extraction, desktop application launching,
safe mouse/keyboard actions (clicking, typing with clipboard fallback, hotkeys),
and autonomous task execution using the Gemini Agent Decision Engine (platform="windows").

Can run live on Windows 10/11 or completely offline (cross-platform) with the --mock flag.

Usage:
  # Offline Simulation (Works on Windows, macOS, or Linux)
  python examples/windows_desktop_demo.py --mock

  # Live Windows Desktop Task
  python examples/windows_desktop_demo.py --app notepad --task "Open Notepad and type 'Gemini Agent Automated Note'"
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Enable Windows virtual terminal processing and UTF-8 stream handling
if sys.platform == "win32":
    os.system("")
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mode = ctypes.c_ulong()
        hOut = kernel32.GetStdHandle(-11)
        if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
            kernel32.SetConsoleMode(hOut, mode.value | 0x0004 | 0x0001 | 0x0002)
    except Exception:
        pass
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure 'src' is accessible on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from android_gemini_agent.agent.loop import AgentDecisionEngine
from android_gemini_agent.agent.models import AgentStep, TaskResult
from android_gemini_agent.config import get_config
from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.windows.controller import WindowsController
from android_gemini_agent.windows.parser import WindowsUIParser

console = Console(highlight=False)


# ---------------------------------------------------------------------------
# Mock / Simulated Desktop Components for Offline & Cross-Platform Execution
# ---------------------------------------------------------------------------


class MockWindowsController:
    """Simulates Windows desktop mouse/keyboard actions and app launching in-memory."""

    def __init__(self, parser: Optional[Any] = None):
        self.parser = parser or MockWindowsUIParser()
        self.launched_apps: List[str] = []
        self.action_history: List[Dict[str, Any]] = []
        self.current_window: str = "Desktop"
        self.buffer_text: str = ""

    def get_screen_size(self) -> Tuple[int, int]:
        return (1920, 1080)

    def get_ui_hierarchy(self) -> UIHierarchy:
        return self.parser.extract_hierarchy(active_app=self.current_window)

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> bool:
        self.action_history.append({"action": "click", "x": x, "y": y, "button": button, "double": double})
        return True

    def right_click(self, x: int, y: int) -> bool:
        return self.click(x, y, button="right")

    def double_click(self, x: int, y: int) -> bool:
        return self.click(x, y, button="left", double=True)

    def type_text(self, text: str, press_enter: bool = False, clear_first: bool = False) -> bool:
        if clear_first:
            self.buffer_text = ""
        self.buffer_text += text
        self.action_history.append({"action": "type_text", "text": text, "press_enter": press_enter})
        return True

    def press_key(self, key_name: str) -> bool:
        self.action_history.append({"action": "press_key", "key": key_name})
        return True

    def hotkey(self, *keys: str) -> bool:
        self.action_history.append({"action": "hotkey", "keys": list(keys)})
        return True

    def scroll(self, clicks: int = 3, direction: str = "down", x: Optional[int] = None, y: Optional[int] = None) -> bool:
        self.action_history.append({"action": "scroll", "clicks": clicks, "direction": direction})
        return True

    def launch_app(self, app_name_or_path: str) -> bool:
        app = app_name_or_path.lower().strip()
        self.launched_apps.append(app)
        self.current_window = app
        self.action_history.append({"action": "launch_app", "app": app})
        return True

    def wait(self, seconds: float) -> None:
        time.sleep(min(0.1, float(seconds)))


class MockWindowsUIParser:
    """Generates realistic UIAutomation hierarchies for common Windows applications."""

    def extract_hierarchy(self, root_control: Optional[Any] = None, active_app: str = "notepad") -> UIHierarchy:
        elements: List[UIElement] = []
        app_norm = active_app.lower()

        if "calc" in app_norm:
            # Simulated Calculator Window
            b1 = BoundingBox(x1=200, y1=150, x2=700, y2=850)
            b2 = BoundingBox(x1=220, y1=200, x2=680, y2=280)
            b3 = BoundingBox(x1=230, y1=320, x2=320, y2=390)
            b4 = BoundingBox(x1=570, y1=320, x2=660, y2=390)
            b5 = BoundingBox(x1=340, y1=410, x2=430, y2=480)
            b6 = BoundingBox(x1=570, y1=590, x2=660, y2=660)

            elements = [
                UIElement(
                    elem_id=1,
                    node_class="WindowControl",
                    element_type="Window",
                    resource_id="CalculatorWindow",
                    text="Calculator",
                    content_desc="Calculator Application",
                    package="Microsoft.WindowsCalculator",
                    bounds=b1,
                    center=b1.center,
                    clickable=False,
                ),
                UIElement(
                    elem_id=2,
                    node_class="TextControl",
                    element_type="Text",
                    resource_id="CalculatorResults",
                    text="Display is 0",
                    content_desc="Result Display",
                    package="Microsoft.WindowsCalculator",
                    bounds=b2,
                    center=b2.center,
                    clickable=False,
                ),
                UIElement(
                    elem_id=3,
                    node_class="ButtonControl",
                    element_type="Button",
                    resource_id="num7Button",
                    text="Seven",
                    content_desc="Seven",
                    package="Microsoft.WindowsCalculator",
                    bounds=b3,
                    center=b3.center,
                    clickable=True,
                ),
                UIElement(
                    elem_id=4,
                    node_class="ButtonControl",
                    element_type="Button",
                    resource_id="plusButton",
                    text="Plus",
                    content_desc="Plus",
                    package="Microsoft.WindowsCalculator",
                    bounds=b4,
                    center=b4.center,
                    clickable=True,
                ),
                UIElement(
                    elem_id=5,
                    node_class="ButtonControl",
                    element_type="Button",
                    resource_id="num5Button",
                    text="Five",
                    content_desc="Five",
                    package="Microsoft.WindowsCalculator",
                    bounds=b5,
                    center=b5.center,
                    clickable=True,
                ),
                UIElement(
                    elem_id=6,
                    node_class="ButtonControl",
                    element_type="Button",
                    resource_id="equalButton",
                    text="Equals",
                    content_desc="Equals",
                    package="Microsoft.WindowsCalculator",
                    bounds=b6,
                    center=b6.center,
                    clickable=True,
                ),
            ]
        else:
            # Simulated Notepad Window (Default)
            b1 = BoundingBox(x1=150, y1=100, x2=950, y2=750)
            b2 = BoundingBox(x1=160, y1=135, x2=210, y2=165)
            b3 = BoundingBox(x1=215, y1=135, x2=265, y2=165)
            b4 = BoundingBox(x1=160, y1=175, x2=940, y2=720)
            b5 = BoundingBox(x1=905, y1=105, x2=945, y2=135)

            elements = [
                UIElement(
                    elem_id=1,
                    node_class="WindowControl",
                    element_type="Window",
                    resource_id="NotepadWindow",
                    text="Untitled - Notepad",
                    content_desc="Notepad Application Window",
                    package="Notepad",
                    bounds=b1,
                    center=b1.center,
                    clickable=False,
                ),
                UIElement(
                    elem_id=2,
                    node_class="MenuItemControl",
                    element_type="MenuItem",
                    resource_id="FileMenu",
                    text="File",
                    content_desc="File Menu",
                    package="Notepad",
                    bounds=b2,
                    center=b2.center,
                    clickable=True,
                ),
                UIElement(
                    elem_id=3,
                    node_class="MenuItemControl",
                    element_type="MenuItem",
                    resource_id="EditMenu",
                    text="Edit",
                    content_desc="Edit Menu",
                    package="Notepad",
                    bounds=b3,
                    center=b3.center,
                    clickable=True,
                ),
                UIElement(
                    elem_id=4,
                    node_class="EditControl",
                    element_type="Edit",
                    resource_id="TextEditor",
                    text="Text Editor Document Area",
                    content_desc="Document Body",
                    package="Notepad",
                    bounds=b4,
                    center=b4.center,
                    clickable=True,
                    editable=True,
                ),
                UIElement(
                    elem_id=5,
                    node_class="ButtonControl",
                    element_type="Button",
                    resource_id="CloseButton",
                    text="Close",
                    content_desc="Close Application",
                    package="Notepad",
                    bounds=b5,
                    center=b5.center,
                    clickable=True,
                ),
            ]

        return UIHierarchy(elements=elements, screen_size=(1920, 1080))


class SimulatedGenAIResponse:
    """Mock Gemini response object matching the google.genai SDK interface."""

    def __init__(self, function_name: str, function_args: Dict[str, Any], thought: str = ""):
        self.text = thought
        self.function_calls = [type("FunctionCall", (), {"name": function_name, "args": function_args})]
        self.usage_metadata = type(
            "UsageMetadata",
            (),
            {"prompt_token_count": 310, "candidates_token_count": 38, "total_token_count": 348},
        )


class SimulatedWindowsGeminiClient:
    """Simulates multi-turn desktop reasoning and Windows tool calling."""

    def __init__(self):
        self.turn_count = 0
        self.models = self

    def generate_content(self, model: str, contents: str, config: Any = None) -> SimulatedGenAIResponse:
        self.turn_count += 1
        prompt_lower = contents.lower()

        if "notepad" in prompt_lower or "type" in prompt_lower or "note" in prompt_lower:
            if self.turn_count == 1:
                return SimulatedGenAIResponse(
                    function_name="launch_app",
                    function_args={"app_name": "notepad"},
                    thought="Launching Notepad application to create the requested note.",
                )
            elif self.turn_count == 2:
                return SimulatedGenAIResponse(
                    function_name="type_text",
                    function_args={"text": "Hello from Android Gemini Agent on Windows Desktop!"},
                    thought="Notepad editor window focused. Typing the requested text document contents.",
                )
            elif self.turn_count == 3:
                return SimulatedGenAIResponse(
                    function_name="hotkey",
                    function_args={"keys": ["ctrl", "s"]},
                    thought="Text entered successfully. Executing Ctrl+S hotkey to trigger save dialog.",
                )
            else:
                return SimulatedGenAIResponse(
                    function_name="finish_task",
                    function_args={
                        "status": "SUCCESS",
                        "message": "Notepad opened, automated note text typed, and save hotkey dispatched.",
                    },
                    thought="Desktop workflow completed successfully.",
                )

        # Calculator Workflow
        if "calc" in prompt_lower or "math" in prompt_lower:
            if self.turn_count == 1:
                return SimulatedGenAIResponse(
                    function_name="launch_app",
                    function_args={"app_name": "calc"},
                    thought="Launching Windows Calculator.",
                )
            elif self.turn_count == 2:
                return SimulatedGenAIResponse(
                    function_name="click",
                    function_args={"x": 275, "y": 355},
                    thought="Clicking button '7' on Calculator.",
                )
            else:
                return SimulatedGenAIResponse(
                    function_name="finish_task",
                    function_args={"status": "SUCCESS", "message": "Calculator calculation sequence executed."},
                    thought="Calculation finished.",
                )

        # Generic Windows Task Fallback
        if self.turn_count == 1:
            return SimulatedGenAIResponse(
                function_name="click",
                function_args={"x": 550, "y": 450},
                thought="Focusing main active application window element.",
            )
        else:
            return SimulatedGenAIResponse(
                function_name="finish_task",
                function_args={"status": "SUCCESS", "message": f"Completed desktop task: {contents[:50]}..."},
                thought="Desktop automation objective finished.",
            )


# ---------------------------------------------------------------------------
# Visual Formatting & Step Progress
# ---------------------------------------------------------------------------


def print_banner(mock_mode: bool) -> None:
    mode_str = "[bold yellow]OFFLINE SIMULATION (--mock)[/bold yellow]" if mock_mode else "[bold green]LIVE WINDOWS DESKTOP[/bold green]"
    title = f"Windows Desktop Gemini Automation Agent\n[dim]Native UIAutomation Tree Extraction & Safe Desktop Driver[/dim]\nMode: {mode_str}"
    console.print(Panel(title, border_style="blue", box=box.ROUNDED, expand=False))


def display_windows_ui_table(hierarchy: UIHierarchy) -> None:
    """Renders formatted table of extracted Windows controls."""
    table = Table(
        title=f"Active Windows UI Elements ({len(hierarchy.elements)} Controls Extracted)",
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
    )
    table.add_column("ID", justify="right", style="bold yellow", width=4)
    table.add_column("Control Type", style="green", width=14)
    table.add_column("Name / Text Content", style="white", min_width=30)
    table.add_column("Center (X, Y)", justify="center", style="cyan", width=14)
    table.add_column("Interactive", style="magenta", width=14)

    for elem in hierarchy.elements:
        flags = []
        if elem.clickable:
            flags.append("click")
        if elem.editable:
            flags.append("edit")
        flags_str = ", ".join(flags) or "read-only"

        table.add_row(
            str(elem.elem_id),
            elem.element_type,
            elem.text or f"<{elem.resource_id}>" if elem.resource_id else "-",
            f"({elem.center[0]}, {elem.center[1]})",
            flags_str,
        )

    console.print(table)
    console.print()


def live_step_callback(step: AgentStep) -> None:
    """Callback invoked after each agent turn to render progress."""
    step_num = step.step_number
    tool = step.tool_name
    args_str = ", ".join(f"{k}={v}" for k, v in step.tool_args.items())

    if tool == "finish_task":
        status_color = "bold green" if step.tool_args.get("status") == "SUCCESS" else "bold red"
        msg = step.tool_args.get("message", "")
        console.print(
            f"  [{status_color}]Turn {step_num}: finish_task -> {msg}[/{status_color}] [dim]({step.latency_ms:.1f}ms)[/dim]"
        )
    else:
        console.print(
            f"  [bold blue]Turn {step_num}:[/bold blue] [bold yellow]{tool}[/bold yellow]({args_str}) "
            f"-> [green]{step.tool_result}[/green] [dim]({step.latency_ms:.1f}ms)[/dim]"
        )
    if step.thought:
        console.print(f"    [dim italic]Thought: {step.thought}[/dim italic]")


# ---------------------------------------------------------------------------
# Main CLI Entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Windows Desktop Automation Demo — Gemini Agent & UIAutomation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mock", action="store_true", help="Run in offline simulation mode (works cross-platform)")
    parser.add_argument(
        "--task",
        type=str,
        default="Open Notepad and type 'Hello from Gemini Agent on Windows!' and save",
        help="Natural language automation task for Windows Agent",
    )
    parser.add_argument("--app", type=str, default="notepad", help="Application name to launch and inspect")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash", help="Gemini model identifier")
    parser.add_argument("--max-steps", type=int, default=10, help="Max decision steps")

    args = parser.parse_args()
    settings = get_config()

    is_windows = sys.platform == "win32"
    use_mock = args.mock or (not is_windows)

    print_banner(mock_mode=use_mock)

    if not is_windows and not args.mock:
        console.print("[dim yellow]Notice: Running on non-Windows OS. Automatically enabling cross-platform mock mode.[/dim yellow]\n")

    # 1. Initialize Controller & Parser
    if use_mock:
        console.print("[cyan][1/3] Initializing Mock Windows Desktop Controller & UI Parser...[/cyan]")
        controller = MockWindowsController()
        ui_parser = MockWindowsUIParser()
        # Simulate launching initial app
        controller.launch_app(args.app)
    else:
        console.print("[cyan][1/3] Initializing Native Windows UIAutomation & PyAutoGUI Driver...[/cyan]")
        ui_parser = WindowsUIParser()
        controller = WindowsController(ui_parser=ui_parser)

    screen_w, screen_h = controller.get_screen_size()
    console.print(f"  [dim]Desktop Resolution: {screen_w}x{screen_h} px[/dim]\n")

    # 2. Extract and display active UI Hierarchy
    console.print("[cyan][2/3] Extracting active window UI accessibility tree...[/cyan]")
    t0 = time.time()
    hierarchy = controller.get_ui_hierarchy()
    dt_ms = (time.time() - t0) * 1000
    console.print(f"  [dim]Extracted {len(hierarchy.elements)} UI elements in {dt_ms:.1f}ms[/dim]\n")
    display_windows_ui_table(hierarchy)

    # 3. Initialize Gemini Decision Engine (platform="windows")
    console.print("[cyan][3/3] Executing autonomous task with AgentDecisionEngine(platform='windows')...[/cyan]")
    console.print(f"  [bold]Objective:[/bold] \"{args.task}\"")
    console.print(f"  [bold]Model:[/bold] {args.model} | [bold]Max Steps:[/bold] {args.max_steps}\n")

    if use_mock or not settings.is_gemini_configured:
        if not use_mock:
            console.print("[dim yellow]Note: No GEMINI_API_KEY configured; using simulated Windows decision engine.[/dim yellow]")
        gemini_client = SimulatedWindowsGeminiClient()
    else:
        try:
            from google import genai
            gemini_client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not initialize Google GenAI SDK ({exc}); using simulated engine.[/yellow]")
            gemini_client = SimulatedWindowsGeminiClient()

    engine = AgentDecisionEngine(
        device_controller=controller,
        ui_parser=ui_parser,
        gemini_client=gemini_client,
        model_name=args.model,
        max_steps=args.max_steps,
        action_delay=0.1 if use_mock else 0.5,
    )
    # Ensure platform is explicitly set to windows
    engine.platform = "windows"

    result: TaskResult = engine.run_task(
        task=args.task,
        on_step_callback=live_step_callback,
    )

    # 4. Render Task Outcome Summary
    console.print()
    status_style = "bold green" if result.is_success else "bold red"
    summary_panel = Panel(
        f"[{status_style}]Status: {result.status}[/{status_style}]\n"
        f"[bold]Message:[/bold] {result.message}\n"
        f"[dim]Steps Executed: {result.step_count} | Duration: {result.total_duration_seconds:.2f}s | "
        f"Total Tokens: {result.token_usage.get('total_tokens', 0)}[/dim]",
        title="Windows Task Summary",
        border_style="green" if result.is_success else "red",
        box=box.ROUNDED,
    )
    console.print(summary_panel)

    return 0 if result.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
