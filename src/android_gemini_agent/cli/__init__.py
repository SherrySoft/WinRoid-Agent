"""
CLI package for Android Gemini Automation Agent.
"""

from .app import AndroidAgentCLI, main
from .console import (
    action_spinner,
    console,
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

__all__ = [
    "AndroidAgentCLI",
    "main",
    "console",
    "get_console",
    "render_banner",
    "render_step_card",
    "render_ui_table",
    "render_outcome_panel",
    "render_status_panel",
    "render_settings_table",
    "render_help_panel",
    "render_info",
    "render_success",
    "render_warning",
    "render_error",
    "thinking_spinner",
    "action_spinner",
]
