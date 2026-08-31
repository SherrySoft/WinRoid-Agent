"""
Unit & Integration Tests for UI Hierarchy Parser and Data Models
"""

import os
from pathlib import Path
import pytest

from android_gemini_agent.parser.models import BoundingBox, UIElement, UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> str:
    """Helper to load an XML fixture file from tests/fixtures/."""
    file_path = FIXTURES_DIR / filename
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================================
# Tier 1 & 2: BoundingBox Model & Coordinate Mathematics Tests
# ============================================================================


class TestBoundingBox:
    def test_bounding_box_creation_and_properties(self):
        bbox = BoundingBox(x1=100, y1=200, x2=500, y2=800)
        assert bbox.x1 == 100
        assert bbox.y1 == 200
        assert bbox.x2 == 500
        assert bbox.y2 == 800
        assert bbox.width == 400
        assert bbox.height == 600
        assert bbox.center_x == 300
        assert bbox.center_y == 500
        assert bbox.center == (300, 500)
        assert bbox.area == 240000

    def test_bounding_box_clamping_negative_dimensions(self):
        bbox = BoundingBox(x1=500, y1=800, x2=100, y2=200)
        assert bbox.width == 0
        assert bbox.height == 0
        assert bbox.area == 0

    def test_bounding_box_from_str_valid(self):
        bbox = BoundingBox.from_str("[144,120][450,192]")
        assert bbox is not None
        assert bbox.x1 == 144
        assert bbox.y1 == 120
        assert bbox.x2 == 450
        assert bbox.y2 == 192
        assert bbox.center == (297, 156)

    def test_bounding_box_from_str_negative_coords(self):
        bbox = BoundingBox.from_str("[-500,-200][-100,-50]")
        assert bbox is not None
        assert bbox.x1 == -500
        assert bbox.y1 == -200
        assert bbox.x2 == -100
        assert bbox.y2 == -50

    def test_bounding_box_from_str_invalid(self):
        assert BoundingBox.from_str("") is None
        assert BoundingBox.from_str(None) is None
        assert BoundingBox.from_str("invalid_bounds") is None
        assert BoundingBox.from_str("[100,200]") is None

    def test_bounding_box_visibility_within_screen(self):
        screen_w, screen_h = 1080, 2400
        # Normal visible box
        box = BoundingBox(100, 200, 400, 500)
        assert box.is_visible(screen_w, screen_h) is True

        # Zero size / empty area
        assert BoundingBox(0, 0, 0, 0).is_visible(screen_w, screen_h) is False
        assert BoundingBox(100, 200, 100, 500).is_visible(screen_w, screen_h) is False
        assert BoundingBox(100, 200, 400, 200).is_visible(screen_w, screen_h) is False

        # Offscreen left (x2 <= 0)
        assert BoundingBox(-500, 100, -10, 300).is_visible(screen_w, screen_h) is False
        assert BoundingBox(-500, 100, 0, 300).is_visible(screen_w, screen_h) is False

        # Offscreen top (y2 <= 0)
        assert BoundingBox(100, -400, 500, 0).is_visible(screen_w, screen_h) is False

        # Offscreen right (x1 >= screen_w)
        assert BoundingBox(1080, 100, 1500, 300).is_visible(screen_w, screen_h) is False
        assert BoundingBox(1200, 100, 1500, 300).is_visible(screen_w, screen_h) is False

        # Offscreen bottom (y1 >= screen_h)
        assert BoundingBox(100, 2400, 500, 2600).is_visible(screen_w, screen_h) is False
        assert BoundingBox(100, 2500, 500, 2700).is_visible(screen_w, screen_h) is False

    def test_bounding_box_contains_point(self):
        bbox = BoundingBox(100, 200, 300, 400)
        assert bbox.contains_point(200, 300) is True
        assert bbox.contains_point(100, 200) is True  # top-left corner
        assert bbox.contains_point(300, 400) is True  # bottom-right corner
        assert bbox.contains_point(50, 300) is False  # outside left
        assert bbox.contains_point(350, 300) is False  # outside right
        assert bbox.contains_point(200, 150) is False  # outside top
        assert bbox.contains_point(200, 450) is False  # outside bottom

    def test_bounding_box_serialization(self):
        bbox = BoundingBox(10, 20, 30, 40)
        d = bbox.to_dict()
        assert d == {
            "x1": 10,
            "y1": 20,
            "x2": 30,
            "y2": 40,
            "width": 20,
            "height": 20,
            "center": [20, 30],
            "area": 400,
        }
        assert str(bbox) == "[10,20][30,40]"
        assert repr(bbox) == "BoundingBox([10,20][30,40])"


