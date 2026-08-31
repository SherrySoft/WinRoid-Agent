"""
Shared Pytest Fixtures for Android Gemini Agent Test Suite.
Provides mock ADB clients, realistic XML hierarchy fixtures, parser instances,
mock Gemini API client responses, and test environment configuration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

# Ensure src/ is on Python search path
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

from android_gemini_agent.adb.client import RealAdbClient
from android_gemini_agent.adb.controller import DeviceController
from android_gemini_agent.adb.mock_client import DEFAULT_MOCK_XML, MockAdbClient
from android_gemini_agent.adb.models import (
    ConnectionResult,
    DeviceInfo,
    DeviceState,
    PairingResult,
    ShellResult,
)
from android_gemini_agent.adb.text_escaper import TextEscaper
from android_gemini_agent.parser.formatters import (
    format_json,
    format_line_dsl,
    format_markdown_table,
)
from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser


# ---------------------------------------------------------------------------
# Fixture File Paths & Contents
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Returns absolute Path to tests/fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def settings_xml() -> str:
    """Raw XML content of Android System Settings screen."""
    path = FIXTURES_DIR / "settings_screen.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_MOCK_XML


@pytest.fixture(scope="session")
def login_xml() -> str:
    """Raw XML content of Login / Authentication Form screen."""
    path = FIXTURES_DIR / "login_screen.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.example.app" bounds="[0,0][1080,2400]">
    <node index="0" text="Sign In" resource-id="com.example.app:id/title" class="android.widget.TextView" package="com.example.app" bounds="[100,200][980,300]" clickable="false"/>
    <node index="1" text="user@example.com" resource-id="com.example.app:id/username" class="android.widget.EditText" package="com.example.app" bounds="[100,350][980,470]" clickable="true"/>
    <node index="2" text="" resource-id="com.example.app:id/password" class="android.widget.EditText" package="com.example.app" bounds="[100,500][980,620]" clickable="true" password="true"/>
    <node index="3" text="Remember me" resource-id="com.example.app:id/remember" class="android.widget.CheckBox" package="com.example.app" bounds="[100,650][500,730]" clickable="true" checkable="true" checked="true"/>
    <node index="4" text="Log In" resource-id="com.example.app:id/btn_login" class="android.widget.Button" package="com.example.app" bounds="[100,770][980,890]" clickable="true"/>
  </node>
</hierarchy>"""


@pytest.fixture(scope="session")
def dialog_xml() -> str:
    """Raw XML content of Alert / Permission Dialog screen."""
    path = FIXTURES_DIR / "dialog_screen.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="android" bounds="[0,0][1080,2400]">
    <node index="0" text="Allow Wireless Debugging?" resource-id="android:id/alertTitle" class="android.widget.TextView" package="android" bounds="[140,950][940,1050]" clickable="false"/>
    <node index="1" text="Always allow on this network" resource-id="android:id/checkbox" class="android.widget.CheckBox" package="android" bounds="[140,1080][940,1160]" clickable="true" checkable="true" checked="false"/>
    <node index="2" text="Cancel" resource-id="android:id/button2" class="android.widget.Button" package="android" bounds="[480,1220][680,1320]" clickable="true"/>
    <node index="3" text="Allow" resource-id="android:id/button1" class="android.widget.Button" package="android" bounds="[720,1220][920,1320]" clickable="true"/>
  </node>
</hierarchy>"""


@pytest.fixture(scope="session")
def media_feed_xml() -> str:
    """Raw XML content of Media Feed / App screen."""
    path = FIXTURES_DIR / "media_feed_screen.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.google.android.youtube" bounds="[0,0][1080,2400]">
    <node index="0" text="" content-desc="Search YouTube" resource-id="com.google.android.youtube:id/menu_search" class="android.widget.ImageView" package="com.google.android.youtube" bounds="[880,100][1020,240]" clickable="true"/>
    <node index="1" text="" resource-id="com.google.android.youtube:id/results_list" class="androidx.recyclerview.widget.RecyclerView" package="com.google.android.youtube" bounds="[0,250][1080,2200]" scrollable="true">
      <node index="0" text="Gemini 2.5 Flash Deep Dive" resource-id="com.google.android.youtube:id/video_title" class="android.widget.TextView" package="com.google.android.youtube" bounds="[60,280][1020,380]" clickable="true"/>
      <node index="1" text="Android Wireless Debugging Tutorial" resource-id="com.google.android.youtube:id/video_title" class="android.widget.TextView" package="com.google.android.youtube" bounds="[60,700][1020,800]" clickable="true"/>
    </node>
  </node>
</hierarchy>"""


