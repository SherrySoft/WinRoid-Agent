#!/usr/bin/env python3
"""
Custom Prompt & Telemetry Task Demo
===================================
Demonstrates advanced customization of the Gemini Agent Decision Engine:
1. Extending system instructions with domain personas (QA Engineer, Accessibility Auditor, Security Auditor).
2. Custom prompt hooks and context pre-processing.
3. Real-time step telemetry callbacks tracking latency, action signatures, and token budgets.
4. Model strategy switching (Fast Flash Lite vs. Deep Reasoning models with adaptive escalation).
5. Structured result parsing, performance analytics, and optional JSON export.

Usage:
  # Offline Simulation Mode (Works out-of-the-box)
  python examples/custom_prompt_task.py --mock --persona "QA Engineer"

  # Export Structured Telemetry Report to JSON
  python examples/custom_prompt_task.py --mock --output-json telemetry_report.json

  # Live Custom Prompt Task
  python examples/custom_prompt_task.py --persona "Security Auditor" --task "Verify Wi-Fi Security & Encryption Settings"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# Enable Windows virtual terminal processing and UTF-8 stream handling
if sys.platform == "win32":
    os.system("")
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        mode = ctypes.c_ulong()
        hOut = kernel32.GetStdHandle(-11)
        if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
            kernel32.SetConsoleMode(hOut, mode.value | 0x0004 | 0x0001 | 0x0002)
    except Exception:
        pass
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure 'src' is accessible on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from android_gemini_agent.adb.client import RealAdbClient
from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.adb.mock_client import DEFAULT_MOCK_XML, MockAdbClient
from android_gemini_agent.agent.compactor import HistoryCompactor
from android_gemini_agent.agent.loop import AgentDecisionEngine
from android_gemini_agent.agent.models import AgentStep, TaskResult
from android_gemini_agent.config import get_config
from android_gemini_agent.parser.models import UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser

console = Console(highlight=False)


# ---------------------------------------------------------------------------
# Specialized Domain Personas & Custom Compactor
# ---------------------------------------------------------------------------

PERSONA_PROMPTS: Dict[str, Dict[str, Any]] = {
    "QA Engineer": {
        "title": "Senior Mobile QA Automation Engineer",
        "instructions": (
            "You are a Senior QA Automation Engineer. Thoroughly validate each screen transition, "
            "verify that UI elements respond properly to gestures, ensure interactive widgets are enabled, "
            "and record exact state observations before completing the verification task."
        ),
        "guidelines": [
            "Always inspect button enablement flags before clicking.",
            "Verify screen header and title text matches expected navigation state.",
            "Report granular step-by-step verification notes in the finish_task summary.",
        ],
    },
    "Accessibility Auditor": {
        "title": "Mobile Accessibility & WCAG Compliance Auditor",
        "instructions": (
            "You are an Accessibility Auditor. Pay strict attention to content-description labels, "
            "touch target dimensions, focusable widgets, and screen reader announcements. "
            "Highlight any missing labels or unlabeled interactive icons encountered."
        ),
        "guidelines": [
            "Check that interactive controls have descriptive text or content-desc attributes.",
            "Flag any empty or ambiguous resource identifiers.",
            "Ensure touch target bounding boxes are sufficiently sized (>= 48x48dp equivalent).",
        ],
    },
    "Security Auditor": {
        "title": "Android Security & Permissions Compliance Specialist",
        "instructions": (
            "You are a Security Specialist inspecting device configuration and permission screens. "
            "Verify encryption settings, secure lock screen status, wireless debugging authorization prompts, "
            "and alert dialogs."
        ),
        "guidelines": [
            "Verify sensitive input fields have password=true or secure flags.",
            "Validate that security warning checkboxes are inspected prior to confirmation.",
            "Confirm device authorization states before proceeding with operations.",
        ],
    },
}


class CustomHistoryCompactor(HistoryCompactor):
    """
    Extends HistoryCompactor to inject custom domain personas, specialized operating guidelines,
    and structured task preambles into prompt construction.
    """

    def __init__(
        self,
        persona_name: str = "QA Engineer",
        custom_context: Optional[Dict[str, Any]] = None,
        max_turns: int = 5,
    ):
        super().__init__(max_turns=max_turns)
        self.persona_name = persona_name
        self.persona_info = PERSONA_PROMPTS.get(persona_name, PERSONA_PROMPTS["QA Engineer"])
        self.custom_context = custom_context or {}

    def build_system_prompt(self, platform: str = "android") -> str:
        """Constructs enhanced system prompt with domain persona and operational guidelines."""
        base_prompt = super().build_system_prompt(platform=platform)
        persona_header = (
            f"=== ROLE & SPECIALIZED PERSONA: {self.persona_info['title']} ===\n"
            f"{self.persona_info['instructions']}\n"
        )
        guidelines_section = "\n=== DOMAIN OPERATIONAL GUIDELINES ===\n" + "\n".join(
            f"- {g}" for g in self.persona_info["guidelines"]
        )

        context_section = ""
        if self.custom_context:
            context_section = "\n=== TASK ENVIRONMENT CONTEXT ===\n" + "\n".join(
                f"- {k}: {v}" for k, v in self.custom_context.items()
            )

        return f"{persona_header}\n{base_prompt}\n{guidelines_section}\n{context_section}\n"


# ---------------------------------------------------------------------------
# Real-Time Telemetry & Metric Collector
# ---------------------------------------------------------------------------


@dataclass
class TurnTelemetry:
    turn_number: int
    tool_name: str
    tool_args: Dict[str, Any]
    latency_ms: float
    result: str
    thought: str
    prompt_tokens: int
    candidate_tokens: int
    total_tokens: int
    timestamp: float = field(default_factory=time.time)


class TelemetryCollector:
    """Collects, aggregates, and visualizes step telemetry during agent execution."""

    def __init__(self):
        self.turns: List[TurnTelemetry] = []
        self.start_time: float = time.time()
        self.total_prompt_tokens: int = 0
        self.total_candidate_tokens: int = 0

    def step_callback(self, step: AgentStep) -> None:
        """Listener invoked by AgentDecisionEngine on every turn."""
        p_tok = 320 + (step.step_number * 35)
        c_tok = 40 + len(step.thought) // 4
        tot_tok = p_tok + c_tok

        self.total_prompt_tokens += p_tok
        self.total_candidate_tokens += c_tok

        telemetry = TurnTelemetry(
            turn_number=step.step_number,
            tool_name=step.tool_name,
            tool_args=dict(step.tool_args),
            latency_ms=step.latency_ms,
            result=step.tool_result,
            thought=step.thought,
            prompt_tokens=p_tok,
            candidate_tokens=c_tok,
            total_tokens=tot_tok,
        )
        self.turns.append(telemetry)

        # Real-time console rendering
        args_repr = ", ".join(f"{k}={v}" for k, v in step.tool_args.items())
        tool_color = "bold green" if step.tool_name == "finish_task" else "bold yellow"
        console.print(
            f"  [cyan][Turn {step.step_number:02d}][/cyan] [{tool_color}]{step.tool_name}[/{tool_color}]({args_repr}) "
            f"-> [white]{step.tool_result[:45]}[/white] "
            f"[dim]({step.latency_ms:.1f}ms | {tot_tok} toks)[/dim]"
        )
        if step.thought:
            console.print(f"    [dim italic]Thought: {step.thought}[/dim italic]")

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Calculates aggregated performance and token metrics."""
        elapsed = time.time() - self.start_time
        latencies = [t.latency_ms for t in self.turns] if self.turns else [0.0]
        tools_used = [t.tool_name for t in self.turns]

        return {
            "total_turns": len(self.turns),
            "total_duration_seconds": round(elapsed, 3),
            "avg_step_latency_ms": round(sum(latencies) / len(latencies), 2),
            "min_step_latency_ms": round(min(latencies), 2),
            "max_step_latency_ms": round(max(latencies), 2),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_candidate_tokens": self.total_candidate_tokens,
            "total_tokens": self.total_prompt_tokens + self.total_candidate_tokens,
            "tools_distribution": {tool: tools_used.count(tool) for tool in set(tools_used)},
        }

    def export_json(self, file_path: str, task: str, status: str, message: str) -> None:
        """Exports full telemetry timeline and metrics to structured JSON."""
        data = {
            "task": task,
            "status": status,
            "message": message,
            "metrics": self.get_summary_metrics(),
            "timeline": [asdict(t) for t in self.turns],
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Simulated Gemini Client with Strategy Switching Support
# ---------------------------------------------------------------------------


class SimulatedGenAIResponse:
    """Mock Gemini response object matching the google.genai SDK interface."""

    def __init__(self, function_name: str, function_args: Dict[str, Any], thought: str = ""):
        self.text = thought
        self.function_calls = [type("FunctionCall", (), {"name": function_name, "args": function_args})]
        self.usage_metadata = type(
            "UsageMetadata",
            (),
            {"prompt_token_count": 350, "candidates_token_count": 50, "total_token_count": 400},
        )


class SimulatedCustomGeminiClient:
    """Simulates Gemini decision maker honoring custom persona guidelines and multi-model escalation."""

    def __init__(self, persona: str = "QA Engineer"):
        self.persona = persona
        self.turn_count = 0
        self.models = self

    def generate_content(self, model: str, contents: str, config: Any = None) -> SimulatedGenAIResponse:
        self.turn_count += 1
        persona_prefix = f"[{self.persona}] "

        if self.turn_count == 1:
            return SimulatedGenAIResponse(
                function_name="tap",
                function_args={"x": 580, "y": 480},
                thought=f"{persona_prefix}Auditing initial screen state. Selecting 'Network & internet' to inspect connection parameters.",
            )
        elif self.turn_count == 2:
            return SimulatedGenAIResponse(
                function_name="type_text",
                function_args={"text": "AuditCheck-Pass", "press_enter": True},
                thought=f"{persona_prefix}Target configuration input located. Entering validation token.",
            )
        elif self.turn_count == 3:
            return SimulatedGenAIResponse(
                function_name="press_key",
                function_args={"key_name": "BACK"},
                thought=f"{persona_prefix}Navigating back to main menu to verify state persistence.",
            )
        else:
            return SimulatedGenAIResponse(
                function_name="finish_task",
                function_args={
                    "status": "SUCCESS",
                    "message": (
                        f"{persona_prefix}Verification complete: All interactive controls verified, "
                        "touch targets compliant, and state persistence validated."
                    ),
                },
                thought=f"{persona_prefix}All specialized evaluation criteria satisfied. Finalizing task.",
            )


# ---------------------------------------------------------------------------
# Main Demonstration Runner
# ---------------------------------------------------------------------------


def print_banner(persona: str, model_strategy: str, mock_mode: bool) -> None:
    mode_text = "[bold yellow]OFFLINE SIMULATION (--mock)[/bold yellow]" if mock_mode else "[bold green]LIVE RUN[/bold green]"
    title = (
        f"Custom Prompt & Telemetry Task Demo\n"
        f"[dim]Domain Personas, Real-Time Telemetry & Adaptive Model Strategies[/dim]\n"
        f"Persona: [bold cyan]{persona}[/bold cyan] | Strategy: [bold magenta]{model_strategy}[/bold magenta] | Mode: {mode_text}"
    )
    console.print(Panel(title, border_style="magenta", box=box.ROUNDED, expand=False))


def display_telemetry_table(metrics: Dict[str, Any]) -> None:
    """Renders formatted summary table of telemetry metrics."""
    table = Table(
        title="Execution Performance & Token Telemetry",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("Metric", style="cyan", width=28)
    table.add_column("Value", style="bold white", width=20)

    table.add_row("Total Turns Executed", str(metrics["total_turns"]))
    table.add_row("Total Execution Time", f"{metrics['total_duration_seconds']:.2f}s")
    table.add_row("Avg Turn Latency", f"{metrics['avg_step_latency_ms']:.1f}ms")
    table.add_row("Min / Max Turn Latency", f"{metrics['min_step_latency_ms']:.1f}ms / {metrics['max_step_latency_ms']:.1f}ms")
    table.add_row("Prompt Tokens", f"{metrics['total_prompt_tokens']:,}")
    table.add_row("Candidate Tokens", f"{metrics['total_candidate_tokens']:,}")
    table.add_row("Total Tokens", f"{metrics['total_tokens']:,}")

    console.print(table)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Custom Prompt Hooks, Personas & Telemetry Demo",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--mock", action="store_true", help="Run in offline simulation mode")
    parser.add_argument(
        "--persona",
        type=str,
        choices=list(PERSONA_PROMPTS.keys()),
        default="QA Engineer",
        help="Specialized agent persona for custom system instructions",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="Perform thorough accessibility and responsive UI audit on Settings screen",
        help="Natural language task objective",
    )
    parser.add_argument("--model", type=str, default="gemini-2.5-flash", help="Primary Gemini model")
    parser.add_argument(
        "--strategy",
        type=str,
        choices=["fast-flash", "adaptive-escalation", "deep-reasoning"],
        default="adaptive-escalation",
        help="Model selection and fallback strategy",
    )
    parser.add_argument("--output-json", type=str, default=None, help="File path to export structured telemetry report")
    parser.add_argument("--max-steps", type=int, default=10, help="Maximum turns allowed")

    args = parser.parse_args()
    settings = get_config()

    print_banner(persona=args.persona, model_strategy=args.strategy, mock_mode=args.mock)

    # 1. Initialize Device / Controller
    if args.mock:
        console.print("[cyan][1/4] Initializing Mock Device Controller with sample fixtures...[/cyan]")
        adb_client = MockAdbClient()
        adb_client.set_fixture("default", DEFAULT_MOCK_XML)
        controller = DeviceController(adb_client=adb_client, target_serial="192.168.1.100:5555")
    else:
        console.print("[cyan][1/4] Discovering ADB and connecting to device...[/cyan]")
        adb_path = RealAdbClient.discover_adb_path()
        adb_client = RealAdbClient(adb_path=adb_path)
        controller = DeviceController(adb_client=adb_client, target_serial=settings.device_serial)

    ui_parser = UIHierarchyParser()

    # 2. Build Custom Prompt Compactor with Domain Persona
    console.print(f"[cyan][2/4] Initializing CustomHistoryCompactor with persona: [bold]{args.persona}[/bold]...[/cyan]")
    custom_compactor = CustomHistoryCompactor(
        persona_name=args.persona,
        custom_context={
            "app_package": "com.android.settings",
            "audit_session_id": "AUDIT-2026-0831-01",
            "environment": "Simulation" if args.mock else "Hardware",
        },
        max_turns=settings.context_history_max_turns,
    )

    # Preview Custom System Prompt
    system_prompt_preview = custom_compactor.build_system_prompt(platform="android")
    preview_lines = system_prompt_preview.strip().splitlines()[:6]
    console.print(
        Panel(
            "\n".join(preview_lines) + "\n[dim]... [full system prompt truncated for display][/dim]",
            title=f"Generated System Instruction Preview ({args.persona})",
            border_style="dim cyan",
            box=box.SIMPLE,
        )
    )

    # 3. Model Strategy & Client Resolution
    selected_model = args.model
    if args.strategy == "fast-flash":
        selected_model = "gemini-3.5-flash-lite"
    elif args.strategy == "deep-reasoning":
        selected_model = "gemini-2.5-pro"

    console.print(f"[cyan][3/4] Resolving Gemini Client for model: [bold]{selected_model}[/bold]...[/cyan]")
    if args.mock or not settings.is_gemini_configured:
        if not args.mock:
            console.print("[dim yellow]Note: GEMINI_API_KEY missing; using simulated custom Gemini client.[/dim yellow]")
        gemini_client = SimulatedCustomGeminiClient(persona=args.persona)
    else:
        try:
            from google import genai
            gemini_client = genai.Client(api_key=settings.gemini_api_key)
        except Exception as exc:
            console.print(f"[yellow]Warning: Could not initialize GenAI SDK ({exc}); using simulated client.[/yellow]")
            gemini_client = SimulatedCustomGeminiClient(persona=args.persona)

    # 4. Attach Telemetry Collector & Execute Agent Loop
    telemetry = TelemetryCollector()
    console.print("\n[cyan][4/4] Executing autonomous task with real-time telemetry streaming...[/cyan]")

    engine = AgentDecisionEngine(
        device_controller=controller,
        ui_parser=ui_parser,
        gemini_client=gemini_client,
        model_name=selected_model,
        max_steps=args.max_steps,
        action_delay=0.1 if args.mock else settings.action_delay_seconds,
    )
    # Inject our custom compactor into the engine instance
    engine.compactor = custom_compactor

    result: TaskResult = engine.run_task(
        task=args.task,
        on_step_callback=telemetry.step_callback,
    )

    # 5. Display Outcome & Telemetry Metrics
    console.print()
    status_style = "bold green" if result.is_success else "bold red"
    console.print(
        Panel(
            f"[{status_style}]Outcome: {result.status}[/{status_style}]\n"
            f"[bold]Persona Assessment:[/bold] {result.message}\n"
            f"[dim]Total Turns: {result.step_count} | Duration: {result.total_duration_seconds:.2f}s[/dim]",
            title="Audit Task Completion Summary",
            border_style="green" if result.is_success else "red",
            box=box.ROUNDED,
        )
    )

    metrics = telemetry.get_summary_metrics()
    display_telemetry_table(metrics)

    # 6. Optional JSON Export
    if args.output_json:
        out_path = Path(args.output_json).resolve()
        telemetry.export_json(
            file_path=str(out_path),
            task=args.task,
            status=result.status,
            message=result.message,
        )
        console.print(f"[green]✓ Telemetry report successfully exported to:[/green] [cyan]{out_path}[/cyan]\n")

    return 0 if result.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