# ============================================================================
# Tier 1 & 2: UIElement Model Tests
# ============================================================================


class TestUIElement:
    def test_element_label_formatting(self):
        bbox = BoundingBox(0, 0, 100, 50)
        # Text only
        el1 = UIElement(1, "android.widget.TextView", "Text", "id1", "Hello", "", "pkg", bbox, (50, 25))
        assert el1.label() == '"Hello"'
        assert el1.get_display_label() == '"Hello"'

        # Content-desc only
        el2 = UIElement(2, "android.widget.ImageView", "Icon", "id2", "", "Search", "pkg", bbox, (50, 25))
        assert el2.label() == 'desc: "Search"'

        # Both text and desc, identical
        el3 = UIElement(3, "android.widget.Button", "Button", "id3", "Submit", "Submit", "pkg", bbox, (50, 25))
        assert el3.label() == '"Submit"'

        # Both text and desc, distinct
        el4 = UIElement(4, "android.widget.Button", "Button", "id4", "Submit", "Submit form", "pkg", bbox, (50, 25))
        assert el4.label() == '"Submit" (desc: "Submit form")'

        # Empty
        el5 = UIElement(5, "android.view.View", "View", "id5", "", "", "pkg", bbox, (50, 25))
        assert el5.label() == '""'

    def test_element_properties_summary(self):
        bbox = BoundingBox(0, 0, 100, 50)
        # Simple view
        el1 = UIElement(1, "android.widget.TextView", "Text", "id1", "Hi", "", "pkg", bbox, (50, 25))
        assert el1.properties() == "view"

        # Clickable button
        el2 = UIElement(2, "android.widget.Button", "Button", "id2", "Ok", "", "pkg", bbox, (50, 25), clickable=True)
        assert el2.properties() == "clickable"

        # Checked switch
        el3 = UIElement(3, "android.widget.Switch", "Switch", "id3", "", "", "pkg", bbox, (50, 25), clickable=True, checkable=True, checked=True)
        assert el3.properties() == "clickable, checked=True"

        # Disabled input with password
        el4 = UIElement(4, "android.widget.EditText", "Input", "id4", "", "", "pkg", bbox, (50, 25), editable=True, enabled=False, password=True)
        assert el4.properties() == "editable, password, disabled"

        # Selected and focused
        el5 = UIElement(5, "android.widget.Button", "Button", "id5", "", "", "pkg", bbox, (50, 25), focused=True, selected=True)
        assert el5.properties() == "focused, selected"

    def test_element_actionable_and_informative_detection(self):
        bbox = BoundingBox(0, 0, 100, 50)
        # Actionable via clickable
        assert UIElement(1, "View", "View", "", "", "", "pkg", bbox, (50, 25), clickable=True).is_actionable() is True
        # Actionable via scrollable
        assert UIElement(2, "View", "View", "", "", "", "pkg", bbox, (50, 25), scrollable=True).is_actionable() is True
        # Actionable via editable
        assert UIElement(3, "View", "View", "", "", "", "pkg", bbox, (50, 25), editable=True).is_actionable() is True
        # Actionable via checkable
        assert UIElement(4, "View", "View", "", "", "", "pkg", bbox, (50, 25), checkable=True).is_actionable() is True
        # Non-actionable container
        assert UIElement(5, "View", "View", "", "", "", "pkg", bbox, (50, 25)).is_actionable() is False

        # Informative via text
        assert UIElement(6, "View", "View", "", "Test", "", "pkg", bbox, (50, 25)).is_informative() is True
        # Informative via content-desc
        assert UIElement(7, "View", "View", "", "", "Description", "pkg", bbox, (50, 25)).is_informative() is True
        # Whitespace-only is not informative
        assert UIElement(8, "View", "View", "", "   \t  ", "", "pkg", bbox, (50, 25)).is_informative() is False

    def test_element_to_dict_structure(self):
        bbox = BoundingBox(10, 20, 110, 70)
        el = UIElement(
            elem_id=1,
            node_class="android.widget.Button",
            element_type="Button",
            resource_id="btn_ok",
            text="OK",
            content_desc="Confirm",
            package="com.example",
            bounds=bbox,
            center=(60, 45),
            clickable=True,
            checked=False,
        )
        d = el.to_dict()
        assert d["id"] == 1
        assert d["type"] == "Button"
        assert d["node_class"] == "android.widget.Button"
        assert d["resource_id"] == "btn_ok"
        assert d["text"] == "OK"
        assert d["content_desc"] == "Confirm"
        assert d["bounds"] == [10, 20, 110, 70]
        assert d["center"] == [60, 45]
        assert d["clickable"] is True


