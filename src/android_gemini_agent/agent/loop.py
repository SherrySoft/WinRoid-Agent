"""
Gemini Autonomous Agent Decision Loop Engine.
Coordinates UI hierarchy extraction, prompt compaction, structured tool calling via Google GenAI SDK,
infinite loop & stagnation detection, and deterministic tool execution on Android devices.
"""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

from google.genai import types

from .compactor import HistoryCompactor
from .loop_detector import LoopDetector
from .models import AgentStep, TaskResult
from .tools import execute_tool, get_agent_tools
from ..parser.models import UIHierarchy

if TYPE_CHECKING:
    from ..adb.controller import DeviceController
    from ..parser.parser import UIHierarchyParser

logger = logging.getLogger(__name__)


class AgentDecisionEngine:
    """
    Main Autonomous Agent Decision Loop.
    Executes multi-turn tool-calling automation tasks using Gemini 2.5 Flash and ADB UI hierarchy extraction.
    """

    def __init__(
        self,
        device_controller: Any,
        ui_parser: Optional[Any] = None,
        gemini_client: Any = None,
        model_name: str = "gemini-3.5-flash-lite",
        max_steps: int = 20,
        loop_threshold: int = 3,
        max_history_turns: int = 10,
        action_delay: float = 0.0,
    ):
        self.controller = device_controller
        self.parser = ui_parser
        self.client = gemini_client
        self.model_name = model_name
        self.max_steps = max_steps
        self.action_delay = max(0.0, action_delay)
        self.platform = "windows" if hasattr(device_controller, "hotkey") and not hasattr(device_controller, "adb") else "android"

        self.loop_detector = LoopDetector(threshold=loop_threshold)
        self.compactor = HistoryCompactor(max_turns=max_history_turns)

    def _call_gemini_with_retry(
        self,
        prompt: str,
        config: Optional[Any] = None,
        max_retries: int = 3,
    ) -> Any:
        """
        Calls Gemini API with automatic 429 quota exhaustion retry & model fallback.
        """
        fallback_models = [self.model_name, "gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]
        seen_models = []
        for m in fallback_models:
            if m not in seen_models:
                seen_models.append(m)

        for attempt in range(max_retries):
            current_model = seen_models[attempt % len(seen_models)]
            try:
                if config is not None:
                    try:
                        return self.client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                            config=config,
                        )
                    except (TypeError, AttributeError):
                        return self.client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                        )
                else:
                    return self.client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                    )
            except Exception as exc:
                exc_str = str(exc)
                is_rate_limit = ("429" in exc_str) or ("RESOURCE_EXHAUSTED" in exc_str) or ("Quota exceeded" in exc_str)
                if is_rate_limit and attempt < max_retries - 1:
                    delay = 5.0
                    m_delay = re.search(r"retry in (\d+(?:\.\d+)?)s", exc_str, re.IGNORECASE)
                    if m_delay:
                        delay = min(30.0, float(m_delay.group(1)) + 1.0)
                    else:
                        m_delay2 = re.search(r"'retryDelay':\s*'(\d+)s'", exc_str)
                        if m_delay2:
                            delay = min(30.0, float(m_delay2.group(1)) + 1.0)
                        else:
                            delay = 5.0 * (attempt + 1)

                    logger.warning(
                        f"429 Rate limit hit on {current_model}. Pausing {delay:.1f}s before retry (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(delay)
                    continue
                raise

    def run_task(
        self,
        task: str,
        on_step_callback: Optional[Callable[[Union[AgentStep, Dict[str, Any]]], None]] = None,
    ) -> TaskResult:
        """
        Executes an autonomous automation task to completion or termination.

        Args:
            task: Natural language description of the objective (e.g. 'Open Settings and enable Dark Mode').
            on_step_callback: Optional callback invoked after each executed step with the AgentStep instance.

        Returns:
            TaskResult containing final status, summary message, executed steps, duration, and token usage.
        """
        start_time = time.time()
        executed_steps: List[AgentStep] = []
        token_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "candidate_tokens": 0,
            "total_tokens": 0,
        }

        status = "FAILURE"
        final_message = "Step limit exceeded before objective completion."
        recovery_prompt = ""

        # Reset state trackers for fresh task run
        self.loop_detector.reset()
        self.compactor.reset()

        try:
            for step_idx in range(1, self.max_steps + 1):
                t_step_start = time.time()

                # 1. UI Extraction & Parsing
                raw_ui = self.controller.get_ui_hierarchy()
                if isinstance(raw_ui, UIHierarchy):
                    ui_hierarchy = raw_ui
                elif self.parser is not None and isinstance(raw_ui, str):
                    ui_hierarchy = self.parser.parse(raw_ui)
                else:
                    ui_hierarchy = UIHierarchy(elements=[])
                state_hash = self.loop_detector.compute_state_hash(ui_hierarchy)

                # 2. Build Token-Efficient Turn Prompt
                prompt = self.compactor.build_turn_prompt(
                    objective=task,
                    ui_hierarchy=ui_hierarchy,
                    recovery_prompt=recovery_prompt,
                )

                # 3. Call Gemini API
                if self.platform == "windows":
                    from ..windows.tools import get_windows_tools, execute_windows_tool
                    tools = get_windows_tools()
                    tool_executor = execute_windows_tool
                else:
                    tools = get_agent_tools()
                    tool_executor = execute_tool

                system_prompt = self.compactor.build_system_prompt(platform=self.platform)
                config = types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=tools,
                    temperature=0.0,
                )

                # Call Gemini API with automatic 429 quota retry and fallback
                response = self._call_gemini_with_retry(prompt=prompt, config=config)

                # Track token usage if available
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    meta = response.usage_metadata
                    p_toks = getattr(meta, "prompt_token_count", 0) or 0
                    c_toks = getattr(meta, "candidates_token_count", 0) or 0
                    tot_toks = getattr(meta, "total_token_count", 0) or (p_toks + c_toks)
                    token_usage["prompt_tokens"] += p_toks
                    token_usage["candidate_tokens"] += c_toks
                    token_usage["total_tokens"] += tot_toks
                else:
                    token_usage["prompt_tokens"] += self.compactor.estimate_prompt_tokens(prompt)

                # 4. Extract Thought and Function Call
                thought = ""
                if hasattr(response, "text") and response.text:
                    thought = response.text

                func_calls = getattr(response, "function_calls", None) or []
                if not func_calls:
                    final_message = "Model returned text without invoking a tool."
                    step_latency = (time.time() - t_step_start) * 1000
                    step_record = AgentStep(
                        step_number=step_idx,
                        tool_name="none",
                        tool_args={},
                        thought=thought,
                        tool_result=final_message,
                        latency_ms=step_latency,
                        screen_state_hash=state_hash,
                        status="FAILED",
                    )
                    executed_steps.append(step_record)
                    if on_step_callback:
                        on_step_callback(step_record)
                    break

                func_call = func_calls[0]
                tool_name = func_call.name
                tool_args = func_call.args if isinstance(func_call.args, dict) else dict(func_call.args)

                # 5. Infinite Loop & Stagnation Detection
                loop_info = self.loop_detector.record_step(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    ui_hierarchy=ui_hierarchy,
                )

                if loop_info.should_abort or (loop_info.detected and loop_info.warning_level >= 2 and loop_info.should_abort):
                    final_message = f"Agent aborted: persistent infinite loop detected ({loop_info.reason})."
                    step_latency = (time.time() - t_step_start) * 1000
                    step_record = AgentStep(
                        step_number=step_idx,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        thought=thought,
                        tool_result=f"Aborted: {loop_info.reason}",
                        latency_ms=step_latency,
                        screen_state_hash=state_hash,
                        status="ABORTED",
                    )
                    executed_steps.append(step_record)
                    if on_step_callback:
                        on_step_callback(step_record)
                    break

                if loop_info.detected:
                    recovery_prompt = loop_info.injection_prompt
                else:
                    recovery_prompt = ""

                # 6. Tool Execution Dispatcher
                if tool_name == "finish_task":
                    status = str(tool_args.get("status", "SUCCESS")).upper()
                    final_message = str(tool_args.get("message", "Objective completed."))
                    step_latency = (time.time() - t_step_start) * 1000
                    step_record = AgentStep(
                        step_number=step_idx,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        thought=thought,
                        tool_result=f"Finished: {final_message}",
                        latency_ms=step_latency,
                        screen_state_hash=state_hash,
                        status="EXECUTED",
                    )
                    executed_steps.append(step_record)
                    self.compactor.add_step(
                        step_num=step_idx,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        result_summary=f"Finished: {final_message}",
                    )
                    if on_step_callback:
                        on_step_callback(step_record)
                    break
                else:
                    tool_ok, result_summary = tool_executor(
                        controller=self.controller,
                        tool_name=tool_name,
                        tool_args=tool_args,
                    )
                    step_latency = (time.time() - t_step_start) * 1000
                    step_record = AgentStep(
                        step_number=step_idx,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        thought=thought,
                        tool_result=result_summary,
                        latency_ms=step_latency,
                        screen_state_hash=state_hash,
                        status="EXECUTED" if tool_ok else "FAILED",
                    )
                    executed_steps.append(step_record)
                    self.compactor.add_step(
                        step_num=step_idx,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        result_summary=result_summary,
                    )
                    if on_step_callback:
                        on_step_callback(step_record)

                    if self.action_delay > 0:
                        time.sleep(self.action_delay)

        except KeyboardInterrupt:
            status = "FAILURE"
            final_message = "Task interrupted by user (SIGINT)."
        except Exception as e:
            status = "FAILURE"
            final_message = f"Execution error: {type(e).__name__}: {str(e)}"
            logger.exception("Unexpected exception in AgentDecisionEngine")

        total_duration = time.time() - start_time
        return TaskResult(
            task=task,
            status=status,
            message=final_message,
            steps=executed_steps,
            total_duration_seconds=total_duration,
            token_usage=token_usage,
        )
