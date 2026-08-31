"""
Unit & Integration Tests for UI Hierarchy State Formatters and Token Efficiency
"""

import json
from pathlib import Path
import pytest

from android_gemini_agent.parser.formatters import (
    estimate_tokens,
    format_json,
    format_line_dsl,
    format_markdown_table,
)
from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Helper to load an XML fixture file from tests/fixtures/."""
    file_path = FIXTURES_DIR / filename
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_hierarchy() -> UIHierarchy:
    elements = [
        UIElement(
            elem_id=1,
            node_class="android.widget.Button",
            element_type="Button",
            resource_id="btn_login",
            text="Sign In",
            content_desc="Sign In Button",
            package="com.example",
            bounds=BoundingBox(100, 500, 900, 620),
            center=(500, 560),
            clickable=True,
        ),
        UIElement(
            elem_id=2,
            node_class="android.widget.EditText",
            element_type="Input",
            resource_id="input_email",
            text="user@example.com",
            content_desc="Email",
            package="com.example",
            bounds=BoundingBox(100, 300, 900, 420),
            center=(500, 360),
            clickable=True,
            editable=True,
        ),
        UIElement(
            elem_id=3,
            node_class="android.widget.Switch",
            element_type="Switch",
            resource_id="switch_dark",
            text="Dark Mode",
            content_desc="",
            package="com.example",
            bounds=BoundingBox(800, 700, 950, 800),
            center=(875, 750),
            clickable=True,
            checkable=True,
            checked=True,
        ),
    ]
    return UIHierarchy(elements=elements, rotation=0, screen_size=(1080, 2400))


# ============================================================================
# Tier 1 & 2: Markdown Table Formatter Tests
# ============================================================================


class TestMarkdownTableFormatter:
    def test_markdown_table_structure_and_headers(self, sample_hierarchy: UIHierarchy):
        table = format_markdown_table(sample_hierarchy)
        lines = table.strip().split("\n")

        assert len(lines) == 5  # Header + Divider + 3 elements
        assert lines[0] == "| ID | Type | Label / Text | Resource ID | Center (X,Y) | Properties |"
        assert lines[1] == "|:---|:---|:---|:---|:---|:---|"
        assert "| [1] | Button |" in lines[2]
        assert "btn_login" in lines[2]
        assert "(500, 560)" in lines[2]
        assert "clickable" in lines[2]

    def test_markdown_table_pipe_escaping(self):
        el = UIElement(
            elem_id=1,
            node_class="android.widget.TextView",
            element_type="Text",
            resource_id="id|with|pipe",
            text="Price: $10 | 50% Off",
            content_desc="Desc | with | pipe",
            package="com.example",
            bounds=BoundingBox(0, 0, 100, 50),
            center=(50, 25),
        )
        hierarchy = UIHierarchy(elements=[el])
        table = format_markdown_table(hierarchy)

        # Unescaped pipes inside columns would break markdown columns
        assert r"id\|with\|pipe" in table
        assert r"Price: $10 \| 50% Off" in table

    def test_markdown_table_multiline_sanitization(self):
        el = UIElement(
            elem_id=1,
            node_class="android.widget.TextView",
            element_type="Text",
            resource_id="tv_multi",
            text="Line 1\nLine 2\r\nLine 3",
            content_desc="",
            package="com.example",
            bounds=BoundingBox(0, 0, 100, 50),
            center=(50, 25),
        )
        hierarchy = UIHierarchy(elements=[el])
        table = format_markdown_table(hierarchy)

        # Ensure no embedded newlines inside rows
        lines = table.strip().split("\n")
        assert len(lines) == 3  # Header + Divider + 1 row
        assert "Line 1 Line 2 Line 3" in lines[2]

    def test_markdown_table_empty_hierarchy(self):
        empty_hierarchy = UIHierarchy(elements=[])
        table = format_markdown_table(empty_hierarchy)
        assert "(empty screen)" in table


# ============================================================================
# Tier 1 & 2: Line DSL Formatter Tests
# ============================================================================


class TestLineDSLFormatter:
    def test_line_dsl_format_elements(self, sample_hierarchy: UIHierarchy):
        dsl = format_line_dsl(sample_hierarchy)
        lines = dsl.strip().split("\n")

        assert len(lines) == 3
        # Check Button line
        assert lines[0].startswith("[1] Button")
        assert 'id=btn_login' in lines[0]
        assert 'pos=(500,560)' in lines[0]
        assert '[clickable]' in lines[0]

        # Check Input line
        assert lines[1].startswith("[2] Input")
        assert 'user@example.com' in lines[1]
        assert 'id=input_email' in lines[1]
        assert '[clickable, editable]' in lines[1]

        # Check Switch line
        assert lines[2].startswith("[3] Switch")
        assert '[clickable, checked=True]' in lines[2]

    def test_line_dsl_empty_hierarchy(self):
        empty_hierarchy = UIHierarchy(elements=[])
        assert format_line_dsl(empty_hierarchy) == "(empty screen)"


# ============================================================================
# Tier 1 & 2: JSON Formatter Tests
# ============================================================================


class TestJSONFormatter:
    def test_json_formatter_valid_and_structured(self, sample_hierarchy: UIHierarchy):
        json_str = format_json(sample_hierarchy)
        data = json.loads(json_str)

        assert data["rotation"] == 0
        assert data["screen_size"] == [1080, 2400]
        assert data["element_count"] == 3
        assert len(data["elements"]) == 3

        elem1 = data["elements"][0]
        assert elem1["id"] == 1
        assert elem1["type"] == "Button"
        assert elem1["resource_id"] == "btn_login"
        assert elem1["center"] == [500, 560]
        assert elem1["clickable"] is True

    def test_json_formatter_with_indent(self, sample_hierarchy: UIHierarchy):
        json_str = format_json(sample_hierarchy, indent=2)
        assert "\n" in json_str
        assert "  " in json_str


# ============================================================================
# Tier 1 & 2: UIHierarchy to_prompt_text Integration Tests
# ============================================================================


class TestPromptTextIntegration:
    def test_to_prompt_text_options(self, sample_hierarchy: UIHierarchy):
        table_out = sample_hierarchy.to_prompt_text("markdown_table")
        assert "| ID | Type |" in table_out

        dsl_out = sample_hierarchy.to_prompt_text("line_dsl")
        assert "[1] Button" in dsl_out

        json_out = sample_hierarchy.to_prompt_text("json")
        data = json.loads(json_out)
        assert data["element_count"] == 3

    def test_to_prompt_text_aliases(self, sample_hierarchy: UIHierarchy):
        assert sample_hierarchy.to_prompt_text("table") == sample_hierarchy.to_markdown_table()
        assert sample_hierarchy.to_prompt_text("dsl") == sample_hierarchy.to_line_dsl()
        assert sample_hierarchy.to_prompt_text("compact") == sample_hierarchy.to_line_dsl()

    def test_to_prompt_text_invalid_type_raises_error(self, sample_hierarchy: UIHierarchy):
        with pytest.raises(ValueError, match="Unknown format_type"):
            sample_hierarchy.to_prompt_text("unknown_format")


# ============================================================================
# Tier 3 & 4: Token Efficiency & Cross-Fixture Benchmarks
# ============================================================================


class TestTokenEfficiency:
    @pytest.mark.parametrize(
        "fixture_name",
        [
            "settings_screen.xml",
            "login_screen.xml",
            "dialog_screen.xml",
            "media_feed_screen.xml",
            "edge_cases.xml",
        ],
    )
    def test_fixture_token_budgets(self, fixture_name: str):
        xml_content = load_fixture(fixture_name)
        hierarchy = UIHierarchyParser.parse_xml(xml_content)

        # Assert Markdown Table is under 1,500 token budget
        table_output = hierarchy.to_markdown_table()
        table_tokens = estimate_tokens(table_output)
        assert table_tokens < 1500, f"{fixture_name} Markdown Table exceeded 1500 tokens: {table_tokens}"

        # Assert Line DSL is under 1,500 token budget
        dsl_output = hierarchy.to_line_dsl()
        dsl_tokens = estimate_tokens(dsl_output)
        assert dsl_tokens < 1500, f"{fixture_name} Line DSL exceeded 1500 tokens: {dsl_tokens}"

        # Line DSL should be strictly more compact than raw XML
        raw_tokens = estimate_tokens(xml_content)
        assert dsl_tokens < raw_tokens

    def test_average_screen_token_count_within_target_range(self):
        fixtures = [
            "settings_screen.xml",
            "login_screen.xml",
            "dialog_screen.xml",
            "media_feed_screen.xml",
        ]
        table_token_counts = []
        dsl_token_counts = []

        for name in fixtures:
            xml_content = load_fixture(name)
            hierarchy = UIHierarchyParser.parse_xml(xml_content)
            table_token_counts.append(estimate_tokens(hierarchy.to_markdown_table()))
            dsl_token_counts.append(estimate_tokens(hierarchy.to_line_dsl()))

        avg_table = sum(table_token_counts) / len(table_token_counts)
        avg_dsl = sum(dsl_token_counts) / len(dsl_token_counts)

        # Average token count must be comfortably between 100 and 600 tokens
        assert 100 <= avg_table <= 600, f"Average table tokens {avg_table} outside expected range"
        assert 50 <= avg_dsl <= 400, f"Average DSL tokens {avg_dsl} outside expected range"


# ============================================================================
# Tier 4: Unicode, RTL and Edge Case Formatting Tests
# ============================================================================


class TestUnicodeAndRTLFormatting:
    def test_unicode_and_rtl_formatting(self):
        xml_content = load_fixture("edge_cases.xml")
        hierarchy = UIHierarchyParser.parse_xml(xml_content)

        table_str = hierarchy.to_markdown_table()
        assert "🚀" in table_str
        assert "مرحبا بكم في التطبيق" in table_str

        dsl_str = hierarchy.to_line_dsl()
        assert "🚀" in dsl_str
        assert "مرحبا بكم في التطبيق" in dsl_str

        json_str = hierarchy.to_json()
        assert "🚀" in json_str
        assert "مرحبا بكم في التطبيق" in json_str
