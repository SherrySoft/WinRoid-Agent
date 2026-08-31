"""
Comprehensive unit tests for Rich Console formatting and AndroidAgentCLI REPL application.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from android_gemini_agent.adb.mock_client import MockAdbClient
from android_gemini_agent.adb.models import ConnectionResult, DeviceState, PairingResult
from android_gemini_agent.cli.app import AndroidAgentCLI, main
from android_gemini_agent.cli.console import (
    action_spinner,
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
from android_gemini_agent.config import Settings
from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser


@pytest.fixture
def mock_console() -> Console:
    """Fixture providing a test Console that records all output to a string buffer."""
    return Console(record=True, width=120, file=io.StringIO())


@pytest.fixture
def sample_hierarchy() -> UIHierarchy:
    """Fixture providing a sample parsed UI hierarchy."""
    elem1 = UIElement(
        elem_id=1,
        node_class="android.widget.TextView",
        element_type="Text",
        resource_id="com.android.settings:id/title",
        text="Network & internet",
        content_desc="",
        package="com.android.settings",
        bounds=BoundingBox(50, 100, 500, 180),
        center=(275, 140),
        clickable=True,
        scrollable=False,
        focusable=True,
    )
    elem2 = UIElement(
        elem_id=2,
        node_class="android.widget.EditText",
        element_type="Input",
        resource_id="com.android.settings:id/search_src_text",
        text="Search settings",
        content_desc="Search query",
        package="com.android.settings",
        bounds=BoundingBox(100, 200, 800, 280),
        center=(450, 240),
        clickable=True,
        scrollable=False,
        focusable=True,
    )
    elem3 = UIElement(
        elem_id=3,
        node_class="android.widget.ScrollView",
        element_type="ScrollView",
        resource_id="com.android.settings:id/main_content",
        text="",
        content_desc="",
        package="com.android.settings",
        bounds=BoundingBox(0, 300, 1080, 2200),
        center=(540, 1250),
        clickable=False,
        scrollable=True,
        focusable=False,
    )
    return UIHierarchy(elements=[elem1, elem2, elem3], screen_size=(1080, 2400))


class TestConsoleUtilities:
    """Tests all visual Rich console renderers, tables, spinners, and panels."""

    def test_render_banner(self, mock_console: Console):
        """Verifies banner formatting, device serial display, model, and badges."""
        render_banner(
            device_serial="192.168.1.50:5555",
            model_name="gemini-2.5-flash",
            connected=True,
            api_key_set=True,
            target_console=mock_console,
        )
        out = mock_console.export_text()
        assert "Android Gemini Automation Agent" in out
        assert "192.168.1.50:5555" in out
        assert "CONNECTED" in out
        assert "gemini-2.5-flash" in out
        assert "CONFIGURED" in out

    def test_render_banner_disconnected_missing_key(self, mock_console: Console):
        """Verifies banner when disconnected and API key is missing."""
        render_banner(
            device_serial="192.168.1.100:5555",
            model_name="gemini-2.5-flash",
            connected=False,
            api_key_set=False,
            target_console=mock_console,
        )
        out = mock_console.export_text()
        assert "DISCONNECTED" in out
        assert "NOT SET" in out

    def test_thinking_and_action_spinners(self, mock_console: Console):
        """Tests that spinner context managers execute and exit without raising errors."""
        with thinking_spinner("Thinking about next tap...", target_console=mock_console):
            pass

        with action_spinner("Tapping coordinates...", target_console=mock_console):
            pass

    def test_render_step_card(self, mock_console: Console):
        """Verifies step card rendering with syntax-highlighted arguments, summary, and latency."""
        render_step_card(
            step_num=3,
            total_steps=20,
            tool_name="type_text",
            tool_args={"text": "Dark Theme", "clear_first": True, "press_enter": True},
            summary="Entered search text",
            duration_ms=145.8,
            target_console=mock_console,
        )
        out = mock_console.export_text()
        assert "Step 3/20" in out
        assert "type_text" in out
        assert "Dark Theme" in out
        assert "Entered search text" in out
        assert "145.8 ms" in out

    def test_render_ui_table(self, mock_console: Console, sample_hierarchy: UIHierarchy):
        """Verifies UI table elements, columns, flags, and center coordinates."""
        render_ui_table(sample_hierarchy, target_console=mock_console)
        out = mock_console.export_text()
        assert "Visible Screen Hierarchy" in out
        assert "Network & internet" in out
        assert "Search settings" in out
        assert "EditText" in out
        assert "(275, 140)" in out  # Center of (50, 100, 500, 180) -> (275, 140)
        assert "C" in out  # Clickable flag

    def test_render_outcome_panel_success(self, mock_console: Console):
        """Verifies success outcome panel styling and data."""
        render_outcome_panel(
            status="SUCCESS",
            message="Dark mode enabled successfully",
            total_steps=4,
            duration_seconds=3.45,
            target_console=mock_console,
        )
        out = mock_console.export_text()
        assert "TASK SUCCESS" in out
        assert "Dark mode enabled successfully" in out
        assert "4" in out
        assert "3.45 seconds" in out

    def test_render_outcome_panel_failure(self, mock_console: Console):
        """Verifies failure outcome panel styling."""
        render_outcome_panel(
            status="FAILURE",
            message="Target toggle button not found on screen",
            total_steps=10,
            duration_seconds=12.8,
            target_console=mock_console,
        )
        out = mock_console.export_text()
        assert "TASK FAILURE" in out
        assert "Target toggle button not found" in out

    def test_render_status_panel(self, mock_console: Console):
        """Verifies status panel information."""
        render_status_panel(
            device_serial="192.168.1.80:5555",
            device_state="connected",
            model_name="gemini-2.5-flash",
            api_key_configured=True,
            settings_dict={"max_agent_steps": 20, "action_delay_seconds": 1.0},
            target_console=mock_console,
        )
        out = mock_console.export_text()
        assert "SYSTEM STATUS" in out
        assert "192.168.1.80:5555" in out
        assert "CONNECTED (Online)" in out

    def test_render_settings_table(self, mock_console: Console):
        """Verifies settings table rendering and API key masking."""
        settings = {
            "gemini_api_key": "test_gemini_dummy_api_key_123456",
            "gemini_model": "gemini-2.5-flash",
            "max_agent_steps": 20,
        }
        render_settings_table(settings, target_console=mock_console)
        out = mock_console.export_text()
        assert "Active Runtime Configuration" in out
        assert "gemini-2.5-flash" in out
        assert "test_g...3456" in out  # Masked API key

    def test_render_help_panel(self, mock_console: Console):
        """Verifies help command table."""
        render_help_panel(target_console=mock_console)
        out = mock_console.export_text()
        assert "Available Commands" in out
        assert "connect [ip:port]" in out
        assert "pair <ip:port> <code>" in out
        assert "dump_ui" in out
        assert "run <task>" in out
        assert "exit / quit" in out

    def test_render_info_success_warning_error(self, mock_console: Console):
        """Verifies message log helpers."""
        render_info("Information message", target_console=mock_console)
        render_success("Operation completed", target_console=mock_console)
        render_warning("Device battery low", target_console=mock_console)
        render_error("Connection timed out", target_console=mock_console)

        out = mock_console.export_text()
        assert "Information message" in out
        assert "Operation completed" in out
        assert "Device battery low" in out
        assert "Connection timed out" in out


class TestAndroidAgentCLI:
    """Tests the AndroidAgentCLI command handlers, REPL dispatcher, and execution loop."""

    @pytest.fixture
    def mock_adb(self, settings_xml: str) -> MockAdbClient:
        """Provides a MockAdbClient with loaded settings fixture."""
        client = MockAdbClient()
        client.set_fixture("settings", settings_xml)
        client.switch_fixture("settings")
        return client

    @pytest.fixture
    def cli_app(self, mock_adb: MockAdbClient, mock_console: Console) -> AndroidAgentCLI:
        """Provides an AndroidAgentCLI instance initialized with mock ADB client and test console."""
        config = Settings(
            gemini_api_key="test_gemini_dummy_api_key_123456",
            gemini_model="gemini-2.5-flash",
            adb_device_ip="192.168.1.100",
            adb_device_port=5555,
            max_agent_steps=10,
        )
        cli = AndroidAgentCLI(
            adb_manager=mock_adb,
            config=config,
            console=mock_console,
        )
        return cli

    def test_cli_initialization(self, cli_app: AndroidAgentCLI):
        """Tests that CLI initializes default properties correctly."""
        assert cli_app.target_serial == "192.168.1.100:5555"
        assert cli_app.controller is not None
        assert cli_app.config.gemini_model == "gemini-2.5-flash"

    def test_handle_connect_success(self, cli_app: AndroidAgentCLI, mock_adb: MockAdbClient):
        """Tests successful connection handler."""
        success = cli_app.handle_connect("192.168.1.50:41253")
        assert success is True
        assert cli_app.target_serial == "192.168.1.50:41253"
        assert cli_app.config.adb_device_ip == "192.168.1.50"
        assert cli_app.config.adb_device_port == 41253
        assert mock_adb.get_state("192.168.1.50:41253") == DeviceState.CONNECTED

    def test_handle_connect_default_args(self, cli_app: AndroidAgentCLI, mock_adb: MockAdbClient):
        """Tests connection handler with omitted arguments defaulting to config."""
        success = cli_app.handle_connect(None)
        assert success is True
        assert cli_app.target_serial == "192.168.1.100:5555"
        assert mock_adb.get_state("192.168.1.100:5555") == DeviceState.CONNECTED

    def test_handle_connect_failure(self, cli_app: AndroidAgentCLI, mock_adb: MockAdbClient, mock_console: Console):
        """Tests handling of connection failure."""
        mock_adb.connect = MagicMock(return_value=ConnectionResult(success=False, message="Connection refused"))
        success = cli_app.handle_connect("192.168.1.99:5555")
        assert success is False
        out = mock_console.export_text()
        assert "Failed to connect" in out
        assert "Troubleshooting tips" in out

    def test_handle_pair_success(self, cli_app: AndroidAgentCLI, mock_adb: MockAdbClient, mock_console: Console):
        """Tests successful device pairing."""
        success = cli_app.handle_pair("192.168.1.100:38912 654321")
        assert success is True
        out = mock_console.export_text()
        assert "successfully paired" in out
        assert "Important Next Step" in out

    def test_handle_pair_missing_args(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests pairing with missing arguments."""
        success1 = cli_app.handle_pair("")
        assert success1 is False

        success2 = cli_app.handle_pair("192.168.1.100:38912")  # Missing code
        assert success2 is False
        out = mock_console.export_text()
        assert "Both target IP:Port and Pairing Code are required" in out

    def test_handle_pair_failure(self, cli_app: AndroidAgentCLI, mock_adb: MockAdbClient, mock_console: Console):
        """Tests handling of pairing failure."""
        mock_adb.pair = MagicMock(return_value=PairingResult(success=False, message="Wrong code"))
        success = cli_app.handle_pair("192.168.1.100:38912 000000")
        assert success is False
        out = mock_console.export_text()
        assert "Pairing failed: Wrong code" in out

    def test_handle_status(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests status handler."""
        cli_app.handle_status()
        out = mock_console.export_text()
        assert "SYSTEM STATUS" in out
        assert "192.168.1.100:5555" in out

    def test_handle_dump_ui(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests dumping and formatting screen UI."""
        cli_app.handle_connect("192.168.1.100:5555")
        hierarchy = cli_app.handle_dump_ui()
        assert hierarchy is not None
        assert len(hierarchy.elements) > 0
        out = mock_console.export_text()
        assert "Visible Screen Hierarchy" in out

    def test_handle_settings_view_and_update(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests settings display and runtime updating."""
        # View settings
        cli_app.handle_settings()
        out1 = mock_console.export_text()
        assert "Active Runtime Configuration" in out1

        # Update valid setting
        cli_app.handle_settings("max_agent_steps=35")
        assert cli_app.config.max_agent_steps == 35

        # Update invalid setting format
        cli_app.handle_settings("invalid_syntax_no_equals")
        out2 = mock_console.export_text()
        assert "Invalid settings format" in out2

        # Update unknown key
        cli_app.handle_settings("unknown_setting_key=100")
        out3 = mock_console.export_text()
        assert "Failed to update setting" in out3

    def test_handle_help(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests help handler."""
        cli_app.handle_help()
        out = mock_console.export_text()
        assert "Available Commands" in out
        assert "connect" in out
        assert "pair" in out

    def test_run_command_dispatcher(self, cli_app: AndroidAgentCLI):
        """Tests run_command verb dispatching and termination signals."""
        assert cli_app.run_command("") is True
        assert cli_app.run_command("help") is True
        assert cli_app.run_command("status") is True
        assert cli_app.run_command("settings") is True
        assert cli_app.run_command("dump_ui") is True
        assert cli_app.run_command("connect 192.168.1.100:5555") is True
        assert cli_app.run_command("pair 192.168.1.100:38912 123456") is True

        # Test exit commands return False
        assert cli_app.run_command("exit") is False
        assert cli_app.run_command("quit") is False
        assert cli_app.run_command("q") is False

    def test_run_task_with_mock_engine(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests running a task with a configured mock engine."""
        mock_engine = MagicMock()
        mock_engine.run_task.return_value = {
            "status": "SUCCESS",
            "message": "Task completed successfully",
            "steps": [
                {"step": 1, "tool": "tap", "args": {"x": 540, "y": 960}, "summary": "Tapped item"},
                {"step": 2, "tool": "finish_task", "args": {"status": "SUCCESS", "message": "Done"}, "summary": "Finished"},
            ],
            "step_count": 2,
        }
        cli_app.engine = mock_engine
        cli_app.handle_connect("192.168.1.100:5555")

        result = cli_app.handle_run_task("Open Display Settings")
        assert result["status"] == "SUCCESS"
        assert result["step_count"] == 2

        out = mock_console.export_text()
        assert "TASK SUCCESS" in out
        assert "Task completed successfully" in out

    def test_run_task_empty_prompt(self, cli_app: AndroidAgentCLI):
        """Tests that empty task descriptions return failure immediately."""
        res = cli_app.handle_run_task("   ")
        assert res["status"] == "FAILURE"
        assert "Empty task description" in res["message"]

    def test_run_task_unconfigured_api_key(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests running a task when GEMINI_API_KEY is not configured."""
        cli_app.config.gemini_api_key = ""
        cli_app.engine = None
        cli_app.handle_connect("192.168.1.100:5555")

        res = cli_app.handle_run_task("Do something")
        assert res["status"] == "FAILURE"
        assert "Missing GEMINI_API_KEY" in res["message"]
        out = mock_console.export_text()
        assert "GEMINI_API_KEY is not configured" in out

    def test_run_task_keyboard_interrupt_safe_handling(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests that Ctrl+C during task execution aborts gracefully without crashing."""
        mock_engine = MagicMock()
        mock_engine.run_task.side_effect = KeyboardInterrupt("User pressed Ctrl+C")
        cli_app.engine = mock_engine
        cli_app.handle_connect("192.168.1.100:5555")

        res = cli_app.handle_run_task("Long running task")
        assert res["status"] == "FAILURE"
        assert "Aborted by user" in res["message"]

        out = mock_console.export_text()
        assert "interrupted by user (Ctrl+C)" in out
        assert "TASK FAILURE" in out

    def test_natural_language_fallback(self, cli_app: AndroidAgentCLI):
        """Tests that arbitrary text not matching a command is dispatched as a task."""
        mock_engine = MagicMock()
        mock_engine.run_task.return_value = {"status": "SUCCESS", "message": "Done", "steps": []}
        cli_app.engine = mock_engine
        cli_app.handle_connect("192.168.1.100:5555")

        # Command without 'run' prefix
        cli_app.run_command("Open Chrome and search for Gemini")
        mock_engine.run_task.assert_called_once()
        assert "Open Chrome and search for Gemini" in mock_engine.run_task.call_args[0][0]

    def test_repl_loop_execution_and_exit(self, cli_app: AndroidAgentCLI):
        """Tests the interactive REPL loop reading inputs and terminating on 'exit'."""
        user_inputs = ["help", "status", "exit"]

        with patch("rich.prompt.Prompt.ask", side_effect=user_inputs):
            cli_app.run_repl()

    def test_repl_loop_ctrl_c_at_prompt(self, cli_app: AndroidAgentCLI, mock_console: Console):
        """Tests that pressing Ctrl+C at the REPL prompt displays a hint and stays in REPL."""
        # 1st prompt: KeyboardInterrupt, 2nd prompt: exit
        with patch("rich.prompt.Prompt.ask", side_effect=[KeyboardInterrupt(), "exit"]):
            cli_app.run_repl()

        # Check console output
        # (Rich console attached to cli_app is mock_console)

    def test_main_entrypoint_flags(self, mock_adb: MockAdbClient):
        """Tests CLI argument parsing via main() entrypoint."""
        with patch("android_gemini_agent.cli.app.RealAdbClient", return_value=mock_adb):
            # Test --status flag
            assert main(["--status"]) == 0

            # Test --pair flag
            assert main(["--pair", "192.168.1.100:38912", "123456"]) == 0

            # Test --dump-ui flag
            mock_adb.connect("192.168.1.100", 5555)
            assert main(["--connect", "192.168.1.100:5555", "--dump-ui"]) == 0
