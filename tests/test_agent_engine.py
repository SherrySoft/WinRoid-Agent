"""
Unit & Integration Tests for Gemini Agent Decision Engine and Context Compactor.
Validates multi-turn tool calling loop, history compaction, token budget enforcement,
loop recovery injections, step callbacks, step limits, and exception resilience.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from google.genai import types

from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.adb.mock_client import MockAdbClient
from android_gemini_agent.agent.compactor import ContextCompactor, HistoryCompactor
from android_gemini_agent.agent.loop import AgentDecisionEngine
from android_gemini_agent.agent.models import AgentStep, TaskResult
from android_gemini_agent.parser.parser import UIHierarchyParser


class TestHistoryCompactor:
    """Tests for HistoryCompactor and prompt builder."""

    def test_empty_history(self):
        compactor = HistoryCompactor(max_turns=5)
        assert compactor.format_history_prompt() == "No previous actions recorded."

    def test_add_steps_and_compaction(self):
        compactor = HistoryCompactor(max_turns=3)
        compactor.add_step(1, "tap", {"x": 100, "y": 200}, "Tapped search")
        compactor.add_step(2, "type_text", {"text": "WiFi"}, "Typed 'WiFi'")
        compactor.add_step(3, "press_key", {"key_name": "ENTER"}, "Pressed ENTER")
        compactor.add_step(4, "tap", {"x": 500, "y": 600}, "Selected WiFi network")

        formatted = compactor.format_history_prompt()
        assert "[Step 2]" in formatted
        assert "[Step 3]" in formatted
        assert "[Step 4]" in formatted
        assert "[Step 1]" not in formatted  # Pruned due to max_turns=3

    def test_build_turn_prompt_structure(
        self, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        hierarchy = ui_parser.parse(settings_xml)
        compactor = HistoryCompactor(max_turns=5)
        compactor.add_step(1, "tap", {"x": 100, "y": 100}, "Tapped menu")

        prompt = compactor.build_turn_prompt(
            objective="Turn on Bluetooth",
            ui_hierarchy=hierarchy,
            recovery_prompt="⚠️ Avoid repeating previous action",
        )

        assert "User Objective: Turn on Bluetooth" in prompt
        assert "Action History:" in prompt
        assert "[Step 1] tap(x=100, y=100)" in prompt
        assert "Current Screen State (UI Elements):" in prompt
        assert "| ID | Type |" in prompt
        assert "Recovery Guidance:" in prompt
        assert "Avoid repeating" in prompt

    def test_turn_prompt_token_budget(
        self, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        hierarchy = ui_parser.parse(settings_xml)
        compactor = HistoryCompactor(max_turns=5)
        for i in range(1, 5):
            compactor.add_step(i, "tap", {"x": i * 10, "y": i * 20}, f"Tapped {i}")

        prompt = compactor.build_turn_prompt(
            objective="Navigate to Display and enable Dark Theme",
            ui_hierarchy=hierarchy,
        )
        tokens = compactor.estimate_prompt_tokens(prompt)
        assert tokens < 1500, f"Prompt token estimate {tokens} exceeds 1,500 token ceiling"


class TestAgentDecisionEngine:
    """Tests for AgentDecisionEngine multi-turn execution loop."""

    def test_single_turn_finish_task_success(
        self,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
        mock_gemini_response_factory,
    ):
        r_finish = mock_gemini_response_factory(
            tool_name="finish_task",
            args={"status": "SUCCESS", "message": "Objective accomplished immediately."},
            text="I see the screen is already in the desired state.",
        )
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.return_value = r_finish

        engine = AgentDecisionEngine(
            device_controller=device_controller,
            ui_parser=ui_parser,
            gemini_client=gemini_mock,
            max_steps=5,
        )

        res = engine.run_task("Verify Screen State")

        assert res.is_success is True
        assert res.status == "SUCCESS"
        assert res.step_count == 1
        assert "Objective accomplished" in res.message
        assert res.steps[0].thought == "I see the screen is already in the desired state."
        assert res.steps[0].tool_name == "finish_task"

    def test_multi_turn_task_execution(
        self,
        mock_adb_client: MockAdbClient,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
        mock_gemini_response_factory,
        settings_xml: str,
        dialog_xml: str,
    ):
        mock_adb_client.set_fixture("settings", settings_xml)
        mock_adb_client.set_fixture("dialog", dialog_xml)

        r1 = mock_gemini_response_factory(tool_name="tap", args={"x": 540, "y": 300})
        r2 = mock_gemini_response_factory(
            tool_name="type_text", args={"text": "Dark Mode", "press_enter": True}
        )
        r3 = mock_gemini_response_factory(
            tool_name="finish_task",
            args={"status": "SUCCESS", "message": "Dark Mode enabled successfully."},
        )

        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = [r1, r2, r3]

        steps_recorded: List[AgentStep] = []

        def on_step(step: AgentStep):
            steps_recorded.append(step)

        engine = AgentDecisionEngine(
            device_controller=device_controller,
            ui_parser=ui_parser,
            gemini_client=gemini_mock,
            max_steps=5,
        )

        res = engine.run_task("Enable Dark Mode", on_step_callback=on_step)

        assert res.is_success is True
        assert res.step_count == 3
        assert len(steps_recorded) == 3
        assert steps_recorded[0].tool_name == "tap"
        assert steps_recorded[1].tool_name == "type_text"
        assert steps_recorded[2].tool_name == "finish_task"
        assert res.token_usage["prompt_tokens"] > 0

    def test_step_limit_exhaustion(
        self,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
        mock_gemini_response_factory,
    ):
        r_tap = mock_gemini_response_factory(tool_name="swipe", args={"direction": "up"})
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.return_value = r_tap

        engine = AgentDecisionEngine(
            device_controller=device_controller,
            ui_parser=ui_parser,
            gemini_client=gemini_mock,
            max_steps=3,
        )

        res = engine.run_task("Infinite Swipe Task")

        assert res.is_success is False
        assert res.status == "FAILURE"
        assert res.step_count == 3
        assert "Step limit exceeded" in res.message

    def test_model_returns_text_without_tool(
        self,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
        mock_gemini_response_factory,
    ):
        r_text_only = mock_gemini_response_factory(
            tool_name=None,
            text="I cannot do this task because there is no button.",
        )
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.return_value = r_text_only

        engine = AgentDecisionEngine(
            device_controller=device_controller,
            ui_parser=ui_parser,
            gemini_client=gemini_mock,
            max_steps=5,
        )

        res = engine.run_task("Unachievable Task")

        assert res.is_success is False
        assert res.status == "FAILURE"
        assert "Model returned text without invoking a tool" in res.message
        assert res.step_count == 1
        assert res.steps[0].status == "FAILED"

    def test_persistent_loop_triggers_abort(
        self,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
        mock_gemini_response_factory,
    ):
        # Repetitive tap action with no state change
        r_tap = mock_gemini_response_factory(tool_name="tap", args={"x": 100, "y": 100})
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.return_value = r_tap

        engine = AgentDecisionEngine(
            device_controller=device_controller,
            ui_parser=ui_parser,
            gemini_client=gemini_mock,
            max_steps=10,
            loop_threshold=3,
        )
        # Configure detector to abort after 1 consecutive warning
        engine.loop_detector.max_warnings = 1

        res = engine.run_task("Stuck in loop")

        assert res.is_success is False
        assert res.status == "FAILURE"
        assert "persistent infinite loop detected" in res.message
        assert engine.loop_detector.warnings_issued >= 1

    def test_keyboard_interrupt_graceful_handling(
        self,
        device_controller: DeviceController,
        ui_parser: UIHierarchyParser,
    ):
        gemini_mock = MagicMock()
        gemini_mock.models.generate_content.side_effect = KeyboardInterrupt()

        engine = AgentDecisionEngine(
            device_controller=device_controller,
            ui_parser=ui_parser,
            gemini_client=gemini_mock,
            max_steps=5,
        )

        res = engine.run_task("Interruptible Task")

        assert res.is_success is False
        assert res.status == "FAILURE"
        assert "SIGINT" in res.message or "interrupted" in res.message.lower()