# ============================================================================
# Tier 1 & 2: UIHierarchy Model & Search Methods Tests
# ============================================================================


class TestUIHierarchy:
    @pytest.fixture
    def sample_hierarchy(self) -> UIHierarchy:
        elements = [
            UIElement(
                elem_id=1,
                node_class="android.widget.FrameLayout",
                element_type="Container",
                resource_id="container_root",
                text="",
                content_desc="",
                package="com.example",
                bounds=BoundingBox(0, 0, 1080, 2400),
                center=(540, 1200),
                clickable=False,
            ),
            UIElement(
                elem_id=2,
                node_class="android.widget.TextView",
                element_type="Text",
                resource_id="title_text",
                text="Welcome to Settings",
                content_desc="",
                package="com.example",
                bounds=BoundingBox(100, 100, 900, 200),
                center=(500, 150),
            ),
            UIElement(
                elem_id=3,
                node_class="android.widget.Button",
                element_type="Button",
                resource_id="btn_submit",
                text="Submit",
                content_desc="Submit Button",
                package="com.example",
                bounds=BoundingBox(100, 500, 400, 600),
                center=(250, 550),
                clickable=True,
            ),
            UIElement(
                elem_id=4,
                node_class="android.widget.ImageView",
                element_type="Icon",
                resource_id="icon_help",
                text="",
                content_desc="Help & Support",
                package="com.example",
                bounds=BoundingBox(500, 500, 600, 600),
                center=(550, 550),
                clickable=True,
            ),
        ]
        return UIHierarchy(elements=elements, rotation=0, screen_size=(1080, 2400))

    def test_find_element_by_id(self, sample_hierarchy: UIHierarchy):
        el = sample_hierarchy.find_element_by_id(3)
        assert el is not None
        assert el.elem_id == 3
        assert el.text == "Submit"

        assert sample_hierarchy.find_element_by_id(999) is None

    def test_find_element_by_coords_exact_and_nested(self, sample_hierarchy: UIHierarchy):
        # Point (250, 550) is inside both root (0,0,1080,2400) and Button (100,500,400,600).
        # Smallest area element (Button) should be returned!
        el = sample_hierarchy.find_element_by_coords(250, 550)
        assert el is not None
        assert el.elem_id == 3
        assert el.element_type == "Button"

        # Point (550, 550) should return Icon
        el_icon = sample_hierarchy.find_element_by_coords(550, 550)
        assert el_icon is not None
        assert el_icon.elem_id == 4

        # Point outside all elements
        assert sample_hierarchy.find_element_by_coords(2000, 3000) is None

    def test_find_elements_by_text(self, sample_hierarchy: UIHierarchy):
        # Substring case-insensitive match
        res1 = sample_hierarchy.find_elements_by_text("settings")
        assert len(res1) == 1
        assert res1[0].elem_id == 2

        # Content desc search
        res2 = sample_hierarchy.find_elements_by_text("support")
        assert len(res2) == 1
        assert res2[0].elem_id == 4

        # Exact match
        res3 = sample_hierarchy.find_elements_by_text("Submit", exact=True)
        assert len(res3) == 1
        assert res3[0].elem_id == 3

        # Non-matching
        assert len(sample_hierarchy.find_elements_by_text("nonexistent")) == 0

    def test_find_elements_by_resource_id(self, sample_hierarchy: UIHierarchy):
        res1 = sample_hierarchy.find_elements_by_resource_id("btn_submit")
        assert len(res1) == 1
        assert res1[0].elem_id == 3

        res2 = sample_hierarchy.find_elements_by_resource_id("com.example:id/btn_submit")
        assert len(res2) == 1
        assert res2[0].elem_id == 3

    def test_hierarchy_dunder_methods(self, sample_hierarchy: UIHierarchy):
        assert len(sample_hierarchy) == 4
        assert [e.elem_id for e in sample_hierarchy] == [1, 2, 3, 4]
        assert sample_hierarchy[2].elem_id == 3


