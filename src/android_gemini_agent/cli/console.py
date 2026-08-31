"""
Rich console utilities, theme formatting, step cards, spinners, and tables
for Android Gemini Automation Agent.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional, Union

from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
import sys

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from ..parser.models import UIHierarchy

# Global console instance
console = Console(legacy_windows=False)


def get_console() -> Console:
    """Returns the shared Rich Console instance."""
    return console


def render_banner(
    device_serial: str = "192.168.1.100:5555",
    model_name: str = "gemini-3.5-flash-lite",
    connected: bool = False,
    api_key_set: bool = True,
    target_console: Optional[Console] = None,
) -> None:
    """Renders the top application welcome banner."""
    c = target_console or console
    conn_badge = "[bold green]CONNECTED[/bold green]" if connected else "[bold red]DISCONNECTED[/bold red]"
    api_badge = "[bold green]CONFIGURED[/bold green]" if api_key_set else "[bold red]NOT SET (Check .env)[/bold red]"

    banner_text = (
        f"[bold cyan]🤖 Android Gemini Automation Agent[/bold cyan]\n"
        f"[dim]Visionless, Token-Optimized Mobile Automation via Wireless ADB & Gemini 3.6[/dim]\n\n"
        f"  [bold white]Target Device:[/bold white]   [bold yellow]{device_serial}[/bold yellow] ({conn_badge})\n"
        f"  [bold white]Gemini Model:[/bold white]    [bold magenta]{model_name}[/bold magenta]\n"
        f"  [bold white]Gemini API Key:[/bold white]  {api_badge}\n"
        f"  [bold white]Interactive Shell:[/bold white] Type [bold green]help[/bold green] for command list or enter instructions directly."
    )

    c.print(
        Panel(
            banner_text,
            box=box.ROUNDED,
            border_style="cyan",
            title="[bold yellow]★ SYSTEM INITIALIZED ★[/bold yellow]",
            subtitle="[dim]Press Ctrl+C to cancel active task • Type 'exit' to quit[/dim]",
        )
    )


@contextmanager
def thinking_spinner(
    message: str = "Gemini 2.5 Flash is analyzing screen hierarchy...",
    target_console: Optional[Console] = None,
) -> Iterator[None]:
    """Context manager showing a live thinking spinner."""
    c = target_console or console
    with c.status(f"[bold cyan]{message}[/bold cyan]", spinner="dots"):
        yield


@contextmanager
def action_spinner(
    message: str = "Executing ADB action on device...",
    target_console: Optional[Console] = None,
) -> Iterator[None]:
    """Context manager showing a live ADB action execution spinner."""
    c = target_console or console
    with c.status(f"[bold yellow]{message}[/bold yellow]", spinner="line"):
        yield


def render_step_card(
    step_num: int,
    total_steps: int,
    tool_name: str,
    tool_args: Dict[str, Any],
    summary: str = "",
    duration_ms: Optional[float] = None,
    target_console: Optional[Console] = None,
) -> None:
    """Renders a formatted card representing an executed agent decision step."""
    c = target_console or console

    # Color code tool name
    tool_color_map = {
        "tap": "bold cyan",
        "type_text": "bold green",
        "press_key": "bold magenta",
        "swipe": "bold yellow",
        "wait": "dim white",
        "finish_task": "bold white on green",
    }
    tool_style = tool_color_map.get(tool_name, "bold blue")

    args_formatted = json.dumps(tool_args, indent=2)
    syntax = Syntax(args_formatted, "json", theme="monokai", line_numbers=False)

    card_content = Text()
    card_content.append(f"Tool: ", style="bold white")
    card_content.append(f"{tool_name}\n", style=tool_style)

    if summary:
        card_content.append(f"Action Summary: ", style="bold white")
        card_content.append(f"{summary}\n", style="white")

    if duration_ms is not None:
        card_content.append(f"Execution Latency: ", style="dim")
        card_content.append(f"{duration_ms:.1f} ms\n", style="bold dim yellow")

    c.print(
        Panel(
            card_content,
            title=f"[bold cyan]Step {step_num}/{total_steps}[/bold cyan] ─ [{tool_style}]{tool_name}[/{tool_style}]",
            subtitle=f"[dim]Tool Arguments: {json.dumps(tool_args)}[/dim]",
            border_style="blue",
            box=box.ROUNDED,
        )
    )


def render_ui_table(
    ui_hierarchy: UIHierarchy,
    max_rows: int = 60,
    target_console: Optional[Console] = None,
) -> None:
    """Renders a Rich Table displaying parsed UI elements from the active screen."""
    c = target_console or console

    table = Table(
        title=f"Visible Screen Hierarchy ({len(ui_hierarchy.elements)} interactive/informative elements)",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        show_lines=True,
    )

    table.add_column("ID", style="bold cyan", justify="right", width=4)
    table.add_column("Type / Class", style="magenta", width=18)
    table.add_column("Resource-ID", style="dim cyan", width=22)
    table.add_column("Label / Text / Desc", style="white", min_width=25)
    table.add_column("Center (X,Y)", style="bold green", justify="center", width=14)
    table.add_column("Bounds", style="dim", width=16)
    table.add_column("Flags", style="bold yellow", justify="center", width=8)

    elements = ui_hierarchy.elements[:max_rows]
    for elem in elements:
        # Flags: C=Clickable, S=Scrollable, E=Editable/Focusable
        flags_list = []
        if elem.clickable:
            flags_list.append("[bold cyan]C[/bold cyan]")
        if elem.scrollable:
            flags_list.append("[bold yellow]S[/bold yellow]")
        if elem.focusable:
            flags_list.append("[bold green]E[/bold green]")
        flags_str = "".join(flags_list) or "[dim]-[/dim]"

        # Format label
        label_text = elem.label() or elem.text or elem.content_desc or "[dim](empty)[/dim]"
        if len(label_text) > 40:
            label_text = label_text[:37] + "..."

        # Simplify class name
        raw_class = getattr(elem, "node_class", None) or getattr(elem, "element_type", None) or getattr(elem, "class_name", "View")
        class_short = raw_class.split(".")[-1] if "." in raw_class else raw_class

        # Simplify resource-id
        res_id_short = elem.resource_id.split("/")[-1] if "/" in elem.resource_id else elem.resource_id

        bounds_str = f"[{elem.bounds.x1},{elem.bounds.y1}][{elem.bounds.x2},{elem.bounds.y2}]"
        center_str = f"({elem.center[0]}, {elem.center[1]})"

        table.add_row(
            str(elem.elem_id),
            class_short,
            res_id_short,
            label_text,
            center_str,
            bounds_str,
            flags_str,
        )

    c.print(table)
    if len(ui_hierarchy.elements) > max_rows:
        c.print(f"[dim]... and {len(ui_hierarchy.elements) - max_rows} more elements hidden (showing top {max_rows}).[/dim]")


def render_outcome_panel(
    status: str,
    message: str,
    total_steps: int = 0,
    duration_seconds: float = 0.0,
    target_console: Optional[Console] = None,
) -> None:
    """Renders final task success or failure outcome panel."""
    c = target_console or console

    is_success = status.upper() == "SUCCESS"
    border_color = "bold green" if is_success else "bold red"
    icon = "✓" if is_success else "✗"
    title_text = f"[{border_color}]{icon} TASK {status.upper()}[/{border_color}]"

    content = (
        f"[bold white]Outcome:[/bold white]          [{border_color}]{status.upper()}[/{border_color}]\n"
        f"[bold white]Summary:[/bold white]          {message}\n"
        f"[bold white]Steps Executed:[/bold white]   [bold yellow]{total_steps}[/bold yellow]\n"
        f"[bold white]Total Duration:[/bold white]   [bold cyan]{duration_seconds:.2f} seconds[/bold cyan]"
    )

    c.print(
        Panel(
            content,
            title=title_text,
            border_style=border_color,
            box=box.DOUBLE,
        )
    )


def render_status_panel(
    device_serial: str,
    device_state: str,
    model_name: str,
    api_key_configured: bool,
    settings_dict: Dict[str, Any],
    target_console: Optional[Console] = None,
) -> None:
    """Renders a comprehensive status panel for device, model, and settings."""
    c = target_console or console

    is_conn = device_state.lower() == "connected"
    conn_badge = "[bold green]CONNECTED (Online)[/bold green]" if is_conn else f"[bold red]{device_state.upper()}[/bold red]"
    api_badge = "[bold green]CONFIGURED (Valid)[/bold green]" if api_key_configured else "[bold red]MISSING / INVALID[/bold red]"

    content = (
        f"[bold cyan]Device Status[/bold cyan]\n"
        f"  • Target Serial:     [bold yellow]{device_serial}[/bold yellow]\n"
        f"  • State:             {conn_badge}\n\n"
        f"[bold cyan]Gemini AI Engine[/bold cyan]\n"
        f"  • Model:             [bold magenta]{model_name}[/bold magenta]\n"
        f"  • API Key:           {api_badge}\n"
        f"  • Temperature:       [bold white]{settings_dict.get('gemini_temperature', 0.2)}[/bold white]\n\n"
        f"[bold cyan]Safety & Limits[/bold cyan]\n"
        f"  • Max Steps/Task:    [bold white]{settings_dict.get('max_agent_steps', 20)}[/bold white]\n"
        f"  • Action Delay:      [bold white]{settings_dict.get('action_delay_seconds', 1.0)}s[/bold white]\n"
        f"  • Loop Threshold:    [bold white]{settings_dict.get('loop_detection_threshold', 3)} steps[/bold white]\n"
        f"  • History Turns:     [bold white]{settings_dict.get('context_history_max_turns', 5)} turns[/bold white]"
    )

    c.print(
        Panel(
            content,
            title="[bold yellow]★ SYSTEM STATUS ★[/bold yellow]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )


def render_settings_table(
    settings_dict: Dict[str, Any],
    target_console: Optional[Console] = None,
) -> None:
    """Renders active settings and their values."""
    c = target_console or console

    table = Table(
        title="Active Runtime Configuration",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
    )
    table.add_column("Setting Key", style="bold cyan")
    table.add_column("Current Value", style="bold yellow")
    table.add_column("Type", style="dim")

    for k, v in settings_dict.items():
        # Mask API key for security
        if "api_key" in k.lower() and v:
            val_str = f"{v[:6]}...{v[-4:]}" if len(str(v)) > 10 else "***"
        else:
            val_str = str(v)
        table.add_row(k, val_str, type(v).__name__)

    c.print(table)
    c.print("[dim]To update a setting: [bold green]settings key=value[/bold green] (e.g. settings max_agent_steps=15)[/dim]\n")


def render_help_panel(target_console: Optional[Console] = None) -> None:
    """Renders command help reference."""
    c = target_console or console

    table = Table(
        title="Available Commands",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Command", style="bold green", width=26)
    table.add_column("Description", style="white")
    table.add_column("Example", style="dim yellow", width=36)

    table.add_row(
        escape("connect [ip:port]"),
        "Connect to wireless Android device. Uses .env defaults if omitted.",
        "connect 192.168.1.100:5555",
    )
    table.add_row(
        escape("pair <ip:port> <code>"),
        "Pair with Android 11+ device using pairing port and 6-digit code.",
        "pair 192.168.1.100:38912 654321",
    )
    table.add_row(
        escape("status"),
        "Display wireless connection state, active Gemini model & quota readiness.",
        "status",
    )
    table.add_row(
        escape("dump_ui"),
        "Dump and inspect interactive UI element table of the current screen.",
        "dump_ui",
    )
    table.add_row(
        escape("run <task>"),
        "Execute natural language automation task on device.",
        "run Open Settings and enable Dark Mode",
    )
    table.add_row(
        escape("<instruction>"),
        "Natural language fallback (run task directly without 'run' prefix).",
        "Open Chrome and search for Gemini",
    )
    table.add_row(
        escape("settings [key=val]"),
        "View active configuration or update setting at runtime.",
        "settings action_delay_seconds=0.5",
    )
    table.add_row(
        escape("help"),
        "Display this command reference guide.",
        "help",
    )
    table.add_row(
        escape("exit / quit"),
        "Disconnect cleanly and exit the interactive shell.",
        "exit",
    )

    c.print(table)


def render_info(message: str, target_console: Optional[Console] = None) -> None:
    """Prints informational message."""
    c = target_console or console
    c.print(f"[bold cyan]ℹ[/bold cyan] [white]{message}[/white]")


def render_success(message: str, target_console: Optional[Console] = None) -> None:
    """Prints success message."""
    c = target_console or console
    c.print(f"[bold green]✓[/bold green] [bold white]{message}[/bold white]")


def render_warning(message: str, target_console: Optional[Console] = None) -> None:
    """Prints warning message."""
    c = target_console or console
    c.print(f"[bold yellow]⚠️  WARNING:[/bold yellow] [yellow]{message}[/yellow]")


def render_error(message: str, target_console: Optional[Console] = None) -> None:
    """Prints error message."""
    c = target_console or console
    c.print(f"[bold red]✗ ERROR:[/bold red] [red]{message}[/red]")
