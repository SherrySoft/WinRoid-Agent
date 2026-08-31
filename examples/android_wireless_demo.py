#!/usr/bin/env python3
"""
Android Wireless Automation Demo
================================
Demonstrates wireless ADB pairing, connection, UI hierarchy extraction with AST container pruning,
and autonomous task execution using the Gemini Agent Decision Engine.

Can run live against a physical Android device or completely offline with the --mock flag.

Usage:
  # Offline Simulation (Zero-hardware / Zero-API-key)
  python examples/android_wireless_demo.py --mock

  # Live Wireless Connection
  python examples/android_wireless_demo.py --connect 192.168.1.100:5555 --task "Enable Dark Theme"

  # Live Android 11+ Pairing + Connection
  python examples/android_wireless_demo.py --pair 192.168.1.100:38912 --code 123456 --connect 192.168.1.100:5555
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

from android_gemini_agent.adb.client import RealAdbClient
from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.adb.mock_client import DEFAULT_MOCK_XML, MockAdbClient
from android_gemini_agent.adb.models import DeviceState
from android_gemini_agent.agent.loop import AgentDecisionEngine
from android_gemini_agent.agent.models import AgentStep, TaskResult
from android_gemini_agent.config import get_config
from android_gemini_agent.parser.formatters import format_line_dsl, format_markdown_table
from android_gemini_agent.parser.parser import UIHierarchyParser

console = Console(highlight=False)

# Realistic Multi-Screen Fixtures for Offline Simulation
SETTINGS_DISPLAY_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.android.settings" bounds="[0,0][1080,2400]">
    <node index="0" text="Display" resource-id="com.android.settings:id/subpage_title" class="android.widget.TextView" package="com.android.settings" bounds="[60,140][900,240]" clickable="false"/>
    <node index="1" text="Brightness level" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,320][980,400]" clickable="true"/>
    <node index="2" text="Dark theme" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,440][800,520]" clickable="true"/>
    <node index="3" text="" resource-id="com.android.settings:id/switch_widget" class="android.widget.Switch" package="com.android.settings" bounds="[880,440][1000,520]" clickable="true" checkable="true" checked="false"/>
    <node index="4" text="Screen timeout" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,560][980,640]" clickable="true"/>
  </node>
</hierarchy>"""

SETTINGS_DARK_ON_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.android.settings" bounds="[0,0][1080,2400]">
    <node index="0" text="Display" resource-id="com.android.settings:id/subpage_title" class="android.widget.TextView" package="com.android.settings" bounds="[60,140][900,240]" clickable="false"/>
    <node index="1" text="Dark theme" resource-id="android:id/title" class="android.widget.TextView" package="com.android.settings" bounds="[180,440][800,520]" clickable="true"/>
    <node index="2" text="" resource-id="com.android.settings:id/switch_widget" class="android.widget.Switch" package="com.android.settings" bounds="[880,440][1000,520]" clickable="true" checkable="true" checked="true"/>
  </node>