# ============================================================================
# Tier 1 & 2: UIHierarchyParser Class & Pruning Heuristics Tests
# ============================================================================


class TestUIHierarchyParser:
    def test_simplify_class_mappings(self):
        p = UIHierarchyParser()
        assert p.simplify_class("android.widget.TextView") == "Text"
        assert p.simplify_class("android.widget.EditText") == "Input"
        assert p.simplify_class("android.widget.AutoCompleteTextView") == "Input"
        assert p.simplify_class("android.widget.Button") == "Button"
        assert p.simplify_class("android.widget.ImageButton") == "Button"
        assert p.simplify_class("android.widget.ImageView") == "Icon"
        assert p.simplify_class("android.widget.CheckBox") == "CheckBox"
        assert p.simplify_class("android.widget.RadioButton") == "RadioButton"
        assert p.simplify_class("android.widget.Switch") == "Switch"
        assert p.simplify_class("androidx.recyclerview.widget.RecyclerView") == "List"
        assert p.simplify_class("android.widget.ListView") == "List"
        assert p.simplify_class("android.widget.ScrollView") == "ScrollView"
        assert p.simplify_class("android.webkit.WebView") == "WebView"
        assert p.simplify_class("com.google.android.material.floatingactionbutton.FloatingActionButton") == "FloatingActionButton"

    def test_clean_resource_id(self):
        p = UIHierarchyParser()
        assert p.clean_resource_id("com.android.settings:id/switch_widget") == "switch_widget"
        assert p.clean_resource_id("android:id/button1") == "button1"
        assert p.clean_resource_id("custom_id") == "custom_id"
        assert p.clean_resource_id("") == ""

    def test_parse_empty_and_whitespace(self):
        p = UIHierarchyParser()
        h1 = p.parse("")
        assert len(h1.elements) == 0
        h2 = p.parse("   \n\t  ")
        assert len(h2.elements) == 0

    def test_parse_malformed_xml_graceful(self):
        p = UIHierarchyParser()
        h = p.parse("<hierarchy rotation='0'><node bounds='[0,0][100,100]'></hierarchy>")
        # Malformed XML syntax should not throw an unhandled exception, returns empty hierarchy
        assert len(h.elements) == 0

    def test_parse_xml_with_adb_preamble(self):
        p = UIHierarchyParser()
        raw = (
            "UI hierchary dumped to: /data/local/tmp/uidump.xml\n"
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n"
            "<hierarchy rotation='0'>\n"
            "  <node index='0' text='OK' resource-id='com.app:id/btn' class='android.widget.Button' "
            "package='com.app' content-desc='' checkable='false' checked='false' clickable='true' "
            "enabled='true' focusable='true' focused='false' scrollable='false' long-clickable='false' "
            "password='false' selected='false' bounds='[100,200][300,400]' />\n"
            "</hierarchy>"
        )
        h = p.parse(raw)
        assert len(h.elements) == 1
        assert h.elements[0].text == "OK"
        assert h.elements[0].resource_id == "btn"
        assert h.elements[0].center == (200, 300)

    def test_parse_settings_screen_fixture(self):
        xml_content = load_fixture("settings_screen.xml")
        parser = UIHierarchyParser()
        hierarchy = parser.parse(xml_content)

        assert hierarchy.rotation == 0
        assert len(hierarchy.elements) > 0

        # Verify key elements are extracted
        title_elem = hierarchy.find_elements_by_text("Settings", exact=True)
        assert len(title_elem) == 1
        assert title_elem[0].element_type == "Text"

        search_btn = hierarchy.find_elements_by_text("Search settings")
        assert len(search_btn) == 1
        assert search_btn[0].element_type == "Button"
        assert search_btn[0].clickable is True

        switch_elem = hierarchy.find_elements_by_resource_id("switch_widget")
        assert len(switch_elem) == 1
        assert switch_elem[0].element_type == "Switch"
        assert switch_elem[0].checkable is True
        assert switch_elem[0].checked is False

        # Verify elements are 1-based sequentially indexed
        for idx, elem in enumerate(hierarchy.elements, start=1):
            assert elem.elem_id == idx

    def test_parse_login_screen_fixture(self):
        xml_content = load_fixture("login_screen.xml")
        hierarchy = UIHierarchyParser.parse_xml(xml_content)

        assert hierarchy.rotation == 0
        # Title & Subtitle
        assert len(hierarchy.find_elements_by_text("Welcome Back!")) == 1

        # Email Input
        email_elem = hierarchy.find_elements_by_resource_id("et_email")
        assert len(email_elem) == 1
        assert email_elem[0].element_type == "Input"
        assert email_elem[0].text == "user@example.com"
        assert email_elem[0].editable is True

        # Password Input
        pw_elem = hierarchy.find_elements_by_resource_id("et_password")
        assert len(pw_elem) == 1
        assert pw_elem[0].element_type == "Input"
        assert pw_elem[0].password is True
        assert pw_elem[0].focused is True

        # Remember Me CheckBox
        cb_elem = hierarchy.find_elements_by_resource_id("cb_remember")
        assert len(cb_elem) == 1
        assert cb_elem[0].element_type == "CheckBox"
        assert cb_elem[0].checked is True

        # Sign In Button
        btn_elem = hierarchy.find_elements_by_resource_id("btn_login")
        assert len(btn_elem) == 1
        assert btn_elem[0].element_type == "Button"
        assert btn_elem[0].text == "Sign In"
        assert btn_elem[0].clickable is True

        # FAB
        fab_elem = hierarchy.find_elements_by_resource_id("fab_help")
        assert len(fab_elem) == 1
        assert fab_elem[0].content_desc == "Need help? Chat with support"

    def test_parse_dialog_screen_fixture(self):
        xml_content = load_fixture("dialog_screen.xml")
        hierarchy = UIHierarchyParser.parse_xml(xml_content)

        assert len(hierarchy.find_elements_by_text("Allow Wireless Debugging?")) == 1
        assert len(hierarchy.find_elements_by_resource_id("button1")) == 1
        assert len(hierarchy.find_elements_by_resource_id("button2")) == 1

        allow_btn = hierarchy.find_elements_by_resource_id("button1")[0]
        assert allow_btn.text == "Allow"
        assert allow_btn.focused is True
        assert allow_btn.clickable is True

        cb = hierarchy.find_elements_by_resource_id("checkbox_always")[0]
        assert cb.checked is True

    def test_parse_media_feed_screen_fixture(self):
        xml_content = load_fixture("media_feed_screen.xml")
        hierarchy = UIHierarchyParser.parse_xml(xml_content)

        # Action bar icons
        assert len(hierarchy.find_elements_by_text("Search YouTube")) == 1
        assert len(hierarchy.find_elements_by_text("Cast")) == 1

        # Feed list items
        video_titles = hierarchy.find_elements_by_resource_id("video_title")
        assert len(video_titles) == 2
        assert "Gemini 2.5 Flash Deep Dive" in video_titles[0].text
        assert "Building Android Automation Agents" in video_titles[1].text

        # Bottom bar tabs
        home_tab = hierarchy.find_elements_by_resource_id("tab_home")[0]
        assert home_tab.selected is True

    def test_parse_edge_cases_fixture(self):
        xml_content = load_fixture("edge_cases.xml")
        hierarchy = UIHierarchyParser.parse_xml(xml_content)

        assert hierarchy.rotation == 1  # Rotation from edge_cases.xml

        # 1. Zero size nodes MUST be pruned
        assert len(hierarchy.find_elements_by_resource_id("zero_size")) == 0
        assert len(hierarchy.find_elements_by_resource_id("zero_width")) == 0

        # 2. Offscreen nodes MUST be pruned
        assert len(hierarchy.find_elements_by_resource_id("offscreen_left")) == 0
        assert len(hierarchy.find_elements_by_resource_id("offscreen_top")) == 0
        assert len(hierarchy.find_elements_by_resource_id("beyond_bottom")) == 0
        assert len(hierarchy.find_elements_by_resource_id("beyond_right")) == 0

        # 3. Special characters & XML entities unescaped
        special_elem = hierarchy.find_elements_by_resource_id("special_text")
        assert len(special_elem) == 1
        assert "50% & free shipping!" in special_elem[0].text
        assert "🚀" in special_elem[0].text
        assert "<$20>" in special_elem[0].text

        # 4. RTL text intact
        arabic_elem = hierarchy.find_elements_by_resource_id("arabic_text")
        assert len(arabic_elem) == 1
        assert "مرحبا بكم في التطبيق" in arabic_elem[0].text
        assert arabic_elem[0].content_desc == "ترحيب"

        # 5. Whitespace-only node without actions should be pruned
        assert len(hierarchy.find_elements_by_resource_id("whitespace_text")) == 0
