"""
Interactive REPL Shell & CLI Entrypoint for Android Gemini Automation Agent.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from ..adb.client import RealAdbClient
from ..adb.controller import DeviceController
from ..adb.models import ConnectionResult, DeviceState, PairingResult
from ..adb.protocol import AdbClientProtocol
from ..config import Settings, get_config
from ..parser.models import UIHierarchy
from ..parser.parser import UIHierarchyParser
from .console import (
    action_spinner,
    get_console,
    render_banner,
    render_error,
    render_help_panel,
    render_info,
    render_outcome_panel,
    render_settings_table,
    render_status_panel,
    render_step_card,
    render_success,
    render_ui_table,
    render_warning,
    thinking_spinner,
)


class AndroidAgentCLI:
    """
    Interactive REPL Shell and Command Dispatcher for Android Gemini Automation Agent.
    Manages wireless device pairing, connection, UI inspection, settings, and task execution.
    """

    def __init__(
        self,
        agent_engine: Optional[Any] = None,
        adb_manager: Optional[AdbClientProtocol] = None,
        ui_parser: Optional[UIHierarchyParser] = None,
        config: Optional[Settings] = None,
        console: Optional[Console] = None,
        target_serial: Optional[str] = None,
        platform: str = "android",
    ):
        self.config: Settings = config or get_config()
        self.console: Console = console or get_console()
        self.platform: str = platform.lower().strip()
        self.adb: AdbClientProtocol = adb_manager or RealAdbClient(
            default_timeout_sec=self.config.adb_timeout_seconds
        )
        self.parser: UIHierarchyParser = ui_parser or UIHierarchyParser()
        self.engine: Optional[Any] = agent_engine

        self.target_serial: str = target_serial or self.config.device_serial
        self.controller: Optional[DeviceController] = None
        self.windows_controller: Optional[Any] = None
        self.windows_parser: Optional[Any] = None

        if self.platform == "windows":
            self._init_windows()
        else:
            self._auto_discover_device()
            if not self.controller and self.target_serial:
                self._init_controller()

    def _init_windows(self) -> None:
        """Initializes the Windows desktop controller and parser."""
        try:
            from ..windows.controller import WindowsController
            from ..windows.parser import WindowsUIParser
            self.windows_parser = WindowsUIParser()
            self.windows_controller = WindowsController(ui_parser=self.windows_parser)
        except Exception as exc:
            self.console.print(f"[dim]Windows automation init error: {exc}[/dim]")

    def _auto_discover_device(self) -> bool:
        """Auto-detects and adopts an online connected Android device if available."""
        try:
            state = self.adb.get_state(self.target_serial)
            if state == DeviceState.CONNECTED:
                self._init_controller()
                return True
        except Exception:
            pass

        try:
            devices = self.adb.list_devices()
            connected = [d for d in devices if d.state == DeviceState.CONNECTED]
            if connected:
                self.target_serial = connected[0].serial
                self._init_controller()
                return True
        except Exception:
            pass
        return False

    def _init_controller(self) -> None:
        """Initializes or updates the DeviceController instance for active target serial."""
        self.controller = DeviceController(
            adb_client=self.adb,
            target_serial=self.target_serial,
            auto_reconnect=True,
            max_reconnect_attempts=3,
            base_backoff_sec=0.5,
        )

    def _parse_ip_port(self, target: Optional[str]) -> Tuple[str, int]:
        """Parses IP and Port string (e.g. '192.168.1.50:5555' or '192.168.1.50')."""
        if not target or not target.strip():
            return self.config.adb_device_ip, self.config.adb_device_port

        cleaned = target.strip()
        if ":" in cleaned:
            parts = cleaned.split(":", 1)
            ip = parts[0].strip()
            try:
                port = int(parts[1].strip())
            except ValueError:
                port = self.config.adb_device_port
            return ip, port
        else:
            return cleaned, self.config.adb_device_port

    def handle_devices(self) -> None:
        """Lists all attached devices and highlights active selection."""
        devices = self.adb.list_devices()
        if not devices:
            self.console.print("[dim]No ADB devices detected. Use 'connect <ip:port>' or 'pair <ip:port> <code>'.[/dim]")
            return

        table = Table(title="Attached Android Devices", box=box.ROUNDED, border_style="cyan")
        table.add_column("Active", justify="center", style="bold green")
        table.add_column("Serial / Endpoint", style="bold yellow")
        table.add_column("State", style="white")
        table.add_column("Model", style="cyan")
        table.add_column("Product", style="dim")

        for d in devices:
            is_active = "★" if d.serial == self.target_serial else ""
            state_color = "green" if d.state == DeviceState.CONNECTED else "red"
            table.add_row(
                is_active,
                d.serial,
                f"[{state_color}]{d.state.value}[/{state_color}]",
                d.model,
                d.product,
            )
        self.console.print(table)

    def handle_connect(self, target: Optional[str] = None) -> bool:
        """
        Connects to a wireless Android device.
        Usage: connect [ip:port]
        """
        ip, port = self._parse_ip_port(target)
        self.console.print(f"[dim]Connecting to wireless device at [bold yellow]{ip}:{port}[/bold yellow]...[/dim]")

        result: ConnectionResult = self.adb.connect(ip, port)
        if result.success:
            self.target_serial = f"{ip}:{port}"
            self.config.adb_device_ip = ip
            self.config.adb_device_port = port
            self._init_controller()
            render_success(f"Connected to {self.target_serial} ({result.message})", target_console=self.console)
            return True
        else:
            # Check if device is already connected via mDNS/TLS or list_devices
            if self._auto_discover_device():
                render_success(f"Active wireless device already connected: {self.target_serial}", target_console=self.console)
                return True
            render_error(f"Failed to connect to {ip}:{port}: {result.error or result.message}", target_console=self.console)
            self.console.print(
                "[dim]Troubleshooting tips:\n"
                "  1. Ensure your Android device and PC are connected to the same Wi-Fi network.\n"
                "  2. In Android Developer Options, verify 'Wireless Debugging' is switched ON.\n"
                "  3. Check if the port changed after Wi-Fi reconnection (check 'IP address & Port' on device).\n"
                "  4. If this is the first time connecting, pair the device first: 'pair <ip:port> <code>'\n"
                "  5. Type 'devices' to view all currently detected devices.[/dim]\n"
            )
            return False

    def handle_pair(self, args_str: Optional[str] = None) -> bool:
        """
        Pairs with an Android 11+ device using a Wi-Fi pairing code.
        Usage: pair <ip:port> <6-digit-code>
        """
        if not args_str or not args_str.strip():
            render_error("Missing arguments. Usage: pair <ip:port> <6-digit-code>", target_console=self.console)
            self.console.print("[dim]Example: pair 192.168.1.100:38912 654321[/dim]")
            return False

        tokens = args_str.strip().split()
        if len(tokens) < 2:
            render_error("Both target IP:Port and Pairing Code are required. Usage: pair <ip:port> <code>", target_console=self.console)
            return False

        target_endpoint, pairing_code = tokens[0], tokens[1]
        ip, port = self._parse_ip_port(target_endpoint)

        self.console.print(f"[dim]Attempting pairing with [bold yellow]{ip}:{port}[/bold yellow] using code [bold green]{pairing_code}[/bold green]...[/dim]")

        result: PairingResult = self.adb.pair(ip, port, pairing_code)
        if result.success:
            self.config.adb_device_ip = ip
            time.sleep(1.0)
            if self._auto_discover_device():
                render_success(f"Device at {ip}:{port} paired and connected as active device: {self.target_serial}!", target_console=self.console)
                return True
            render_success(f"Device at {ip}:{port} successfully paired!", target_console=self.console)
            self.console.print(
                "[bold cyan]Important Next Step:[/bold cyan] Pairing port is single-use. "
                "Look at the main 'Wireless Debugging' screen on your device for the active "
                "[bold yellow]Connection IP & Port[/bold yellow], then run: [bold green]connect <ip:port>[/bold green]\n"
            )
            return True
        else:
            render_error(f"Pairing failed: {result.error or result.message}", target_console=self.console)
            self.console.print(
                "[dim]Troubleshooting tips:\n"
                "  1. Ensure the 'Pair device with pairing code' popup dialog is currently open on your phone.\n"
                "  2. Verify that the 6-digit code matches exactly.\n"
                "  3. Note that the pairing dialog displays an ephemeral port separate from the main connection port.[/dim]\n"
            )
            return False

    def handle_platform(self, platform_name: Optional[str]) -> None:
        """Switches between Android phone and Windows desktop automation platforms."""
        if not platform_name or not platform_name.strip():
            self.console.print(f"[bold cyan]Current Target Platform:[/bold cyan] [bold yellow]{self.platform.upper()}[/bold yellow]")
            self.console.print("[dim]Switch platforms using 'platform windows' or 'platform android'.[/dim]")
            return

        target = platform_name.strip().lower()
        if target in ("win", "windows", "desktop", "pc"):
            self.platform = "windows"
            self.engine = None
            self._init_windows()
            render_success("Switched target platform to WINDOWS DESKTOP 🖥️", target_console=self.console)
        elif target in ("android", "phone", "mobile", "adb"):
            self.platform = "android"
            self.engine = None
            self._auto_discover_device()
            render_success("Switched target platform to ANDROID PHONE 📱", target_console=self.console)
        else:
            render_error(f"Unknown platform '{platform_name}'. Choose 'windows' or 'android'.", target_console=self.console)

    def handle_status(self) -> None:
        """Displays system and device connectivity status."""
        if self.platform == "windows":
            dev_serial = "Local Windows Desktop 🖥️"
            dev_state = "ACTIVE"
        else:
            dev_serial = self.target_serial
            state = self.adb.get_state(self.target_serial)
            dev_state = state.value if hasattr(state, "value") else str(state)

        render_status_panel(
            device_serial=dev_serial,
            device_state=dev_state,
            model_name=self.config.gemini_model,
            api_key_configured=self.config.is_gemini_configured,
            settings_dict=self.config.to_dict(),
            target_console=self.console,
        )

    def handle_dump_ui(self) -> Optional[UIHierarchy]:
        """
        Dumps the active screen UI hierarchy from the connected device and renders a formatted table.
        Usage: dump_ui
        """
        if self.platform == "windows":
            if not self.windows_controller:
                self._init_windows()
            try:
                with action_spinner("Dumping Windows active UI hierarchy...", target_console=self.console):
                    ui_hierarchy = self.windows_controller.get_ui_hierarchy()
                render_ui_table(ui_hierarchy, target_console=self.console)
                return ui_hierarchy
            except Exception as exc:
                render_error(f"Failed to dump Windows UI hierarchy: {exc}", target_console=self.console)
                return None

        if not self.controller:
            self._init_controller()

        state = self.adb.get_state(self.target_serial)
        if state != DeviceState.CONNECTED:
            render_warning(f"Device {self.target_serial} is not connected ({state}). Attempting connect...", target_console=self.console)
            if not self.handle_connect(self.target_serial):
                return None

        try:
            with action_spinner(f"Dumping UI hierarchy from {self.target_serial}...", target_console=self.console):
                raw_xml = self.controller.get_ui_hierarchy()
                screen_size = self.controller.get_screen_size()
                ui_hierarchy = self.parser.parse(raw_xml, screen_size=screen_size)

            render_ui_table(ui_hierarchy, target_console=self.console)
            return ui_hierarchy
        except Exception as exc:
            render_error(f"Failed to dump UI hierarchy: {exc}", target_console=self.console)
            return None

    def handle_settings(self, arg_str: Optional[str] = None) -> None:
        """
        Displays or updates configuration settings.
        Usage: settings [key=value]
        """
        if not arg_str or not arg_str.strip():
            render_settings_table(self.config.to_dict(), target_console=self.console)
            return

        cleaned = arg_str.strip()
        if "=" not in cleaned:
            render_error("Invalid settings format. Usage: settings key=value (e.g. settings max_agent_steps=15)", target_console=self.console)
            return

        key, val = cleaned.split("=", 1)
        key = key.strip()
        val = val.strip()

        try:
            self.config.update_setting(key, val)
            render_success(f"Configuration setting '{key}' updated to: {getattr(self.config, key.lower())}", target_console=self.console)
        except Exception as exc:
            render_error(f"Failed to update setting '{key}': {exc}", target_console=self.console)

    def handle_help(self) -> None:
        """Renders command help guide."""
        render_help_panel(target_console=self.console)

    def handle_run_task(self, task_description: str) -> Dict[str, Any]:
        """
        Executes a natural language automation task on the target device or Windows desktop.
        Usage: run <task description> or direct prompt.
        """
        task_clean = task_description.strip()
        if not task_clean:
            render_error("Task description cannot be empty.", target_console=self.console)
            return {"status": "FAILURE", "message": "Empty task description", "steps": [], "duration_seconds": 0.0}

        if self.platform == "windows":
            if not self.windows_controller:
                self._init_windows()
            active_controller = self.windows_controller
            active_parser = self.windows_parser
            target_display = "Windows Desktop 🖥️"
        else:
            if not self.controller:
                self._init_controller()
            state = self.adb.get_state(self.target_serial)
            if state != DeviceState.CONNECTED:
                render_warning(f"Device {self.target_serial} is not connected ({state}). Connecting before running task...", target_console=self.console)
                if not self.handle_connect(self.target_serial):
                    render_error("Aborting task: could not establish connection to Android device.", target_console=self.console)
                    return {"status": "FAILURE", "message": "Device not connected", "steps": [], "duration_seconds": 0.0}
            active_controller = self.controller
            active_parser = self.parser
            target_display = self.target_serial

        # Initialize engine if not already set or provided
        if self.engine is None:
            if not self.config.is_gemini_configured:
                render_error(
                    "GEMINI_API_KEY is not configured or is a placeholder. "
                    "Please set your Gemini API key in the .env file or via environment variables.",
                    target_console=self.console,
                )
                return {"status": "FAILURE", "message": "Missing GEMINI_API_KEY", "steps": [], "duration_seconds": 0.0}

            try:
                from google import genai
                from ..agent.loop import AgentDecisionEngine

                gemini_client = genai.Client(api_key=self.config.gemini_api_key)
                self.engine = AgentDecisionEngine(
                    device_controller=active_controller,
                    ui_parser=active_parser,
                    gemini_client=gemini_client,
                    model_name=self.config.gemini_model,
                    max_steps=self.config.max_agent_steps,
                    action_delay=self.config.action_delay_seconds,
                    loop_threshold=self.config.loop_detection_threshold,
                )
            except Exception as exc:
                render_error(f"Failed to initialize Gemini Agent Engine: {exc}", target_console=self.console)
                return {"status": "FAILURE", "message": f"Engine initialization error: {exc}", "steps": [], "duration_seconds": 0.0}

        self.console.print(f"\n[bold cyan]🚀 Launching Task:[/bold cyan] [bold white]{task_clean}[/bold white]")
        self.console.print(f"[dim]Platform: {self.platform.upper()} • Model: {self.config.gemini_model} • Target: {target_display} • Max Steps: {self.config.max_agent_steps}[/dim]\n")

        start_time = time.perf_counter()

        def step_callback(step_record: Any) -> None:
            if hasattr(step_record, "step_number"):
                step_num = step_record.step_number
                tool_name = step_record.tool_name
                tool_args = step_record.tool_args
                summary = step_record.thought or step_record.tool_result or ""
                duration_ms = step_record.latency_ms
            elif isinstance(step_record, dict):
                step_num = step_record.get("step", step_record.get("step_number", 1))
                tool_name = step_record.get("tool", step_record.get("tool_name", "unknown"))
                tool_args = step_record.get("args", step_record.get("tool_args", {}))
                summary = step_record.get("summary", step_record.get("thought", ""))
                duration_ms = step_record.get("duration_ms", step_record.get("latency_ms"))
            else:
                step_num = 1
                tool_name = "action"
                tool_args = {}
                summary = str(step_record)
                duration_ms = None

            render_step_card(
                step_num=step_num,
                total_steps=self.config.max_agent_steps,
                tool_name=tool_name,
                tool_args=tool_args,
                summary=summary,
                duration_ms=duration_ms,
                target_console=self.console,
            )

        try:
            result = self.engine.run_task(task_clean, on_step_callback=step_callback)
            elapsed = time.perf_counter() - start_time

            # Normalize result dict
            if hasattr(result, "status"):
                status = getattr(result, "status")
                message = getattr(result, "message", "")
                steps = getattr(result, "steps", [])
            elif isinstance(result, dict):
                status = result.get("status", "SUCCESS")
                message = result.get("message", "")
                steps = result.get("steps", [])
            else:
                status = "SUCCESS"
                message = str(result)
                steps = []

            step_count = len(steps) if steps else result.get("step_count", 0) if isinstance(result, dict) else 0

            render_outcome_panel(
                status=status,
                message=message,
                total_steps=step_count,
                duration_seconds=elapsed,
                target_console=self.console,
            )
            return {
                "status": status,
                "message": message,
                "steps": steps,
                "step_count": step_count,
                "duration_seconds": elapsed,
            }
        except KeyboardInterrupt:
            elapsed = time.perf_counter() - start_time
            render_warning("Task execution interrupted by user (Ctrl+C). Aborted active loop.", target_console=self.console)
            render_outcome_panel(
                status="FAILURE",
                message="Aborted by user (Ctrl+C)",
                total_steps=0,
                duration_seconds=elapsed,
                target_console=self.console,
            )
            return {
                "status": "FAILURE",
                "message": "Aborted by user (Ctrl+C)",
                "steps": [],
                "step_count": 0,
                "duration_seconds": elapsed,
            }
        except Exception as exc:
            elapsed = time.perf_counter() - start_time
            render_error(f"Task encountered unexpected exception: {exc}", target_console=self.console)
            render_outcome_panel(
                status="FAILURE",
                message=str(exc),
                total_steps=0,
                duration_seconds=elapsed,
                target_console=self.console,
            )
            return {
                "status": "FAILURE",
                "message": str(exc),
                "steps": [],
                "step_count": 0,
                "duration_seconds": elapsed,
            }

    def run_command(self, user_input: str) -> bool:
        """
        Parses and executes a single CLI command string.
        Returns False if the REPL should terminate (exit/quit), True otherwise.
        """
        raw = user_input.strip().lstrip(":")
        if not raw:
            return True

        tokens = raw.split(maxsplit=1)
        verb = tokens[0].lower()
        args = tokens[1].strip() if len(tokens) > 1 else None

        if verb in ("exit", "quit", "q"):
            self.console.print("[bold yellow]Exiting Android Gemini Agent. Goodbye![/bold yellow]")
            return False
        elif verb in ("devices", "list_devices", "ls"):
            self.handle_devices()
        elif verb in ("use", "select"):
            if not args:
                render_error("Usage: use <serial>", target_console=self.console)
            else:
                self.target_serial = args
                self._init_controller()
                render_success(f"Active target device set to: {self.target_serial}", target_console=self.console)
        elif verb in ("platform", "mode"):
            self.handle_platform(args)
        elif verb in ("windows", "win", "desktop", "pc"):
            self.handle_platform("windows")
        elif verb in ("android", "phone", "mobile"):
            self.handle_platform("android")
        elif verb == "connect":
            self.handle_connect(args)
        elif verb == "pair":
            self.handle_pair(args)
        elif verb == "status":
            self.handle_status()
        elif verb == "dump_ui":
            self.handle_dump_ui()
        elif verb == "settings":
            self.handle_settings(args)
        elif verb == "help":
            self.handle_help()
        elif verb == "run":
            if not args:
                render_error("Usage: run <task description>", target_console=self.console)
            else:
                self.handle_run_task(args)
        else:
            # Natural language task fallback
            self.handle_run_task(raw)

        return True

    def run_repl(self) -> None:
        """Starts the interactive REPL shell."""
        if self.platform == "windows":
            banner_serial = "Local Windows Desktop 🖥️"
            is_conn = True
        else:
            self._auto_discover_device()
            banner_serial = self.target_serial
            state = self.adb.get_state(self.target_serial)
            is_conn = (state == DeviceState.CONNECTED)

        render_banner(
            device_serial=banner_serial,
            model_name=self.config.gemini_model,
            connected=is_conn,
            api_key_set=self.config.is_gemini_configured,
            target_console=self.console,
        )

        while True:
            try:
                user_input = Prompt.ask(f"[bold green]{self.platform}-gemini[/bold green] > ").strip()
                if not user_input:
                    continue
                should_continue = self.run_command(user_input)
                if not should_continue:
                    break
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Interrupted. Type 'exit' to quit.[/yellow]")
            except EOFError:
                self.console.print("\n[bold yellow]Exiting Gemini Automation Agent. Goodbye![/bold yellow]")
                break


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint with argument parsing and REPL launcher."""
    parser = argparse.ArgumentParser(
        description="Gemini Automation Agent - Visionless AI Automation for Android & Windows"
    )
    parser.add_argument(
        "--platform",
        "-p",
        choices=["android", "windows"],
        default="android",
        help="Target platform ('android' for phone, 'windows' for PC desktop)",
    )
    parser.add_argument(
        "--connect",
        metavar="IP:PORT",
        nargs="?",
        const="",
        help="Connect to wireless device (default: configured ADB_DEVICE_IP:ADB_DEVICE_PORT)",
    )
    parser.add_argument(
        "--pair",
        nargs=2,
        metavar=("IP:PORT", "CODE"),
        help="Pair with Android 11+ device using pairing code",
    )
    parser.add_argument(
        "--task",
        "-t",
        metavar="DESCRIPTION",
        help="Run a single automation task and exit",
    )
    parser.add_argument(
        "--dump-ui",
        action="store_true",
        help="Dump and display active screen UI hierarchy and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display device and configuration status and exit",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL_NAME",
        help="Override Gemini model identifier (e.g. gemini-3.5-flash-lite)",
    )

    args = parser.parse_args(argv)
    config = get_config()

    if args.model:
        config.gemini_model = args.model

    cli = AndroidAgentCLI(config=config, platform=args.platform)

    # Process one-shot flags
    if args.pair:
        ip_port, code = args.pair
        success = cli.handle_pair(f"{ip_port} {code}")
        return 0 if success else 1

    if args.connect is not None:
        target = args.connect if args.connect else None
        cli.handle_connect(target)

    if args.status:
        cli.handle_status()
        return 0

    if args.dump_ui:
        cli.handle_dump_ui()
        return 0

    if args.task:
        result = cli.handle_run_task(args.task)
        return 0 if result.get("status") == "SUCCESS" else 1

    # Start interactive REPL if no one-shot command was given
    cli.run_repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
