"""
Data models for the Gemini Agent Decision Engine.
Defines AgentStep, TaskResult, ActionRecord, and LoopDetectionResult.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class AgentStep:
    """Represents a single discrete turn or action taken by the agent."""

    step_number: int
    tool_name: str
    tool_args: Dict[str, Any] = field(default_factory=dict)
    thought: str = ""
    tool_result: str = ""
    latency_ms: float = 0.0
    screen_state_hash: str = ""
    status: str = "EXECUTED"

    def summary_str(self) -> str:
        """Returns a concise single-line summary of the step."""
        args_str = ", ".join(f"{k}={v}" for k, v in self.tool_args.items())
        res = f" -> {self.tool_result}" if self.tool_result else ""
        return f"[Step {self.step_number}] {self.tool_name}({args_str}){res}"

    def to_dict(self) -> Dict[str, Any]:
        """Converts step to dictionary representation."""
        return {
            "step": self.step_number,
            "step_number": self.step_number,
            "thought": self.thought,
            "tool": self.tool_name,
            "tool_name": self.tool_name,
            "args": dict(self.tool_args),
            "tool_args": dict(self.tool_args),
            "result": self.tool_result,
            "tool_result": self.tool_result,
            "latency_ms": self.latency_ms,
            "screen_state_hash": self.screen_state_hash,
            "status": self.status,
        }

    def __getitem__(self, key: str) -> Any:
        """Enables dictionary-style key access for backward compatibility."""
        d = self.to_dict()
        if key in d:
            return d[key]
        raise KeyError(f"AgentStep has no field '{key}'")

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()


@dataclass
class TaskResult:
    """Encapsulates the final outcome of an automation task execution."""

    task: str
    status: str  # "SUCCESS" or "FAILURE"
    message: str
    steps: List[AgentStep] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        """Alias for total_duration_seconds."""
        return self.total_duration_seconds

    @property
    def step_count(self) -> int:
        """Total number of executed steps."""
        return len(self.steps)

    @property
    def is_success(self) -> bool:
        """True if the task finished with SUCCESS status."""
        return self.status.upper() == "SUCCESS"

    def to_dict(self) -> Dict[str, Any]:
        """Converts result to dictionary representation."""
        return {
            "task": self.task,
            "status": self.status,
            "message": self.message,
            "steps": [s.to_dict() for s in self.steps],
            "step_count": len(self.steps),
            "total_duration_seconds": self.total_duration_seconds,
            "duration_seconds": self.total_duration_seconds,
            "token_usage": dict(self.token_usage),
        }

    def __getitem__(self, key: str) -> Any:
        """Enables dictionary-style key access for backward compatibility."""
        d = self.to_dict()
        if key in d:
            return d[key]
        raise KeyError(f"TaskResult has no field '{key}'")

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()


@dataclass
class ActionRecord:
    """Historical record of an action taken, used by loop detection and compaction."""

    step_number: int
    tool_name: str
    tool_args: Dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""
    state_hash: str = ""
    timestamp: float = 0.0

    @property
    def signature(self) -> Tuple[str, str]:
        """Deterministic tuple of (tool_name, sorted_json_args)."""
        serialized = json.dumps(self.tool_args, sort_keys=True, default=str)
        return (self.tool_name, serialized)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "tool_name": self.tool_name,
            "tool_args": dict(self.tool_args),
            "result_summary": self.result_summary,
            "state_hash": self.state_hash,
            "timestamp": self.timestamp,
        }


@dataclass
class LoopDetectionResult:
    """Result of an evaluation by the 3-tier LoopDetector."""

    detected: bool = False
    tier: int = 0  # 1 (Repetition), 2 (Stagnation), 3 (Oscillation)
    reason: str = ""
    warning_level: int = 0
    should_abort: bool = False
    injection_prompt: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "tier": self.tier,
            "reason": self.reason,
            "warning_level": self.warning_level,
            "should_abort": self.should_abort,
            "injection_prompt": self.injection_prompt,
        }

    def __getitem__(self, key: str) -> Any:
        """Enables dictionary-style key access for backward compatibility."""
        d = self.to_dict()
        if key in d:
            return d[key]
        raise KeyError(f"LoopDetectionResult has no field '{key}'")

    def __contains__(self, key: str) -> bool:
        return key in self.to_dict()
