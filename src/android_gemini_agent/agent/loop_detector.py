"""
3-Tier Infinite Loop and Stagnation Detection Engine.
Monitors agent action history and screen state hashes to detect repetitive cycles,
stagnation, and multi-step oscillations, injecting recovery prompts and aborting if unrecoverable.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .models import ActionRecord, LoopDetectionResult

if TYPE_CHECKING:
    from ..parser.models import UIHierarchy

DEFAULT_WARNING_PROMPT = (
    "⚠️ WARNING: You have performed repetitive actions or cycled without making progress. "
    "The previous action had no effect. Do NOT repeat it. Re-evaluate the visible UI, try scrolling/swiping "
    "to reveal new elements, press BACK, or call finish_task(status='FAILURE', message=...) if the objective is blocked."
)


class LoopDetector:
    """
    3-Tier Cycle and Stagnation Detector for Autonomous Android Agents.

    Detection Tiers:
    - Tier 1 (Repetition): >= 3 consecutive identical actions (same tool and arguments).
    - Tier 2 (Stagnation): >= 3 consecutive identical screen state hashes with non-wait actions.
    - Tier 3 (Oscillation): Recurring 2-step (A->B->A->B) or 3-step (A->B->C->A->B->C) action/state cycles.
    """

    def __init__(
        self,
        threshold: int = 3,
        max_warnings: int = 2,
        warning_prompt: str = DEFAULT_WARNING_PROMPT,
    ):
        """
        Args:
            threshold: Number of consecutive steps required to trigger loop detection.
            max_warnings: Maximum consecutive loop warnings before forcing an abort.
            warning_prompt: Prompt text injected into agent context upon loop detection.
        """
        self.threshold = max(2, threshold)
        self.max_warnings = max_warnings
        self.warning_prompt = warning_prompt

        self.action_history: List[Tuple[str, str]] = []  # (tool_name, serialized_args)
        self.action_records: List[ActionRecord] = []
        self.state_hashes: List[str] = []
        self.consecutive_loop_count: int = 0
        self.warnings_issued: int = 0

    def compute_state_hash(self, ui_hierarchy: UIHierarchy) -> str:
        """
        Computes a structural MD5 hash of visible UI element IDs, text, resource IDs, and bounding coordinates.
        """
        summary = "|".join(
            f"{e.elem_id}:{e.text}:{e.resource_id}:{e.bounds.x1},{e.bounds.y1},{e.bounds.x2},{e.bounds.y2}"
            for e in ui_hierarchy.elements
        )
        return hashlib.md5(summary.encode("utf-8")).hexdigest()

    def record_step(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        ui_hierarchy: UIHierarchy,
        result_summary: str = "",
    ) -> LoopDetectionResult:
        """
        Records a step and evaluates 3-tier cycle detection rules.

        Args:
            tool_name: Name of tool called (e.g. tap, swipe, type_text).
            tool_args: Dictionary of arguments passed to the tool.
            ui_hierarchy: Current UIHierarchy instance before/at tool execution.
            result_summary: Optional textual summary of execution result.

        Returns:
            LoopDetectionResult containing detection status, tier, reason, and abort recommendations.
        """
        serialized_args = json.dumps(tool_args, sort_keys=True, default=str)
        action_sig = (tool_name, serialized_args)
        self.action_history.append(action_sig)

        state_hash = self.compute_state_hash(ui_hierarchy)
        self.state_hashes.append(state_hash)

        record = ActionRecord(
            step_number=len(self.action_history),
            tool_name=tool_name,
            tool_args=tool_args,
            result_summary=result_summary,
            state_hash=state_hash,
            timestamp=time.time(),
        )
        self.action_records.append(record)

        is_loop = False
        detected_tier = 0
        reason = ""

        # Tier 1: Identical action repetition (>= threshold identical consecutive actions)
        if len(self.action_history) >= self.threshold:
            recent_actions = self.action_history[-self.threshold:]
            if len(set(recent_actions)) == 1 and recent_actions[0][0] != "wait":
                is_loop = True
                detected_tier = 1
                reason = (
                    f"Tier 1: Executed '{recent_actions[0][0]}' with identical arguments "
                    f"{self.threshold} times consecutively."
                )

        # Tier 2: Stagnant screen state (>= threshold identical states with non-wait actions)
        if not is_loop and len(self.state_hashes) >= self.threshold:
            recent_states = self.state_hashes[-self.threshold:]
            recent_tools = [a[0] for a in self.action_history[-self.threshold:]]
            if len(set(recent_states)) == 1 and all(
                t == recent_tools[0] and t != "wait" for t in recent_tools
            ):
                is_loop = True
                detected_tier = 2
                reason = f"Tier 2: Screen state remained stagnant for {self.threshold} consecutive actions."

        # Tier 3: Oscillation detection
        # 3a. 2-step action oscillation (A -> B -> A -> B)
        if not is_loop and len(self.action_history) >= 4:
            a1, a2, a3, a4 = self.action_history[-4:]
            if a1 == a3 and a2 == a4 and a1 != a2:
                is_loop = True
                detected_tier = 3
                reason = "Tier 3: Detected 2-step action oscillation cycle (A -> B -> A -> B)."

        # 3b. 3-step action oscillation (A -> B -> C -> A -> B -> C)
        if not is_loop and len(self.action_history) >= 6:
            a1, a2, a3, a4, a5, a6 = self.action_history[-6:]
            if a1 == a4 and a2 == a5 and a3 == a6 and len({a1, a2, a3}) > 1:
                is_loop = True
                detected_tier = 3
                reason = "Tier 3: Detected 3-step action oscillation cycle (A -> B -> C -> A -> B -> C)."

        # 3c. 2-step screen state oscillation (State A <-> State B)
        if not is_loop and len(self.state_hashes) >= 4:
            s1, s2, s3, s4 = self.state_hashes[-4:]
            if s1 == s3 and s2 == s4 and s1 != s2:
                is_loop = True
                detected_tier = 3
                reason = "Tier 3: Detected 2-step screen state oscillation cycle (State A <-> State B)."

        if is_loop:
            self.consecutive_loop_count += 1
            self.warnings_issued += 1
            should_abort = self.consecutive_loop_count > self.max_warnings
            return LoopDetectionResult(
                detected=True,
                tier=detected_tier,
                reason=reason,
                warning_level=self.warnings_issued,
                should_abort=should_abort,
                injection_prompt=self.warning_prompt,
            )
        else:
            self.consecutive_loop_count = 0
            return LoopDetectionResult(
                detected=False,
                tier=0,
                reason="",
                warning_level=self.warnings_issued,
                should_abort=False,
                injection_prompt="",
            )

    def reset(self) -> None:
        """Clears all history and resets detector state."""
        self.action_history.clear()
        self.action_records.clear()
        self.state_hashes.clear()
        self.consecutive_loop_count = 0
        self.warnings_issued = 0
