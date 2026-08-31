"""
Unit and integration tests for Windows desktop automation modules.
"""

from unittest.mock import MagicMock, patch
import pytest

from android_gemini_agent.agent.loop import AgentDecisionEngine
from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.windows.controller import WindowsController
from android_gemini_agent.windows.parser import WindowsUIParser
from android_gemini_agent.windows.tools import (
    execute_windows_tool,
    get_windows_tools,
)


class TestWindowsTools:
    """Tests Windows tool definitions and dispatcher."""

    def test_tool_declarations(self):
        tools = get_windows_tools()
        assert len(tools) == 1
        names = [decl.name for decl in tools[0].function_declarations]
        assert "click" in names
        assert "type_text" in names
        assert "press_key" in names
        assert "hotkey" in names
        assert "scroll" in names
        assert "launch_app" in names
        assert "wait" in names
        assert "finish_task" in names

    def test_tool_execution_dispatch(self):
        mock_controller = MagicMock(spec=WindowsController)
        mock_controller.click.return_value = True
        mock_controller.type_text.return_value = True
        mock_controller.press_key.return_value = True
        mock_controller.hotkey.return_value = True
        mock_controller.scroll.return_value = True
        mock_controller.launch_app.return_value = True

        # Click
        ok, res = execute_windows_tool(mock_controller, "click", {"x": 100, "y": 200, "button": "left"})
        assert ok is True
        mock_controller.click.assert_called_once_with(100, 200, button="left", double=False)

        # Type
        ok, res = execute_windows_tool(mock_controller, "type_text", {"text": "hello", "press_enter": True})
        assert ok is True
        mock_controller.type_text.assert_called_once_with("hello", press_enter=True, clear_first=False)

        # Hotkey
        ok, res = execute_windows_tool(mock_controller, "hotkey", {"keys": ["win", "r"]})
        assert ok is True
        mock_controller.hotkey.assert_called_once_with("win", "r")

        # Key
        ok, res = execute_windows_tool(mock_controller, "press_key", {"key_name": "enter"})
        assert ok is True
        mock_controller.press_key.assert_called_once_with("enter")

        # Launch App
        ok, res = execute_windows_tool(mock_controller, "launch_app", {"app_name": "notepad"})
        assert ok is True
        mock_controller.launch_app.assert_called_once_with("notepad")

        # Finish
        ok, res = execute_windows_tool(mock_controller, "finish_task", {"status": "SUCCESS", "message": "Done"})
        assert ok is True
        assert "Done" in res


class TestWindowsParser:
    """Tests Windows UI hierarchy extraction and compression."""

    def test_parser_extract_hierarchy_empty(self):
        parser = WindowsUIParser()
        hierarchy = parser.extract_hierarchy(root_control=None)
        assert isinstance(hierarchy, UIHierarchy)

    def test_parser_control_conversion(self):
        parser = WindowsUIParser()
        elements = []

        class MockRect:
            def __init__(self, left, top, right, bottom):
                self.left = left
                self.top = top
                self.right = right
                self.bottom = bottom
            def width(self): return self.right - self.left
            def height(self): return self.bottom - self.top

        class MockControl:
            def __init__(self, name, ctrl_type, rect):
                self.Name = name
                self.ControlTypeName = ctrl_type
                self.ClassName = ctrl_type
                self.AutomationId = "test_id"
                self.IsEnabled = True
                self.IsOffscreen = False
                self.BoundingRectangle = rect
            def GetValuePattern(self): return None
            def GetChildren(self): return []

        mock_ctrl = MockControl("Start Button", "ButtonControl", MockRect(10, 10, 60, 60))
        parser._traverse_control(mock_ctrl, depth=0, elements=elements)

        assert len(elements) == 1
        elem = elements[0]
        assert elem.text == "Start Button"
        assert elem.element_type == "Button"
        assert elem.clickable is True
        assert elem.bounds.center == (35, 35)


class TestWindowsAgentEngineIntegration:
    """Tests AgentDecisionEngine operating in Windows desktop mode."""

    def test_windows_agent_loop(self):
        mock_controller = MagicMock()
        mock_controller.hotkey = MagicMock(return_value=True)
        del mock_controller.adb  # Ensure platform is detected as windows

        sample_elem = UIElement(
            elem_id=1,
            node_class="EditControl",
            element_type="Edit",
            resource_id="search_box",
            text="Search",
            content_desc="Search Box",
            package="windows",
            bounds=BoundingBox(x1=100, y1=100, x2=300, y2=150),
            center=(200, 125),
            clickable=True,
        )
        sample_hierarchy = UIHierarchy(elements=[sample_elem])
        mock_controller.get_ui_hierarchy.return_value = sample_hierarchy

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_call = MagicMock()
        mock_call.name = "finish_task"
        mock_call.args = {"status": "SUCCESS", "message": "Windows task completed"}
        mock_resp.function_calls = [mock_call]
        mock_resp.text = "Finished task on Windows"
        mock_client.models.generate_content.return_value = mock_resp

        engine = AgentDecisionEngine(
            device_controller=mock_controller,
            ui_parser=None,
            gemini_client=mock_client,
            model_name="gemini-3.5-flash-lite",
            max_steps=5,
        )

        assert engine.platform == "windows"
        result = engine.run_task("Search for documents")
        assert result.status == "SUCCESS"
        assert len(result.steps) == 1