@pytest.fixture(scope="session")
def edge_cases_xml() -> str:
    """Raw XML content containing edge cases (Unicode, RTL, zero area, offscreen)."""
    path = FIXTURES_DIR / "edge_cases.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.example.edge" bounds="[0,0][1080,2400]">
    <node index="0" text="Invisible Node" resource-id="zero_area" class="android.widget.TextView" package="com.example.edge" bounds="[0,0][0,0]" clickable="false"/>
    <node index="1" text="Offscreen Top" resource-id="offscreen_top" class="android.widget.Button" package="com.example.edge" bounds="[100,-200][500,-50]" clickable="true"/>
    <node index="2" text="Offscreen Bottom" resource-id="offscreen_bottom" class="android.widget.Button" package="com.example.edge" bounds="[100,2500][500,2700]" clickable="true"/>
    <node index="3" text="Special Characters &amp; &lt; &gt; &quot;" resource-id="special_chars" class="android.widget.TextView" package="com.example.edge" bounds="[50,100][900,200]" clickable="true"/>
    <node index="4" text="مرحبا بكم (Arabic RTL)" resource-id="rtl_text" class="android.widget.TextView" package="com.example.edge" bounds="[50,220][900,320]" clickable="true"/>
    <node index="5" text="Emoji 🚀🤖🔥 Wi‑Fi" resource-id="emoji_text" class="android.widget.TextView" package="com.example.edge" bounds="[50,340][900,440]" clickable="true"/>
  </node>
