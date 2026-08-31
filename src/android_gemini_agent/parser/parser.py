"""
UI Hierarchy XML Parser
Parses Android UiAutomator XML dumps, extracts bounds, simplifies widget classes,
prunes non-actionable layout containers, and generates structured UIHierarchy objects.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from .models import BoundingBox, UIElement, UIHierarchy

# Widget class simplification mapping
CLASS_SIMPLIFICATION_MAP: Dict[str, str] = {
    "android.widget.TextView": "Text",
    "android.widget.EditText": "Input",
    "android.widget.AutoCompleteTextView": "Input",
    "android.widget.ExtractEditText": "Input",
    "android.widget.Button": "Button",
    "android.widget.ImageButton": "Button",
    "android.widget.ImageView": "Icon",
    "android.widget.CheckBox": "CheckBox",
    "android.widget.RadioButton": "RadioButton",
    "android.widget.Switch": "Switch",
    "android.widget.ToggleButton": "Switch",
    "androidx.appcompat.widget.SwitchCompat": "Switch",
    "androidx.recyclerview.widget.RecyclerView": "List",
    "android.widget.ListView": "List",
    "android.widget.GridView": "List",
    "android.widget.ScrollView": "ScrollView",
    "android.widget.HorizontalScrollView": "ScrollView",
    "androidx.core.widget.NestedScrollView": "ScrollView",
    "android.webkit.WebView": "WebView",
    "android.widget.ProgressBar": "ProgressBar",
    "android.widget.SeekBar": "SeekBar",
    "android.widget.Spinner": "Dropdown",
}


class UIHierarchyParser:
    """Parser for Android UiAutomator XML hierarchies with token-optimizing AST pruning."""

    def __init__(self, default_screen_size: Tuple[int, int] = (1080, 2400)):
        self.default_screen_size = default_screen_size

    @staticmethod
    def simplify_class(class_name: str) -> str:
        """Simplifies full Android widget class name into concise human-readable element type."""
        if not class_name:
            return "View"
        if class_name in CLASS_SIMPLIFICATION_MAP:
            return CLASS_SIMPLIFICATION_MAP[class_name]
        # Fallback to simple class name
        if "." in class_name:
            return class_name.split(".")[-1]
        return class_name

    @staticmethod
    def clean_resource_id(resource_id: str) -> str:
        """Strips package prefix from resource-id (e.g., com.app:id/btn -> btn)."""
        if not resource_id:
            return ""
        if ":id/" in resource_id:
            return resource_id.split(":id/")[-1]
        if "/" in resource_id:
            return resource_id.split("/")[-1]
        return resource_id

    @staticmethod
    def parse_bounds(bounds_str: str) -> Optional[BoundingBox]:
        """Parses bounds string [x1,y1][x2,y2] into a BoundingBox."""
        return BoundingBox.from_str(bounds_str)

    def parse(
        self, xml_str: str, screen_size: Optional[Tuple[int, int]] = None
    ) -> UIHierarchy:
        """
        Parses raw UiAutomator XML into a pruned, indexed UIHierarchy.

        Args:
            xml_str: Raw XML string from UiAutomator dump.
            screen_size: Tuple (width, height) of the device screen.

        Returns:
            UIHierarchy instance containing pruned and indexed UIElements.
        """
        resolved_screen_size = screen_size or self.default_screen_size
        screen_w, screen_h = resolved_screen_size

        if not xml_str or not xml_str.strip():
            return UIHierarchy(
                elements=[],
                rotation=0,
                screen_size=resolved_screen_size,
                raw_xml=xml_str or "",
            )

        # Strip any extraneous terminal preamble before XML header
        cleaned_xml = xml_str.strip()
        idx_xml = cleaned_xml.find("<?xml")
        if idx_xml != -1:
            cleaned_xml = cleaned_xml[idx_xml:]
        else:
            idx_hier = cleaned_xml.find("<hierarchy")
            if idx_hier != -1:
                cleaned_xml = cleaned_xml[idx_hier:]

        try:
            root = ET.fromstring(cleaned_xml)
        except ET.ParseError:
            # Fallback for malformed XML: return empty hierarchy
            return UIHierarchy(
                elements=[],
                rotation=0,
                screen_size=resolved_screen_size,
                raw_xml=xml_str,
            )

        rotation = 0
        if root.tag == "hierarchy":
            try:
                rotation = int(root.attrib.get("rotation", "0"))
            except ValueError:
                rotation = 0

        elements: List[UIElement] = []
        elem_counter = 1

        def traverse(node: ET.Element):
            nonlocal elem_counter

            bounds_str = node.attrib.get("bounds", "")
            bbox = self.parse_bounds(bounds_str)

            if bbox and bbox.is_visible(screen_w, screen_h):
                node_class = node.attrib.get("class", "")
                elem_type = self.simplify_class(node_class)
                raw_text = node.attrib.get("text", "")
                raw_desc = node.attrib.get("content-desc", "")
                res_id = self.clean_resource_id(node.attrib.get("resource-id", ""))
                pkg = node.attrib.get("package", "")

                clickable = node.attrib.get("clickable", "false").lower() == "true"
                scrollable = node.attrib.get("scrollable", "false").lower() == "true"
                checkable = node.attrib.get("checkable", "false").lower() == "true"
                checked = node.attrib.get("checked", "false").lower() == "true"
                enabled = node.attrib.get("enabled", "true").lower() == "true"
                focused = node.attrib.get("focused", "false").lower() == "true"
                password = node.attrib.get("password", "false").lower() == "true"
                selected = node.attrib.get("selected", "false").lower() == "true"
                focusable = node.attrib.get("focusable", "false").lower() == "true"
                long_clickable = (
                    node.attrib.get("long-clickable", "false").lower() == "true"
                )

                # Editable detection: either EditText class or explicit editable flag
                is_editable = (
                    elem_type == "Input"
                    or "EditText" in node_class
                    or node.attrib.get("editable", "false").lower() == "true"
                )

                elem = UIElement(
                    elem_id=elem_counter,
                    node_class=node_class,
                    element_type=elem_type,
                    resource_id=res_id,
                    text=raw_text,
                    content_desc=raw_desc,
                    package=pkg,
                    bounds=bbox,
                    center=bbox.center,
                    clickable=clickable,
                    scrollable=scrollable,
                    editable=is_editable,
                    checkable=checkable,
                    checked=checked,
                    enabled=enabled,
                    focused=focused,
                    password=password,
                    selected=selected,
                    focusable=focusable,
                    long_clickable=long_clickable,
                )

                # AST Pruning: Only retain actionable or informative elements
                if elem.is_significant(screen_w, screen_h):
                    elements.append(elem)
                    elem_counter += 1

            for child in node:
                traverse(child)

        traverse(root)

        return UIHierarchy(
            elements=elements,
            rotation=rotation,
            screen_size=resolved_screen_size,
            raw_xml=xml_str,
        )

    @classmethod
    def parse_xml(
        cls, xml_str: str, screen_size: Tuple[int, int] = (1080, 2400)
    ) -> UIHierarchy:
        """Convenience classmethod to parse an XML string without manually instantiating parser."""
        return cls(default_screen_size=screen_size).parse(
            xml_str, screen_size=screen_size
        )
