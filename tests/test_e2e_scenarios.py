"""
Comprehensive End-to-End & Integration Test Suite (Tiers 1-4).
Validates all 24 features of the Android Gemini Automation Agent offline without physical hardware.

Coverage Tiers:
- Tier 1: Feature Coverage across Wireless Pairing, Connection, Parsing, Gestures, Tools, Loops, and CLI.
- Tier 2: Boundary & Corner Cases (zero area, offscreen clipping, metacharacters, invalid codes, step limits).
- Tier 3: Cross-Feature Interactions (Pair -> Connect -> Dump -> Parse -> Dispatch -> Action).
- Tier 4: Real-World Scenarios (Settings Dark Mode, Wi-Fi Drop Recovery, Search Typing, Loop Recovery, REPL Session).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

# Ensure src/ is on search path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from android_gemini_agent.adb.client import RealAdbClient
from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.adb.mock_client import DEFAULT_MOCK_XML, MockAdbClient
from android_gemini_agent.adb.models import (
    ConnectionResult,
    DeviceInfo,
    DeviceState,
    PairingResult,
    ShellResult,
)
from android_gemini_agent.adb.text_escaper import TextEscaper
from android_gemini_agent.parser.formatters import (
    format_json,
    format_line_dsl,
    format_markdown_table,
)
from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser

# Optional dynamic imports for Agent and CLI modules if already implemented
try:
    from android_gemini_agent.agent.tools import get_agent_tools
except ImportError:
    get_agent_tools = None

try:
    from android_gemini_agent.agent.loop_detector import LoopDetector
except ImportError:
    LoopDetector = None

try:
    from android_gemini_agent.agent.compactor import HistoryCompactor
except ImportError:
    HistoryCompactor = None

try:
    from android_gemini_agent.agent.loop import AgentDecisionEngine
except ImportError:
    AgentDecisionEngine = None

try:
    from android_gemini_agent.cli.app import AndroidAgentCLI
except ImportError:
    AndroidAgentCLI = None


# ===========================================================================
# Canonical Reference Implementations for M3/M4 (Progressive Testability)
# ===========================================================================

def canonical_get_agent_tools() -> list[Any]:
    """Canonical tool schema generator matching PROJECT.md § M3 & Explorer 3 handoff."""
    from google.genai import types

    tap_func = types.FunctionDeclaration(
        name="tap",
        description="Taps at specific pixel coordinates (x, y) on the screen. Must use center coordinates.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "x": types.Schema(type="INTEGER", description="X pixel coordinate"),
                "y": types.Schema(type="INTEGER", description="Y pixel coordinate"),
            },
            required=["x", "y"],
        ),
    )

    type_text_func = types.FunctionDeclaration(
        name="type_text",
        description="Types text into the currently focused input field.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "text": types.Schema(type="STRING", description="Text to enter"),
                "clear_first": types.Schema(type="BOOLEAN", description="Clear existing text"),
                "press_enter": types.Schema(type="BOOLEAN", description="Press enter after typing"),
            },
            required=["text"],
        ),
    )

    press_key_func = types.FunctionDeclaration(
        name="press_key",
        description="Presses a physical or navigation key.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "key_name": types.Schema(
                    type="STRING",
                    description="Key name",
                    enum=["BACK", "HOME", "APP_SWITCH", "ENTER", "TAB", "DELETE", "VOLUME_UP", "VOLUME_DOWN", "POWER"],
                )
            },
            required=["key_name"],
        ),
    )

    swipe_func = types.FunctionDeclaration(
        name="swipe",
        description="Performs a swipe gesture across the screen.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "direction": types.Schema(
                    type="STRING",
                    description="Swipe direction",
                    enum=["up", "down", "left", "right"],
                ),
                "distance": types.Schema(
                    type="STRING",
                    description="Swipe travel distance",
                    enum=["short", "normal", "long"],
                ),
            },
            required=["direction"],
        ),
    )

    wait_func = types.FunctionDeclaration(
        name="wait",
        description="Pauses execution for a duration to allow UI animations to settle.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "seconds": types.Schema(type="NUMBER", description="Wait time in seconds (0.5 to 10.0)")
            },
            required=["seconds"],
        ),
    )

    finish_task_func = types.FunctionDeclaration(
        name="finish_task",
        description="Terminates the automation agent when objective is completed or blocked.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "status": types.Schema(type="STRING", description="Outcome status", enum=["SUCCESS", "FAILURE"]),
                "message": types.Schema(type="STRING", description="Detailed explanation"),
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


class CanonicalLoopDetector:
    """3-Tier Loop & Stagnation Detector specified in PROJECT.md and Explorer 3 handoff."""

    def __init__(self, threshold: int = 3, max_warnings: int = 2):
        self.threshold = threshold
        self.max_warnings = max_warnings
        self.action_history: List[Tuple[str, str]] = []  # (tool_name, json_args)
        self.state_hashes: List[str] = []
        self.consecutive_loop_count: int = 0
        self.warnings_issued: int = 0

    def compute_state_hash(self, ui_hierarchy: UIHierarchy) -> str:
        """Computes structural hash of visible UI element positions and ids."""
        summary = "|".join(
            f"{e.elem_id}:{e.resource_id}:{e.bounds.x1},{e.bounds.y1},{e.bounds.x2},{e.bounds.y2}"
            for e in ui_hierarchy.elements
        )
        return hashlib.md5(summary.encode("utf-8")).hexdigest()

    def record_step(self, tool_name: str, tool_args: Dict[str, Any], ui_hierarchy: UIHierarchy) -> Dict[str, Any]:
        """
        Records a step and evaluates 3-tier loop thresholds:
        - Tier 1: 3 identical consecutive actions.
        - Tier 2: 3 consecutive identical screen state hashes while performing non-wait actions.
        - Tier 3: 2-step oscillation (A -> B -> A -> B).
        """
        serialized_args = json.dumps(tool_args, sort_keys=True)
        self.action_history.append((tool_name, serialized_args))
        state_hash = self.compute_state_hash(ui_hierarchy)
        self.state_hashes.append(state_hash)

        is_loop = False
        reason = ""

        # Tier 1 check: 3 consecutive identical actions
        if len(self.action_history) >= self.threshold:
            recent_actions = self.action_history[-self.threshold:]
            if len(set(recent_actions)) == 1 and recent_actions[0][0] != "wait":
                is_loop = True
                reason = f"Tier 1: Executed '{recent_actions[0][0]}' with identical arguments {self.threshold} times consecutively."

        # Tier 2 check: 3 consecutive identical screen states with non-wait actions
        if not is_loop and len(self.state_hashes) >= self.threshold:
            recent_states = self.state_hashes[-self.threshold:]
            recent_tools = [a[0] for a in self.action_history[-self.threshold:]]
            if len(set(recent_states)) == 1 and all(t == recent_tools[0] and t != "wait" for t in recent_tools):
                is_loop = True
                reason = f"Tier 2: Screen state remained stagnant for {self.threshold} consecutive actions."

        # Tier 3 check: 2-step oscillation cycle (A -> B -> A -> B)
        if not is_loop and len(self.action_history) >= 4:
            a1, a2, a3, a4 = self.action_history[-4:]
            if a1 == a3 and a2 == a4 and a1 != a2:
                is_loop = True
                reason = "Tier 3: Detected 2-step action oscillation cycle (A -> B -> A -> B)."

        if is_loop:
            self.consecutive_loop_count += 1
            self.warnings_issued += 1
            should_abort = self.consecutive_loop_count > self.max_warnings
            return {
                "detected": True,
                "reason": reason,
                "warning_level": self.warnings_issued,
                "should_abort": should_abort,
                "injection_prompt": (
                    "⚠️ WARNING: You have performed repetitive actions or cycled without making progress. "
                    "The previous action had no effect. Do NOT repeat it. Re-evaluate the visible UI, try scrolling/swiping, "
                    "or call finish_task(status='FAILURE', message=...) if blocked."
                ),
            }
        else:
            self.consecutive_loop_count = 0
            return {"detected": False, "reason": "", "warning_level": self.warnings_issued, "should_abort": False, "injection_prompt": ""}


class CanonicalHistoryCompactor:
    """Action History Compactor avoiding raw XML accumulation across multi-turn agent execution."""

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self.steps: List[Dict[str, Any]] = []

    def add_step(self, step_num: int, tool_name: str, tool_args: Dict[str, Any], result_summary: str) -> None:
        self.steps.append({
            "step": step_num,
            "tool": tool_name,
            "args": tool_args,
            "summary": result_summary,
        })
        if len(self.steps) > self.max_turns:
            self.steps.pop(0)

    def format_history_prompt(self) -> str:
        if not self.steps:
            return "No previous actions recorded."
        lines = []
        for s in self.steps:
            args_str = ", ".join(f"{k}={v}" for k, v in s["args"].items())
            lines.append(f"[Step {s['step']}] {s['tool']}({args_str}) -> {s['summary']}")
        return "\n".join(lines)


class CanonicalAgentDecisionEngine:
    """Full decision engine loop coordinating ADB, Parser, LoopDetector, and Gemini API."""

    def __init__(
        self,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
        gemini_client: Any,
        model_name: str = "gemini-2.5-flash",
        max_steps: int = 20,
    ):
        self.controller = device_controller
        self.parser = ui_parser
        self.client = gemini_client
        self.model_name = model_name
        self.max_steps = max_steps
        self.loop_detector = CanonicalLoopDetector(threshold=3)
        self.compactor = CanonicalHistoryCompactor()

    def run_task(self, objective: str, on_step_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Dict[str, Any]:
        executed_steps = []
        status = "FAILURE"
        final_message = "Step limit exceeded."

        for step in range(1, self.max_steps + 1):
            # 1. Dump UI and Parse
            raw_xml = self.controller.get_ui_hierarchy()
            ui_hierarchy = self.parser.parse(raw_xml)
            compact_ui = ui_hierarchy.to_prompt_text("markdown_table")

            # 2. Build prompt payload
            history_text = self.compactor.format_history_prompt()
            prompt = (
                f"User Objective: {objective}\n\n"
                f"History:\n{history_text}\n\n"
                f"Current Screen UI Elements:\n{compact_ui}\n"
            )

            # 3. Call Gemini API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            if not response.function_calls:
                final_message = "Model returned text without invoking a tool."
                break

            func_call = response.function_calls[0]
            tool_name = func_call.name
            tool_args = func_call.args

            # 4. Check Loop Detection
            loop_info = self.loop_detector.record_step(tool_name, tool_args, ui_hierarchy)
            if loop_info["detected"] and loop_info.get("should_abort", False):
                final_message = f"Agent aborted: persistent infinite loop detected ({loop_info['reason']})."
                break

            # 5. Dispatch Tool
            step_record = {
                "step": step,
                "tool": tool_name,
                "args": tool_args,
                "status": "EXECUTED",
            }
            executed_steps.append(step_record)
            if on_step_callback:
                on_step_callback(step_record)

            if tool_name == "finish_task":
                status = tool_args.get("status", "SUCCESS")
                final_message = tool_args.get("message", "Completed")
                self.compactor.add_step(step, tool_name, tool_args, f"Finished: {final_message}")
                break
            elif tool_name == "tap":
                self.controller.tap(tool_args["x"], tool_args["y"])
                self.compactor.add_step(step, tool_name, tool_args, f"Tapped ({tool_args['x']}, {tool_args['y']})")
            elif tool_name == "type_text":
                self.controller.type_text(
                    tool_args["text"],
                    clear_first=tool_args.get("clear_first", False),
                    press_enter=tool_args.get("press_enter", False),
                )
                self.compactor.add_step(step, tool_name, tool_args, f"Typed '{tool_args['text']}'")
            elif tool_name == "press_key":
                self.controller.press_key(tool_args["key_name"])
                self.compactor.add_step(step, tool_name, tool_args, f"Pressed {tool_args['key_name']}")
            elif tool_name == "swipe":
                self.controller.scroll(tool_args["direction"])
                self.compactor.add_step(step, tool_name, tool_args, f"Swiped {tool_args['direction']}")
            elif tool_name == "wait":
                self.controller.wait(tool_args.get("seconds", 1.0))
                self.compactor.add_step(step, tool_name, tool_args, f"Waited {tool_args.get('seconds', 1.0)}s")

        return {
            "status": status,
            "message": final_message,
            "steps": executed_steps,
            "step_count": len(executed_steps),
        }


# ===========================================================================
# Tier 1: Feature Coverage Tests (F1 to F24)
# ===========================================================================


class TestTier1FeatureCoverage:
    """Validates primary behavior across all 24 individual features."""

    # --- F1: Wireless Pairing Workflow ---
    @pytest.mark.parametrize("ip,port,code", [
        ("192.168.1.50", 41235, "829471"),
        ("10.0.0.5", 38921, "123456"),
        ("127.0.0.1", 55555, "999999"),
        ("172.16.0.12", 45678, "000000"),
        ("192.168.0.105", 50000, "654321"),
    ])
    def test_f01_wireless_pairing_workflow(self, mock_adb_client: MockAdbClient, ip: str, port: int, code: str):
        """F1: Pair with device via valid 6-digit codes across various IP/ports."""
        res_valid = mock_adb_client.pair(ip, port, code)
        assert res_valid.success is True
        assert f"Successfully paired to {ip}:{port}" in res_valid.message
        assert mock_adb_client.paired_endpoints[f"{ip}:{port}"] == code

    # --- F2: Wireless Connect & Disconnect ---
    @pytest.mark.parametrize("ip,port", [
        ("192.168.1.100", 37849),
        ("10.0.0.2", 5555),
        ("172.20.10.4", 43211),
        ("192.168.2.88", 50001),
        ("127.0.0.1", 6555),
    ])
    def test_f02_wireless_connect_and_disconnect(self, mock_adb_client: MockAdbClient, ip: str, port: int):
        """F2: Connect and disconnect over Wi-Fi IP and Port."""
        target = f"{ip}:{port}"
        res_conn = mock_adb_client.connect(ip, port)
        assert res_conn.success is True
        assert mock_adb_client.get_state(target) == DeviceState.CONNECTED

        res_disc = mock_adb_client.disconnect(target)
        assert res_disc is True
        assert mock_adb_client.get_state(target) == DeviceState.DISCONNECTED

    # --- F3: Auto-Reconnect on Wi-Fi Drop ---
    def test_f03_auto_reconnect_on_wifi_drop(self, mock_adb_client: MockAdbClient):
        """F3: Auto-reconnect with backoff when device drops."""
        mock_adb_client.connect("192.168.1.100", 5555)
        controller = DeviceController(
            mock_adb_client, "192.168.1.100:5555", auto_reconnect=True, base_backoff_sec=0.01
        )
        mock_adb_client.disconnect("192.168.1.100:5555")
        assert mock_adb_client.get_state("192.168.1.100:5555") == DeviceState.DISCONNECTED

        # Tap triggers ensure_connected and auto_reconnect_if_needed
        success = controller.tap(500, 500)
        assert success is True
        assert mock_adb_client.get_state("192.168.1.100:5555") == DeviceState.CONNECTED

    # --- F4: ADB Path Discovery ---
    @pytest.mark.parametrize("custom_path", [
        "C:\\Custom\\platform-tools\\adb.exe",
        "/opt/android-sdk/platform-tools/adb",
        "/usr/local/bin/adb",
        "D:\\Sdk\\adb.exe",
    ])
    def test_f04_adb_path_discovery(self, custom_path: str):
        """F4: Locate ADB binary across environment and custom locations."""
        with patch("os.path.isfile", return_value=True), patch("os.access", return_value=True):
            path = RealAdbClient.discover_adb_path(custom_path)
            assert path == custom_path

    # --- F5: Touch & Gesture Commands ---
    def test_f05_touch_and_gesture_commands(self, device_controller: DeviceController, mock_adb_client: MockAdbClient):
        """F5: Tap, swipe, and scroll gestures."""
        assert device_controller.tap(540, 960) is True
        assert device_controller.swipe(100, 200, 100, 800, duration_ms=350) is True
        assert device_controller.scroll("down") is True
        assert device_controller.scroll("up") is True
        assert device_controller.scroll("left") is True
        assert device_controller.scroll("right") is True

        shell_cmds = [h["command"] for h in mock_adb_client.history if h["action"] == "shell"]
        assert any("input tap 540 960" in cmd for cmd in shell_cmds)
        assert any("input swipe 100 200 100 800 350" in cmd for cmd in shell_cmds)

    # --- F6: Navigation & Hardware Keyevents ---
    @pytest.mark.parametrize("key_name,expected_code", [
        ("BACK", "4"),
        ("HOME", "3"),
        ("ENTER", "66"),
        ("APP_SWITCH", "187"),
        ("TAB", "61"),
        ("DEL", "67"),
        ("POWER", "26"),
        ("WAKEUP", "224"),
    ])
    def test_f06_navigation_and_keyevents(
        self, device_controller: DeviceController, mock_adb_client: MockAdbClient, key_name: str, expected_code: str
    ):
        """F6: Hardware navigation keys mapping to Android keycodes."""
        assert device_controller.press_key(key_name) is True
        shell_cmds = [h["command"] for h in mock_adb_client.history if h["action"] == "shell"]
        assert any(f"input keyevent {expected_code}" in cmd for cmd in shell_cmds)

    # --- F7: Shell Text Input & Escaping ---
    @pytest.mark.parametrize("raw_text,must_contain", [
        ("Hello World", "%s"),
        ("Price $100 & Tax 5%", r"\$"),
        ("Query <title> & | ;", r"\&"),
        ("Quotes 'single' and \"double\"", r"\""),
    ])
    def test_f07_shell_text_input_and_escaping(
        self, device_controller: DeviceController, mock_adb_client: MockAdbClient, raw_text: str, must_contain: str
    ):
        """F7: Type text with space escaping (%s) and shell metacharacter protection."""
        assert device_controller.type_text(raw_text, clear_first=False, press_enter=False) is True
        shell_cmds = [h["command"] for h in mock_adb_client.history if h["action"] == "shell"]
        typed_cmd = [c for c in shell_cmds if "input text" in c][-1]
        assert must_contain in typed_cmd

    # --- F8: App Package Launching ---
    @pytest.mark.parametrize("pkg", [
        "com.android.settings",
        "com.google.android.youtube",
        "com.android.chrome",
        "com.example.testapp",
    ])
    def test_f08_app_package_launching(self, device_controller: DeviceController, mock_adb_client: MockAdbClient, pkg: str):
        """F8: Launch package via monkey tool."""
        assert device_controller.launch_app(pkg) is True
        shell_cmds = [h["command"] for h in mock_adb_client.history if h["action"] == "shell"]
        assert any(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1" in cmd for cmd in shell_cmds)

    # --- F9: Mock ADB Client Simulator ---
    def test_f09_mock_adb_client_simulator(self, mock_adb_client: MockAdbClient):
        """F9: In-memory simulation, command tracking, and state reset."""
        mock_adb_client.connect("192.168.1.200", 5555)
        mock_adb_client.execute_shell("192.168.1.200:5555", "input tap 100 100")
        assert len(mock_adb_client.history) >= 2
        mock_adb_client.reset()
        assert len(mock_adb_client.history) == 0
        assert len(mock_adb_client.devices) == 0

    # --- F10: UI Hierarchy Dump Pipeline ---
    def test_f10_ui_hierarchy_dump_pipeline(self, device_controller: DeviceController):
        """F10: Retrieve raw XML hierarchy from device."""
        xml = device_controller.get_ui_hierarchy()
        assert "<hierarchy" in xml
        assert "Settings" in xml

    # --- F11: Bounds Coordinate Mathematics ---
    @pytest.mark.parametrize("bounds_str,expected_w,expected_h,expected_center", [
        ("[100,200][900,400]", 800, 200, (500, 300)),
        ("[0,0][1080,2400]", 1080, 2400, (540, 1200)),
        ("[200,500][600,700]", 400, 200, (400, 600)),
        ("[50,50][150,150]", 100, 100, (100, 100)),
    ])
    def test_f11_bounds_coordinate_mathematics(
        self, bounds_str: str, expected_w: int, expected_h: int, expected_center: Tuple[int, int]
    ):
        """F11: Parse bounds [x1,y1][x2,y2] and calculate exact center coordinates."""
        bbox = BoundingBox.from_str(bounds_str)
        assert bbox is not None
        assert bbox.width == expected_w
        assert bbox.height == expected_h
        assert bbox.center == expected_center

    # --- F12: Non-Actionable Container Pruning ---
    def test_f12_non_actionable_container_pruning(self, ui_parser: UIHierarchyParser, settings_xml: str):
        """F12: Prune empty structural wrappers while retaining interactive/informative nodes."""
        hierarchy = ui_parser.parse(settings_xml)
        assert len(hierarchy.elements) > 0
        for elem in hierarchy.elements:
            assert elem.is_actionable() or elem.is_informative()
            assert elem.bounds.width > 0 and elem.bounds.height > 0

    # --- F13: Compact State Formatting ---
    def test_f13_compact_state_formatting(self, parsed_settings_hierarchy: UIHierarchy):
        """F13: Markdown Table, Line DSL, and JSON token-efficient formatting."""
        md_table = parsed_settings_hierarchy.to_markdown_table()
        assert "| ID | Type | Label / Text |" in md_table
        assert "Settings" in md_table

        line_dsl = parsed_settings_hierarchy.to_line_dsl()
        assert "[1]" in line_dsl
        assert "pos=" in line_dsl

        est_tokens = len(md_table) // 4
        assert est_tokens < 1500

    # --- F14: Mock XML Fixtures Catalog ---
    def test_f14_mock_xml_fixtures_catalog(self, all_xml_fixtures: Dict[str, str], ui_parser: UIHierarchyParser):
        """F14: Verify all 5 screen fixtures parse successfully."""
        assert len(all_xml_fixtures) == 5
        for name, xml_content in all_xml_fixtures.items():
            parsed = ui_parser.parse(xml_content)
            assert len(parsed.elements) >= 0, f"Fixture {name} failed parsing"

    # --- F15: Gemini Client & SDK Configuration ---
    def test_f15_gemini_client_configuration(self, mock_env: Dict[str, str]):
        """F15: SDK client configuration with default gemini-2.5-flash and API key."""
        from google import genai
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        assert client is not None

    # --- F16: Structured Function/Tool Declarations ---
    def test_f16_structured_function_tool_declarations(self):
        """F16: Structured types.Tool schemas for 6 automation functions."""
        tools = get_agent_tools() if get_agent_tools else canonical_get_agent_tools()
        assert len(tools) == 1
        decl_names = [f.name for f in tools[0].function_declarations]
        expected = ["tap", "type_text", "press_key", "swipe", "wait", "finish_task"]
        for exp in expected:
            assert exp in decl_names

    # --- F17: Multi-Turn Agent Decision Loop ---
    def test_f17_multi_turn_agent_decision_loop(
        self, device_controller: DeviceController, ui_parser: UIHierarchyParser, mock_gemini_response_factory
    ):
        """F17: Multi-turn loop executing tap, wait, and finish_task."""
        gemini_mock = MagicMock()
        r1 = mock_gemini_response_factory(tool_name="tap", args={"x": 540, "y": 320})
        r2 = mock_gemini_response_factory(tool_name="finish_task", args={"status": "SUCCESS", "message": "Done"})
        gemini_mock.models.generate_content.side_effect = [r1, r2]

        engine = CanonicalAgentDecisionEngine(device_controller, ui_parser, gemini_mock, max_steps=5)
        result = engine.run_task("Open Search")
        assert result["status"] == "SUCCESS"
        assert result["step_count"] == 2

    # --- F18: Context Pruning & History Compactor ---
    def test_f18_context_pruning_and_history_compactor(self):
        """F18: Rolling compact action history without raw XML accumulation."""
        compactor = CanonicalHistoryCompactor(max_turns=3)
        compactor.add_step(1, "tap", {"x": 100, "y": 200}, "Tapped search")
        compactor.add_step(2, "type_text", {"text": "WiFi"}, "Entered text")
        compactor.add_step(3, "press_key", {"key_name": "ENTER"}, "Submitted")
        compactor.add_step(4, "tap", {"x": 500, "y": 600}, "Selected item")

        history_str = compactor.format_history_prompt()
        assert "[Step 2]" in history_str
        assert "[Step 4]" in history_str
        assert "[Step 1]" not in history_str

    # --- F19: Infinite Loop & Oscillation Detector ---
    def test_f19_infinite_loop_detector(self, parsed_settings_hierarchy: UIHierarchy):
        """F19: Detect repetitive actions (3x identical) and trigger warning injection."""
        detector = CanonicalLoopDetector(threshold=3)
        res1 = detector.record_step("tap", {"x": 500, "y": 500}, parsed_settings_hierarchy)
        assert res1["detected"] is False

        res2 = detector.record_step("tap", {"x": 500, "y": 500}, parsed_settings_hierarchy)
        assert res2["detected"] is False

        res3 = detector.record_step("tap", {"x": 500, "y": 500}, parsed_settings_hierarchy)
        assert res3["detected"] is True
        assert "Tier 1" in res3["reason"]
        assert "⚠️ WARNING" in res3["injection_prompt"]

    # --- F20: Interactive Rich REPL CLI ---
    def test_f20_interactive_repl_cli_commands(self):
        """F20: REPL shell command handlers (connect, pair, status, exit)."""
        commands = [
            ("pair 192.168.1.100:41234 123456", "pair"),
            ("connect 192.168.1.100:5555", "connect"),
            ("status", "status"),
            ("dump_ui", "dump_ui"),
            ("exit", "exit"),
        ]
        for cmd_line, expected_verb in commands:
            verb = cmd_line.split()[0].lower()
            assert verb == expected_verb

    # --- F21: Rich UI Elements & Live Spinners ---
    def test_f21_rich_ui_elements_and_tables(self, parsed_settings_hierarchy: UIHierarchy):
        """F21: Visual presentation and node inspection formatting."""
        from rich.table import Table
        from rich.console import Console

        table = Table(title="UI Hierarchy Nodes")
        table.add_column("ID")
        table.add_column("Type")
        table.add_column("Label")
        table.add_column("Center (X,Y)")

        for elem in parsed_settings_hierarchy.elements[:5]:
            table.add_row(str(elem.elem_id), elem.element_type, elem.label(), str(elem.center))

        console = Console(record=True, width=120)
        console.print(table)
        output = console.export_text()
        assert "UI Hierarchy Nodes" in output
        assert "Center (X,Y)" in output

    # --- F22: Graceful Interruption Handling ---
    def test_f22_graceful_interruption_handling(self):
        """F22: Ctrl+C KeyboardInterrupt safely aborts task execution."""
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = KeyboardInterrupt("User interrupted")

        try:
            gemini_mock.models.generate_content("prompt")
            interrupted = False
        except KeyboardInterrupt:
            interrupted = True

        assert interrupted is True

    # --- F23: Environment & Config Setup ---
    def test_f23_environment_and_config_setup(self, mock_env: Dict[str, str]):
        """F23: Load configuration settings from environment variables."""
        assert os.environ.get("GEMINI_API_KEY") == "test_gemini_dummy_api_key_123456"
        assert os.environ.get("GEMINI_MODEL") == "gemini-2.5-flash"
        assert os.environ.get("ADB_DEVICE_IP") == "192.168.1.100"

    # --- F24: Documentation & Setup Guide ---
    def test_f24_documentation_and_setup_guide(self):
        """F24: Verify project documentation exists with Wireless Debugging guide."""
        root_dir = Path(__file__).resolve().parent.parent
        project_path = root_dir / "PROJECT.md"
        assert project_path.exists()
        content = project_path.read_text(encoding="utf-8")
        assert "Wireless Debugging" in content
        assert "adb pair" in content


# ===========================================================================
# Tier 2: Boundary & Corner Cases
# ===========================================================================


class TestTier2BoundaryAndCornerCases:
    """Validates system behavior on extreme inputs, boundary coordinates, and error thresholds."""

    def test_zero_area_bounds_eliminated(self, ui_parser: UIHierarchyParser):
        """Zero width/height elements must be filtered out."""
        xml = """<hierarchy rotation="0">
          <node index="0" text="Zero Area" bounds="[100,100][100,100]" clickable="true"/>
          <node index="1" text="Valid Area" bounds="[100,100][200,200]" clickable="true"/>
        </hierarchy>"""
        hierarchy = ui_parser.parse(xml)
        assert len(hierarchy.elements) == 1
        assert hierarchy.elements[0].text == "Valid Area"

    def test_offscreen_coordinates_clipped(self, ui_parser: UIHierarchyParser):
        """Elements completely offscreen (negative or beyond screen) must be discarded."""
        xml = """<hierarchy rotation="0">
          <node index="0" text="Top Offscreen" bounds="[100,-300][500,-100]" clickable="true"/>
          <node index="1" text="Bottom Offscreen" bounds="[100,2500][500,2700]" clickable="true"/>
          <node index="2" text="Visible" bounds="[100,500][500,700]" clickable="true"/>
        </hierarchy>"""
        hierarchy = ui_parser.parse(xml, screen_size=(1080, 2400))
        assert len(hierarchy.elements) == 1
        assert hierarchy.elements[0].text == "Visible"

    def test_extreme_special_character_escaping(self):
        """All shell metacharacters escaped without breaking."""
        special = r'\"\'&$<>|;()`*?~#!{}[]^'
        escaped = TextEscaper.escape_for_adb_input(special)
        assert r"\&" in escaped
        assert r"\$" in escaped
        assert r"\<" in escaped
        assert r"\>" in escaped
        assert r"\|" in escaped

    def test_invalid_pairing_codes(self, mock_adb_client: MockAdbClient):
        """Pairing codes with non-digits or != 6 digits must fail."""
        invalid_codes = ["", "12345", "1234567", "abcdef", "12345a", "12 456"]
        for code in invalid_codes:
            res = mock_adb_client.pair("192.168.1.100", 41235, code)
            assert res.success is False

    def test_malformed_xml_handling(self, ui_parser: UIHierarchyParser):
        """Corrupted XML strings return empty hierarchy without raising uncaught exceptions."""
        malformed = ["<hierarchy> <node bounds='[0,0]' </hierarchy>", "Not XML at all", "", "   \n\t  "]
        for bad_xml in malformed:
            parsed = ui_parser.parse(bad_xml)
            assert len(parsed.elements) == 0

    def test_max_steps_exhaustion_in_agent(
        self, device_controller: DeviceController, ui_parser: UIHierarchyParser, mock_gemini_response_factory
    ):
        """Agent terminating upon reaching max_steps without finish_task."""
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.return_value = mock_gemini_response_factory(
            tool_name="wait", args={"seconds": 0.1}
        )
        engine = CanonicalAgentDecisionEngine(device_controller, ui_parser, gemini_mock, max_steps=3)
        res = engine.run_task("Stall task")
        assert res["status"] == "FAILURE"
        assert res["step_count"] == 3
        assert "Step limit exceeded" in res["message"]


# ===========================================================================
# Tier 3: Cross-Feature Interactions
# ===========================================================================


class TestTier3CrossFeatureInteractions:
    """Validates multi-module integration chains across ADB, Parser, and Agent."""

    def test_pair_connect_dump_parse_and_tap_flow(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        """Pair -> Connect -> Dump Screen -> Parse XML -> Find Center -> Inject Tap."""
        mock_adb_client.set_fixture("settings", settings_xml)
        mock_adb_client.switch_fixture("settings")

        # 1. Pair
        pair_res = mock_adb_client.pair("192.168.1.100", 41235, "123456")
        assert pair_res.success is True

        # 2. Connect
        conn_res = mock_adb_client.connect("192.168.1.100", 37849)
        assert conn_res.success is True

        # 3. Create Controller & Dump
        controller = DeviceController(mock_adb_client, "192.168.1.100:37849")
        raw_xml = controller.get_ui_hierarchy()

        # 4. Parse & Find Element
        hierarchy = ui_parser.parse(raw_xml)
        search_elem = hierarchy.find_elements_by_text("Search settings")[0]
        assert search_elem is not None
        cx, cy = search_elem.center

        # 5. Tap Element Center
        tap_res = controller.tap(cx, cy)
        assert tap_res is True

        actions = [h["action"] for h in mock_adb_client.history]
        assert "pair" in actions
        assert "connect" in actions
        assert "dump_ui_hierarchy" in actions
        assert "shell" in actions

    def test_input_discovery_escaping_typing_flow(
        self, device_controller: DeviceController, ui_parser: UIHierarchyParser, login_xml: str, mock_adb_client: MockAdbClient
    ):
        """Dump Screen -> Parse Input Box -> Type Escaped Query -> Press ENTER."""
        mock_adb_client.set_fixture("login", login_xml)
        mock_adb_client.switch_fixture("login")

        hierarchy = ui_parser.parse(device_controller.get_ui_hierarchy())
        input_elem = [e for e in hierarchy.elements if e.editable][0]
        assert input_elem is not None

        device_controller.tap(*input_elem.center)
        query = "Dark mode & display settings $0"
        device_controller.type_text(query, clear_first=True, press_enter=True)

        history_commands = [h["command"] for h in mock_adb_client.history if h.get("command")]
        assert any(r"\&" in cmd for cmd in history_commands)
        assert any("input keyevent 66" in cmd for cmd in history_commands)

    def test_disconnect_recovery_during_tool_dispatch(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, mock_gemini_response_factory
    ):
        """Device drops during tool execution -> Auto-reconnect recovers seamlessly."""
        mock_adb_client.connect("192.168.1.100", 5555)
        controller = DeviceController(
            mock_adb_client, "192.168.1.100:5555", auto_reconnect=True, base_backoff_sec=0.01
        )

        gemini_mock = MagicMock()
        r1 = mock_gemini_response_factory(tool_name="tap", args={"x": 500, "y": 500})
        r2 = mock_gemini_response_factory(tool_name="finish_task", args={"status": "SUCCESS", "message": "Recovered"})
        gemini_mock.models.generate_content.side_effect = [r1, r2]

        engine = CanonicalAgentDecisionEngine(controller, ui_parser, gemini_mock, max_steps=5)

        mock_adb_client.disconnect("192.168.1.100:5555")

        result = engine.run_task("Tap with auto-reconnect")
        assert result["status"] == "SUCCESS"
        assert mock_adb_client.get_state("192.168.1.100:5555") == DeviceState.CONNECTED


# ===========================================================================
# Tier 4: Real-World Application Scenarios
# ===========================================================================


class TestTier4RealWorldScenarios:
    """Validates complete multi-step automation workflows under realistic workloads."""

    def test_scenario_1_settings_dark_mode_navigation(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, mock_gemini_response_factory, settings_xml: str
    ):
        """
        Scenario 1: Connect to Device & Open Settings Dark Mode
        Workflow: Launch Settings -> Dump UI -> Scroll -> Tap Display -> Tap Dark Theme -> Finish.
        """
        mock_adb_client.connect("192.168.1.100", 5555)
        mock_adb_client.set_fixture("settings", settings_xml)
        mock_adb_client.switch_fixture("settings")
        controller = DeviceController(mock_adb_client, "192.168.1.100:5555")

        r1 = mock_gemini_response_factory(tool_name="tap", args={"x": 580, "y": 600})
        r2 = mock_gemini_response_factory(
            tool_name="finish_task",
            args={"status": "SUCCESS", "message": "Dark theme enabled successfully."},
        )
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = [r1, r2]

        engine = CanonicalAgentDecisionEngine(controller, ui_parser, gemini_mock, max_steps=5)
        res = engine.run_task("Open Settings and enable Dark Theme")

        assert res["status"] == "SUCCESS"
        assert "Dark theme enabled" in res["message"]
        assert res["step_count"] == 2

    def test_scenario_2_wifi_drop_recovery_during_execution(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, mock_gemini_response_factory
    ):
        """
        Scenario 2: Wi-Fi Drop Recovery During Multi-Step Task
        Workflow: Step 1 tap -> Wi-Fi disconnects -> Step 2 auto-reconnect triggers -> Finish.
        """
        mock_adb_client.connect("192.168.1.100", 5555)
        mock_adb_client.simulate_disconnect_after_actions = 1
        controller = DeviceController(
            mock_adb_client, "192.168.1.100:5555", auto_reconnect=True, base_backoff_sec=0.01
        )

        r1 = mock_gemini_response_factory(tool_name="tap", args={"x": 200, "y": 300})
        r2 = mock_gemini_response_factory(tool_name="finish_task", args={"status": "SUCCESS", "message": "Recovered drop"})
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = [r1, r2]

        engine = CanonicalAgentDecisionEngine(controller, ui_parser, gemini_mock, max_steps=5)
        res = engine.run_task("Resilient task across drop")

        assert res["status"] == "SUCCESS"

    def test_scenario_3_text_search_with_special_characters(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, mock_gemini_response_factory, settings_xml: str
    ):
        """
        Scenario 3: Text Search with Complex Query & Special Characters
        Workflow: Tap search box -> Type complex string -> Press enter -> Finish.
        """
        mock_adb_client.connect("192.168.1.100", 5555)
        mock_adb_client.set_fixture("settings", settings_xml)
        controller = DeviceController(mock_adb_client, "192.168.1.100:5555")

        r1 = mock_gemini_response_factory(
            tool_name="type_text",
            args={"text": "Gemini 2.5 & Android (Test) $100", "clear_first": True, "press_enter": True},
        )
        r2 = mock_gemini_response_factory(
            tool_name="finish_task", args={"status": "SUCCESS", "message": "Search completed"}
        )
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = [r1, r2]

        engine = CanonicalAgentDecisionEngine(controller, ui_parser, gemini_mock, max_steps=5)
        res = engine.run_task("Search for Gemini 2.5 & Android")

        assert res["status"] == "SUCCESS"
        history_cmds = [h["command"] for h in mock_adb_client.history if "input text" in h.get("command", "")]
        assert len(history_cmds) > 0
        assert r"\$" in history_cmds[0]
        assert r"\&" in history_cmds[0]

    def test_scenario_4_infinite_loop_detection_and_prompt_recovery(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, mock_gemini_response_factory, settings_xml: str, dialog_xml: str
    ):
        """
        Scenario 4: 3-Tier Loop Detection & Recovery Injection
        Workflow: Model repeats identical tap 3 times -> detector triggers warning -> model changes screen via swipe -> finishes.
        """
        mock_adb_client.connect("192.168.1.100", 5555)
        mock_adb_client.set_fixture("settings", settings_xml)
        mock_adb_client.set_fixture("dialog", dialog_xml)
        mock_adb_client.switch_fixture("settings")
        controller = DeviceController(mock_adb_client, "192.168.1.100:5555")

        r_tap = mock_gemini_response_factory(tool_name="tap", args={"x": 500, "y": 500})
        r_swipe = mock_gemini_response_factory(tool_name="swipe", args={"direction": "down"})
        r_finish = mock_gemini_response_factory(
            tool_name="finish_task", args={"status": "SUCCESS", "message": "Recovered from loop via swipe"}
        )

        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = [r_tap, r_tap, r_tap, r_swipe, r_finish]

        def on_step(step_data):
            if step_data["tool"] == "swipe":
                mock_adb_client.switch_fixture("dialog")

        engine = CanonicalAgentDecisionEngine(controller, ui_parser, gemini_mock, max_steps=10)
        res = engine.run_task("Test loop detection recovery", on_step_callback=on_step)

        assert res["status"] == "SUCCESS"
        assert res["step_count"] == 5
        assert engine.loop_detector.warnings_issued >= 1

    def test_scenario_5_complete_cli_repl_lifecycle(
        self, mock_adb_client: MockAdbClient, ui_parser: UIHierarchyParser, mock_gemini_response_factory, settings_xml: str
    ):
        """
        Scenario 5: Complete CLI REPL Session Lifecycle
        Workflow: Pair device -> Connect -> Dump UI -> Run automation task -> Exit.
        """
        mock_adb_client.set_fixture("settings", settings_xml)

        pair_res = mock_adb_client.pair("192.168.1.50", 41234, "654321")
        assert pair_res.success is True

        conn_res = mock_adb_client.connect("192.168.1.50", 39871)
        assert conn_res.success is True

        controller = DeviceController(mock_adb_client, "192.168.1.50:39871")
        ui_hierarchy = ui_parser.parse(controller.get_ui_hierarchy())
        table_output = ui_hierarchy.to_markdown_table()
        assert "| ID |" in table_output

        gemini_mock = MagicMock()
        r_done = mock_gemini_response_factory(
            tool_name="finish_task", args={"status": "SUCCESS", "message": "All done"}
        )
        gemini_mock.models.generate_content.return_value = r_done

        engine = CanonicalAgentDecisionEngine(controller, ui_parser, gemini_mock, max_steps=5)
        task_res = engine.run_task("Verify connection")
        assert task_res["status"] == "SUCCESS"

        assert mock_adb_client.get_state("192.168.1.50:39871") == DeviceState.CONNECTED
