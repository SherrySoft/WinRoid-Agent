"""
Unit & Integration Tests for Agent Tools, Schemas, Execution Dispatcher, and Models.
Validates google-genai FunctionDeclaration schemas, parameter enforcement, DeviceController
dispatch mapping, and dataclass models.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from google.genai import types

from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.agent.models import (
    ActionRecord,
    AgentStep,
    LoopDetectionResult,
    TaskResult,
)
from android_gemini_agent.agent.tools import execute_tool, get_agent_tools


class TestAgentToolDeclarations:
    """Tests for Tool declarations generated for Google GenAI."""

    def test_get_agent_tools_structure(self):
        tools = get_agent_tools()
        assert isinstance(tools, list)
        assert len(tools) == 1
        assert isinstance(tools[0], types.Tool)

        funcs = tools[0].function_declarations
        assert len(funcs) == 6

        func_names = {f.name for f in funcs}
        assert func_names == {
            "tap",
            "type_text",
            "press_key",
            "swipe",
            "wait",
            "finish_task",
        }

    def test_tap_function_schema(self):
        tools = get_agent_tools()
        tap_decl = next(f for f in tools[0].function_declarations if f.name == "tap")
        assert tap_decl.description is not None
        assert "x" in tap_decl.parameters.properties
        assert "y" in tap_decl.parameters.properties
        assert set(tap_decl.parameters.required) == {"x", "y"}

    def test_type_text_function_schema(self):
        tools = get_agent_tools()
        decl = next(f for f in tools[0].function_declarations if f.name == "type_text")
        assert "text" in decl.parameters.properties
        assert "clear_first" in decl.parameters.properties
        assert "press_enter" in decl.parameters.properties
        assert decl.parameters.required == ["text"]

    def test_press_key_function_schema(self):
        tools = get_agent_tools()
        decl = next(f for f in tools[0].function_declarations if f.name == "press_key")
        assert "key_name" in decl.parameters.properties
        assert decl.parameters.required == ["key_name"]
        enums = decl.parameters.properties["key_name"].enum
        assert "BACK" in enums
        assert "HOME" in enums
        assert "APP_SWITCH" in enums
        assert "ENTER" in enums
        assert "DELETE" in enums

    def test_swipe_function_schema(self):
        tools = get_agent_tools()
        decl = next(f for f in tools[0].function_declarations if f.name == "swipe")
        assert "direction" in decl.parameters.properties
        assert "distance" in decl.parameters.properties
        assert decl.parameters.required == ["direction"]
        assert set(decl.parameters.properties["direction"].enum) == {
            "up",
            "down",
            "left",
            "right",
        }
        assert set(decl.parameters.properties["distance"].enum) == {
            "short",
            "normal",
            "long",
        }

    def test_wait_function_schema(self):
        tools = get_agent_tools()
        decl = next(f for f in tools[0].function_declarations if f.name == "wait")
        assert "seconds" in decl.parameters.properties
        assert decl.parameters.required == ["seconds"]

    def test_finish_task_function_schema(self):
        tools = get_agent_tools()
        decl = next(f for f in tools[0].function_declarations if f.name == "finish_task")
        assert "status" in decl.parameters.properties
        assert "message" in decl.parameters.properties
        assert set(decl.parameters.required) == {"status", "message"}
        assert set(decl.parameters.properties["status"].enum) == {"SUCCESS", "FAILURE"}


class TestToolExecutionDispatcher:
    """Tests for execute_tool mapping tool calls to DeviceController methods."""

    @pytest.fixture
    def mock_controller(self) -> MagicMock:
        controller = MagicMock(spec=DeviceController)
        controller.tap.return_value = True
        controller.type_text.return_value = True
        controller.press_key.return_value = True
        controller.scroll.return_value = True
        controller.wait.return_value = None
        return controller

    def test_execute_tap_success(self, mock_controller: MagicMock):
        ok, summary = execute_tool(mock_controller, "tap", {"x": 540, "y": 1200})
        assert ok is True
        assert "540" in summary and "1200" in summary
        mock_controller.tap.assert_called_once_with(540, 1200)

    def test_execute_tap_failure(self, mock_controller: MagicMock):
        mock_controller.tap.return_value = False
        ok, summary = execute_tool(mock_controller, "tap", {"x": 100, "y": 200})
        assert ok is False
        assert "Failed to tap" in summary

    def test_execute_type_text_basic(self, mock_controller: MagicMock):
        ok, summary = execute_tool(mock_controller, "type_text", {"text": "hello"})
        assert ok is True
        assert "Typed 'hello'" in summary
        mock_controller.type_text.assert_called_once_with(
            "hello", clear_first=False, press_enter=False
        )

    def test_execute_type_text_options(self, mock_controller: MagicMock):
        ok, summary = execute_tool(
            mock_controller,
            "type_text",
            {"text": "Search Query", "clear_first": True, "press_enter": True},
        )
        assert ok is True
        assert "Search Query" in summary
        assert "cleared" in summary
        assert "enter" in summary
        mock_controller.type_text.assert_called_once_with(
            "Search Query", clear_first=True, press_enter=True
        )

    def test_execute_press_key_standard(self, mock_controller: MagicMock):
        ok, summary = execute_tool(mock_controller, "press_key", {"key_name": "BACK"})
        assert ok is True
        assert "BACK" in summary
        mock_controller.press_key.assert_called_once_with("BACK")

    def test_execute_press_key_delete_normalization(self, mock_controller: MagicMock):
        ok, summary = execute_tool(mock_controller, "press_key", {"key_name": "DELETE"})
        assert ok is True
        mock_controller.press_key.assert_called_once_with("DEL")

    def test_execute_swipe_distances(self, mock_controller: MagicMock):
        # Short distance
        ok, _ = execute_tool(
            mock_controller, "swipe", {"direction": "up", "distance": "short"}
        )
        assert ok is True
        mock_controller.scroll.assert_called_with("up", distance_ratio=0.25)

        # Normal distance
        ok, _ = execute_tool(
            mock_controller, "swipe", {"direction": "down", "distance": "normal"}
        )
        assert ok is True
        mock_controller.scroll.assert_called_with("down", distance_ratio=0.5)

        # Long distance
        ok, _ = execute_tool(
            mock_controller, "swipe", {"direction": "left", "distance": "long"}
        )
        assert ok is True
        mock_controller.scroll.assert_called_with("left", distance_ratio=0.75)

    def test_execute_wait(self, mock_controller: MagicMock):
        ok, summary = execute_tool(mock_controller, "wait", {"seconds": 2.5})
        assert ok is True
        assert "2.5s" in summary
        mock_controller.wait.assert_called_once_with(2.5)

    def test_execute_finish_task(self, mock_controller: MagicMock):
        ok, summary = execute_tool(
            mock_controller,
            "finish_task",
            {"status": "SUCCESS", "message": "Objective completed."},
        )
        assert ok is True
        assert "SUCCESS" in summary
        assert "Objective completed." in summary

    def test_execute_unknown_tool(self, mock_controller: MagicMock):
        ok, summary = execute_tool(mock_controller, "non_existent_tool", {})
        assert ok is False
        assert "Unknown tool" in summary

    def test_execute_tool_exception_handling(self, mock_controller: MagicMock):
        mock_controller.tap.side_effect = RuntimeError("ADB socket disconnected")
        ok, summary = execute_tool(mock_controller, "tap", {"x": 500, "y": 500})
        assert ok is False
        assert "RuntimeError" in summary


class TestAgentDataModels:
    """Tests for AgentStep, TaskResult, ActionRecord, and LoopDetectionResult."""

    def test_agent_step_creation_and_dict_access(self):
        step = AgentStep(
            step_number=1,
            tool_name="tap",
            tool_args={"x": 100, "y": 200},
            thought="Tapping the search button",
            tool_result="Tapped at (100, 200)",
            latency_ms=120.5,
            screen_state_hash="abc123hash",
        )
        assert step.step_number == 1
        assert step["step"] == 1
        assert step["tool"] == "tap"
        assert step["args"] == {"x": 100, "y": 200}
        assert step["result"] == "Tapped at (100, 200)"
        assert "tap(x=100, y=200)" in step.summary_str()

        d = step.to_dict()
        assert d["step_number"] == 1
        assert d["status"] == "EXECUTED"

    def test_task_result_properties_and_access(self):
        step1 = AgentStep(step_number=1, tool_name="tap", tool_args={"x": 50, "y": 50})
        step2 = AgentStep(
            step_number=2,
            tool_name="finish_task",
            tool_args={"status": "SUCCESS", "message": "Done"},
        )
        res = TaskResult(
            task="Test Goal",
            status="SUCCESS",
            message="Completed successfully",
            steps=[step1, step2],
            total_duration_seconds=3.5,
            token_usage={"total_tokens": 1200},
        )

        assert res.is_success is True
        assert res.step_count == 2
        assert res.duration_seconds == 3.5
        assert res["status"] == "SUCCESS"
        assert res["message"] == "Completed successfully"
        assert res["step_count"] == 2
        assert len(res["steps"]) == 2

    def test_action_record_signature(self):
        rec1 = ActionRecord(
            step_number=1,
            tool_name="tap",
            tool_args={"y": 200, "x": 100},
        )
        rec2 = ActionRecord(
            step_number=2,
            tool_name="tap",
            tool_args={"x": 100, "y": 200},
        )
        # Signature must sort dictionary keys deterministically
        assert rec1.signature == rec2.signature

    def test_loop_detection_result_dict_access(self):
        ldr = LoopDetectionResult(
            detected=True,
            tier=1,
            reason="Repetition detected",
            warning_level=1,
            should_abort=False,
            injection_prompt="Please stop repeating.",
        )
        assert ldr["detected"] is True
        assert ldr["tier"] == 1
        assert ldr["reason"] == "Repetition detected"
        assert ldr["should_abort"] is False
        assert ldr["injection_prompt"] == "Please stop repeating."