</hierarchy>"""


class SimulatedGenAIResponse:
    """Mock Gemini response object matching the google.genai SDK interface."""

    def __init__(self, function_name: str, function_args: Dict[str, Any], thought: str = ""):
        self.text = thought
        self.function_calls = [type("FunctionCall", (), {"name": function_name, "args": function_args})]
        self.usage_metadata = type(
            "UsageMetadata",
            (),
            {"prompt_token_count": 380, "candidates_token_count": 45, "total_token_count": 425},
        )


class SimulatedGeminiClient:
    """
    Intelligent simulated Gemini decision client for offline demonstration.
    Dynamically responds to user objectives and current UI hierarchy states.
    """

    def __init__(self, mock_adb: Optional[MockAdbClient] = None):
        self.mock_adb = mock_adb
        self.turn_count = 0
        self.models = self

    def generate_content(self, model: str, contents: str, config: Any = None) -> SimulatedGenAIResponse:
        self.turn_count += 1
        prompt_lower = contents.lower()

        # Multi-turn Settings -> Display -> Dark theme workflow
        if "dark" in prompt_lower or "display" in prompt_lower or "settings" in prompt_lower:
            if self.turn_count == 1:
                # Step 1: Click Display in Settings Home
                if self.mock_adb:
                    self.mock_adb.set_fixture("display", SETTINGS_DISPLAY_XML)
                    self.mock_adb.switch_fixture("display")
                return SimulatedGenAIResponse(
                    function_name="tap",
                    function_args={"x": 580, "y": 600},
                    thought="I see 'Display' settings in the UI hierarchy (ID 3 at x=580, y=600). Tapping to open display options.",
                )
            elif self.turn_count == 2:
                # Step 2: Toggle Dark Theme Switch
                if self.mock_adb:
                    self.mock_adb.set_fixture("dark_on", SETTINGS_DARK_ON_XML)
                    self.mock_adb.switch_fixture("dark_on")
                return SimulatedGenAIResponse(
                    function_name="tap",
                    function_args={"x": 940, "y": 480},
                    thought="Display settings loaded. The 'Dark theme' switch is located at x=940, y=480. Tapping toggle.",
                )
            else:
                # Step 3: Finish Task
                return SimulatedGenAIResponse(
                    function_name="finish_task",
                    function_args={
                        "status": "SUCCESS",
                        "message": "Dark Theme switch has been enabled successfully in Display Settings.",
                    },
                    thought="Dark Theme switch is now checked=true. Task objective is complete.",
                )

        # Generic Task Fallback Simulation
        if self.turn_count == 1:
            return SimulatedGenAIResponse(
                function_name="tap",
                function_args={"x": 540, "y": 320},
                thought="Inspecting UI tree and tapping search bar to initiate objective.",
            )
        elif self.turn_count == 2:
            return SimulatedGenAIResponse(
                function_name="type_text",
                function_args={"text": "Wi-Fi Preferences", "press_enter": True},
                thought="Typing target query into focused search input field.",
            )
        else:
            return SimulatedGenAIResponse(
                function_name="finish_task",
                function_args={
                    "status": "SUCCESS",
                    "message": f"Successfully completed simulated objective: {contents[:60]}...",
                },
                thought="Verification complete. Screen reached target state.",
            )


def print_banner(mock_mode: bool) -> None:
    """Renders a stylish CLI welcome banner."""
    mode_text = "[bold yellow]OFFLINE SIMULATION (--mock)[/bold yellow]" if mock_mode else "[bold green]LIVE HARDWARE MODE[/bold green]"
    title = f"Android Gemini Automation Agent\n[dim]Wireless ADB & Visionless UI Hierarchy Decision Engine[/dim]\nMode: {mode_text}"
    console.print(Panel(title, border_style="cyan", box=box.ROUNDED, expand=False))


def display_ui_preview(hierarchy_xml: str, parser: UIHierarchyParser, format_type: str) -> None:
    """Parses and renders the compact UI element preview."""
    hierarchy = parser.parse(hierarchy_xml)
    total_elements = len(hierarchy.elements)

    table = Table(
        title=f"Extracted UI Hierarchy Preview ({total_elements} Actionable Elements)",
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
    )
    table.add_column("ID", justify="right", style="bold yellow", width=4)
    table.add_column("Type", style="green", width=10)
    table.add_column("Text / Content-Desc", style="white", min_width=25)
    table.add_column("Center (X, Y)", justify="center", style="cyan", width=14)
    table.add_column("Interactivity", style="magenta", width=16)

    for elem in hierarchy.elements[:8]:
        flags = []
        if elem.clickable:
            flags.append("click")
        if elem.editable:
            flags.append("edit")
        if elem.checkable:
            flags.append("check" if not elem.checked else "checked")
        flags_str = ", ".join(flags) or "info"

        label = elem.text or elem.content_desc or f"<{elem.resource_id}>" if elem.resource_id else "-"
        table.add_row(
            str(elem.elem_id),
            elem.element_type,
            label[:35],
            f"({elem.center[0]}, {elem.center[1]})",
            flags_str,
        )

    console.print(table)
    if total_elements > 8:
        console.print(f"[dim]... and {total_elements - 8} more elements (AST pruned from raw XML)[/dim]\n")


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
            f"  [bold cyan]Turn {step_num}:[/bold cyan] [bold yellow]{tool}[/bold yellow]({args_str}) "
            f"-> [green]{step.tool_result}[/green] [dim]({step.latency_ms:.1f}ms)[/dim]"
        )
    if step.thought:
        console.print(f"    [dim italic]Thought: {step.thought}[/dim italic]")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Android Gemini Agent — Wireless ADB & UI Hierarchy Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mock", action="store_true", help="Run in offline simulation mode without physical hardware")
    parser.add_argument("--connect", type=str, default=None, help="Target device serial/IP:PORT (e.g. 192.168.1.100:5555)")
    parser.add_argument("--pair", type=str, default=None, help="Pairing endpoint IP:PORT (e.g. 192.168.1.100:38912)")
    parser.add_argument("--code", type=str, default=None, help="6-digit Android 11+ pairing code")
    parser.add_argument(
        "--task",
        type=str,
        default="Open Settings and navigate to Display to enable Dark Theme",
        help="Natural language automation task for Gemini Agent",
    )
    parser.add_argument("--model", type=str, default="gemini-2.5-flash", help="Gemini model identifier")
    parser.add_argument(
        "--format",
        type=str,
        choices=["markdown_table", "line_dsl"],
        default="markdown_table",
        help="UI hierarchy representation format",
    )
    parser.add_argument("--max-steps", type=int, default=10, help="Max decision steps")

    args = parser.parse_args()
    settings = get_config()

    print_banner(mock_mode=args.mock)

    # 1. Initialize ADB Client
    if args.mock:
        console.print("[cyan][1/4] Initializing MockAdbClient simulator...[/cyan]")
        adb_client = MockAdbClient()
        adb_client.set_fixture("default", DEFAULT_MOCK_XML)
        target_serial = args.connect or "192.168.1.100:5555"
    else:
        console.print("[cyan][1/4] Discovering ADB executable on host system...[/cyan]")
        adb_path = RealAdbClient.discover_adb_path()
        console.print(f"  [dim]Found ADB at: {adb_path}[/dim]")
        adb_client = RealAdbClient(adb_path=adb_path)
        target_serial = args.connect or settings.device_serial

    # 2. Wireless Pairing (if requested)
    if args.pair:
        if not args.code:
            console.print("[bold red]Error: --code <6-digit PIN> is required when --pair is specified.[/bold red]")
            return 1
        console.print(f"[cyan]Pairing with Android 11+ endpoint {args.pair} using code {args.code}...[/cyan]")
        try:
            pair_ip, pair_port_str = args.pair.split(":", 1)
            pair_res = adb_client.pair(pair_ip, int(pair_port_str), args.code)
            if pair_res.success:
                console.print(f"  [green][OK] Pairing succeeded: {pair_res.message}[/green]")
            else:
                console.print(f"  [bold red][FAIL] Pairing failed: {pair_res.error}[/bold red]")
                if not args.mock:
                    return 1
        except ValueError:
            console.print(f"[bold red]Invalid pairing format '{args.pair}'. Expected IP:PORT.[/bold red]")
            return 1

    # 3. Wireless Connection
    console.print(f"[cyan][2/4] Connecting to target serial {target_serial}...[/cyan]")
    try:
        if ":" in target_serial:
            ip, port_str = target_serial.split(":", 1)
            conn_res = adb_client.connect(ip, int(port_str))
            if conn_res.success:
                console.print(f"  [green][OK] Successfully connected to {target_serial}[/green]")
            else:
                console.print(f"  [bold yellow][!] Connection response: {conn_res.error or conn_res.message}[/bold yellow]")
                if not args.mock:
                    return 1
        else:
            console.print(f"  [dim]Using direct hardware serial: {target_serial}[/dim]")
    except Exception as exc:
        console.print(f"  [yellow]Connection notice: {exc}[/yellow]")

    controller = DeviceController(adb_client=adb_client, target_serial=target_serial)
    ui_parser = UIHierarchyParser()

    # Query Screen Metrics
    w, h = controller.get_screen_size()
    console.print(f"  [dim]Device resolution: {w}x{h} px[/dim]\n")

    # 4. Dump & Inspect UI Hierarchy
    console.print("[cyan][3/4] Extracting screen UI hierarchy & applying AST pruning...[/cyan]")
    t0 = time.time()
    raw_xml = controller.get_ui_hierarchy()
    dt_dump = (time.time() - t0) * 1000
    console.print(f"  [dim]UI extracted in {dt_dump:.1f}ms ({len(raw_xml)} bytes raw XML)[/dim]\n")
    display_ui_preview(raw_xml, ui_parser, args.format)

    # 5. Initialize Gemini Decision Engine
    console.print(f"[cyan][4/4] Executing autonomous task with AgentDecisionEngine...[/cyan]")
    console.print(f"  [bold]Objective:[/bold] \"{args.task}\"")
    console.print(f"  [bold]Model:[/bold] {args.model} | [bold]Max Steps:[/bold] {args.max_steps}\n")

    if args.mock or not settings.is_gemini_configured:
        if not args.mock:
            console.print("[dim yellow]Note: No GEMINI_API_KEY detected in .env; switching decision engine to simulated mode.[/dim yellow]")
        gemini_client = SimulatedGeminiClient(mock_adb=adb_client if isinstance(adb_client, MockAdbClient) else None)
    else:
        try:
            from google import genai
            gemini_client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not initialize Google GenAI SDK ({exc}); using simulated engine.[/yellow]")
            gemini_client = SimulatedGeminiClient()

    engine = AgentDecisionEngine(
        device_controller=controller,
        ui_parser=ui_parser,
        gemini_client=gemini_client,
        model_name=args.model,
        max_steps=args.max_steps,
        action_delay=0.1 if args.mock else settings.action_delay_seconds,
    )

    result: TaskResult = engine.run_task(
        task=args.task,
        on_step_callback=live_step_callback,
    )

    # 6. Render Task Outcome Summary
    console.print()
    status_style = "bold green" if result.is_success else "bold red"
    summary_panel = Panel(
        f"[{status_style}]Status: {result.status}[/{status_style}]\n"
        f"[bold]Message:[/bold] {result.message}\n"
        f"[dim]Steps Executed: {result.step_count} | Duration: {result.total_duration_seconds:.2f}s | "
        f"Total Tokens: {result.token_usage.get('total_tokens', 0)}[/dim]",
        title="Task Execution Summary",
        border_style="green" if result.is_success else "red",
        box=box.ROUNDED,
    )
    console.print(summary_panel)

    return 0 if result.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
