"""
Windows Desktop Automation package for Gemini Agent.
"""

from .controller import WindowsController
from .parser import WindowsUIParser
from .tools import execute_windows_tool, get_windows_tools

__all__ = [
    "WindowsController",
    "WindowsUIParser",
    "get_windows_tools",
    "execute_windows_tool",
]