</hierarchy>"""


@pytest.fixture(scope="session")
def all_xml_fixtures(
    settings_xml: str,
    login_xml: str,
    dialog_xml: str,
    media_feed_xml: str,
    edge_cases_xml: str,
) -> Dict[str, str]:
    """Dictionary containing all loaded screen XML fixtures."""
    return {
        "settings": settings_xml,
        "login": login_xml,
        "dialog": dialog_xml,
        "media_feed": media_feed_xml,
        "edge_cases": edge_cases_xml,
    }


# ---------------------------------------------------------------------------
# Mock ADB Subsystem Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_adb_client(all_xml_fixtures: Dict[str, str]) -> MockAdbClient:
    """Provides a fresh MockAdbClient with all XML fixtures registered."""
    client = MockAdbClient()
    for key, xml in all_xml_fixtures.items():
        client.set_fixture(key, xml)
    return client


@pytest.fixture
def connected_mock_adb_client(mock_adb_client: MockAdbClient) -> MockAdbClient:
    """Provides a MockAdbClient pre-connected to 192.168.1.100:5555."""
    res = mock_adb_client.connect("192.168.1.100", 5555)
    assert res.success, "Pre-connection failed in fixture"
    return mock_adb_client


@pytest.fixture
def device_controller(connected_mock_adb_client: MockAdbClient) -> DeviceController:
    """Provides a DeviceController bound to the pre-connected mock device."""
    return DeviceController(
        adb_client=connected_mock_adb_client,
        target_serial="192.168.1.100:5555",
        auto_reconnect=True,
        max_reconnect_attempts=3,
        base_backoff_sec=0.01,  # Fast backoff for unit/e2e testing
    )


# ---------------------------------------------------------------------------
# UI Hierarchy & Parser Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ui_parser() -> UIHierarchyParser:
    """Provides a standard UIHierarchyParser configured for 1080x2400 displays."""
    return UIHierarchyParser(default_screen_size=(1080, 2400))


@pytest.fixture
def parsed_settings_hierarchy(
    ui_parser: UIHierarchyParser, settings_xml: str
) -> UIHierarchy:
    """Parsed UIHierarchy instance for System Settings screen."""
    return ui_parser.parse(settings_xml)


@pytest.fixture
def parsed_login_hierarchy(
    ui_parser: UIHierarchyParser, login_xml: str
) -> UIHierarchy:
    """Parsed UIHierarchy instance for Login screen."""
    return ui_parser.parse(login_xml)


@pytest.fixture
def parsed_dialog_hierarchy(
    ui_parser: UIHierarchyParser, dialog_xml: str
) -> UIHierarchy:
    """Parsed UIHierarchy instance for Alert Dialog screen."""
    return ui_parser.parse(dialog_xml)


@pytest.fixture
def parsed_media_hierarchy(
    ui_parser: UIHierarchyParser, media_feed_xml: str
) -> UIHierarchy:
    """Parsed UIHierarchy instance for Media Feed screen."""
    return ui_parser.parse(media_feed_xml)


@pytest.fixture
def parsed_edge_cases_hierarchy(
    ui_parser: UIHierarchyParser, edge_cases_xml: str
) -> UIHierarchy:
    """Parsed UIHierarchy instance for Edge Cases screen."""
    return ui_parser.parse(edge_cases_xml)


# ---------------------------------------------------------------------------
# Mock Gemini API & Response Generators
# ---------------------------------------------------------------------------


class MockFunctionCall:
    """Mock representing a Gemini function call in google.genai."""

    def __init__(self, name: str, args: Dict[str, Any]):
        self.name = name
        self.args = args

    def __repr__(self) -> str:
        return f"MockFunctionCall(name='{self.name}', args={self.args})"


class MockCandidate:
    """Mock representing a candidate response from Gemini."""

    def __init__(
        self,
        function_calls: Optional[List[MockFunctionCall]] = None,
        text: Optional[str] = None,
    ):
        self.function_calls = function_calls or []
        self._text = text or ""

    @property
    def content(self):
        mock_content = MagicMock()
        parts = []
        for fc in self.function_calls:
            part = MagicMock()
            part.function_call = fc
            parts.append(part)
        if self._text:
            part = MagicMock()
            part.text = self._text
            parts.append(part)
        mock_content.parts = parts
        return mock_content


class MockGenerateContentResponse:
    """Mock response from google.genai client.models.generate_content."""

    def __init__(
        self,
        function_calls: Optional[List[Dict[str, Any]]] = None,
        text: Optional[str] = None,
    ):
        self._function_calls = [
            MockFunctionCall(fc["name"], fc.get("args", {}))
            for fc in (function_calls or [])
        ]
        self._text = text or ""
        self.candidates = [MockCandidate(self._function_calls, self._text)]

    @property
    def function_calls(self) -> List[MockFunctionCall]:
        return self._function_calls

    @property
    def text(self) -> str:
        return self._text


@pytest.fixture
def mock_gemini_response_factory() -> Callable[..., MockGenerateContentResponse]:
    """Factory fixture to produce mock Gemini responses with function calls."""

    def _create_response(
        tool_name: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        text: Optional[str] = None,
    ) -> MockGenerateContentResponse:
        calls = []
        if tool_name:
            calls.append({"name": tool_name, "args": args or {}})
        return MockGenerateContentResponse(function_calls=calls, text=text)

    return _create_response


@pytest.fixture
def mock_gemini_client(mock_gemini_response_factory) -> MagicMock:
    """
    Mock google-genai Client that returns canned or sequential responses.
    """
    client = MagicMock()
    # Default behavior returns finish_task SUCCESS
    default_resp = mock_gemini_response_factory(
        tool_name="finish_task",
        args={"status": "SUCCESS", "message": "Objective completed."},
    )
    client.models.generate_content.return_value = default_resp
    return client


# ---------------------------------------------------------------------------
# Test Environment Configuration Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch) -> Dict[str, str]:
    """Configures deterministic mock environment variables for testing."""
    env_vars = {
        "GEMINI_API_KEY": "test_gemini_dummy_api_key_123456",
        "GEMINI_MODEL": "gemini-2.5-flash",
        "ADB_DEVICE_IP": "192.168.1.100",
        "ADB_DEVICE_PORT": "5555",
        "ADB_TIMEOUT_SECONDS": "5.0",
        "MAX_AGENT_STEPS": "20",
        "ACTION_DELAY_SECONDS": "0.0",
        "LOOP_DETECTION_THRESHOLD": "3",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars
