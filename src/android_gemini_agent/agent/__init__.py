"""
Gemini Decision Engine & Automation Agent Module.
Exports models, tool declarations, execution dispatchers, loop detectors, context compactors,
and the main AgentDecisionEngine.
"""

from .compactor import ContextCompactor, HistoryCompactor
from .loop import AgentDecisionEngine
from .loop_detector import LoopDetector
from .models import ActionRecord, AgentStep, LoopDetectionResult, TaskResult
from .tools import execute_tool, get_agent_tools

__all__ = [
    "AgentDecisionEngine",
    "LoopDetector",
    "HistoryCompactor",
    "ContextCompactor",
    "get_agent_tools",
    "execute_tool",
    "AgentStep",
    "TaskResult",
    "ActionRecord",
    "LoopDetectionResult",
]
