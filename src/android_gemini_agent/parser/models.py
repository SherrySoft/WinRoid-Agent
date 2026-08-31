"""
UI Hierarchy Data Models
Defines BoundingBox, UIElement, and UIHierarchy for parsed Android UI hierarchies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

BOUNDS_PATTERN = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


@dataclass(frozen=True)
class BoundingBox:
    """Represents rectangular screen coordinates [x1, y1][x2, y2]."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Width in pixels (non-negative)."""
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        """Height in pixels (non-negative)."""
        return max(0, self.y2 - self.y1)

    @property
    def center_x(self) -> int:
        """Center X coordinate."""
        return (self.x1 + self.x2) // 2

    @property
    def center_y(self) -> int:
        """Center Y coordinate."""
        return (self.y1 + self.y2) // 2

    @property
    def center(self) -> Tuple[int, int]:
        """Calculates center point ((x1+x2)//2, (y1+y2)//2)."""
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def area(self) -> int:
        """Area in square pixels."""
        return self.width * self.height

    def is_visible(self, screen_w: int = 1080, screen_h: int = 2400) -> bool:
        """Checks if the bounding box has non-zero area and is within the screen bounds."""
        if self.width <= 0 or self.height <= 0:
            return False
        # If completely off-screen
        if self.x2 <= 0 or self.y2 <= 0 or self.x1 >= screen_w or self.y1 >= screen_h:
            return False
        return True

    def contains_point(self, x: int, y: int) -> bool:
        """Checks if a point (x, y) falls within the bounding box (inclusive)."""
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    @classmethod
    def from_str(cls, bounds_str: str) -> Optional[BoundingBox]:
        """Parses a bounds string format '[x1,y1][x2,y2]' into a BoundingBox."""
        if not bounds_str:
            return None
        match = BOUNDS_PATTERN.match(bounds_str.strip())
        if not match:
            return None
        x1, y1, x2, y2 = map(int, match.groups())
        return cls(x1=x1, y1=y1, x2=x2, y2=y2)

    def to_dict(self) -> Dict[str, Any]:
        """Converts BoundingBox to dictionary representation."""
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "width": self.width,
            "height": self.height,
            "center": list(self.center),
            "area": self.area,
        }

    def __str__(self) -> str:
        return f"[{self.x1},{self.y1}][{self.x2},{self.y2}]"

    def __repr__(self) -> str:
        return f"BoundingBox([{self.x1},{self.y1}][{self.x2},{self.y2}])"


@dataclass
class UIElement:
    """Represents a simplified, actionable, or informative UI node extracted from hierarchy."""

    elem_id: int
    node_class: str
    element_type: str
    resource_id: str
    text: str
    content_desc: str
    package: str
    bounds: BoundingBox
    center: Tuple[int, int]
    clickable: bool = False
    scrollable: bool = False
    editable: bool = False
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    focused: bool = False
    password: bool = False
    selected: bool = False
    focusable: bool = False
    long_clickable: bool = False

    def is_actionable(self) -> bool:
        """Returns True if the element accepts user interactions."""
        return (
            self.clickable
            or self.scrollable
            or self.checkable
            or self.editable
            or self.password
            or self.long_clickable
        )

    def is_informative(self) -> bool:
        """Returns True if the element contains meaningful text or content description."""
        return bool(self.text.strip() or self.content_desc.strip())

    def is_significant(self, screen_w: int = 1080, screen_h: int = 2400) -> bool:
        """Returns True if element is visible and either actionable or informative."""
        return self.bounds.is_visible(screen_w, screen_h) and (
            self.is_actionable() or self.is_informative()
        )

    def label(self) -> str:
        """Returns a formatted display label combining text and content description."""
        t = self.text.strip()
        d = self.content_desc.strip()
        if t and d:
            if t == d:
                return f'"{t}"'
            return f'"{t}" (desc: "{d}")'
        if t:
            return f'"{t}"'
        if d:
            return f'desc: "{d}"'
        return '""'

    def get_display_label(self) -> str:
        """Alias for label()."""
        return self.label()

    def properties(self) -> str:
        """Returns a comma-separated summary of active element flags/properties."""
        props: List[str] = []
        if self.clickable:
            props.append("clickable")
        if self.editable:
            props.append("editable")
        if self.scrollable:
            props.append("scrollable")
        if self.checkable:
            props.append(f"checked={self.checked}")
        if self.focused:
            props.append("focused")
        if self.password:
            props.append("password")
        if not self.enabled:
            props.append("disabled")
        if self.selected:
            props.append("selected")
        return ", ".join(props) if props else "view"

    def get_properties_summary(self) -> str:
        """Alias for properties()."""
        return self.properties()

    def to_dict(self) -> Dict[str, Any]:
        """Converts UIElement to dictionary representation."""
        data: Dict[str, Any] = {
            "id": self.elem_id,
            "type": self.element_type,
            "node_class": self.node_class,
            "package": self.package,
            "bounds": [self.bounds.x1, self.bounds.y1, self.bounds.x2, self.bounds.y2],
            "center": list(self.center),
        }
        if self.text:
            data["text"] = self.text
        if self.content_desc:
            data["content_desc"] = self.content_desc
        if self.resource_id:
            data["resource_id"] = self.resource_id
        if self.clickable:
            data["clickable"] = True
        if self.scrollable:
            data["scrollable"] = True
        if self.editable:
            data["editable"] = True
        if self.checkable:
            data["checkable"] = True
            data["checked"] = self.checked
        if not self.enabled:
            data["enabled"] = False
        if self.focused:
            data["focused"] = True
        if self.password:
            data["password"] = True
        if self.selected:
            data["selected"] = True
        return data


@dataclass
class UIHierarchy:
    """Encapsulates a parsed UI hierarchy with search and export capabilities."""

    elements: List[UIElement] = field(default_factory=list)
    rotation: int = 0
    screen_size: Tuple[int, int] = (1080, 2400)
    raw_xml: str = ""

    def find_element_by_id(self, elem_id: int) -> Optional[UIElement]:
        """Finds element by 1-based sequential element ID."""
        for elem in self.elements:
            if elem.elem_id == elem_id:
                return elem
        return None

    def find_element_by_coords(self, x: int, y: int) -> Optional[UIElement]:
        """Finds the most specific element (smallest area) containing the coordinates (x, y)."""
        matching: List[UIElement] = [
            elem for elem in self.elements if elem.bounds.contains_point(x, y)
        ]
        if not matching:
            return None
        # Sort by area ascending; if tie, last in document order (innermost leaf) wins
        matching.sort(key=lambda elem: elem.bounds.area)
        min_area = matching[0].bounds.area
        candidates = [elem for elem in matching if elem.bounds.area == min_area]
        return candidates[-1]

    def find_elements_by_text(
        self, query: str, exact: bool = False, case_sensitive: bool = False
    ) -> List[UIElement]:
        """Finds elements whose text or content description matches the query."""
        results: List[UIElement] = []
        q = query if case_sensitive else query.lower()

        for elem in self.elements:
            t = elem.text if case_sensitive else elem.text.lower()
            d = elem.content_desc if case_sensitive else elem.content_desc.lower()

            if exact:
                if (t and t == q) or (d and d == q):
                    results.append(elem)
            else:
                if (t and q in t) or (d and q in d):
                    results.append(elem)
        return results

    def find_elements_by_resource_id(
        self, resource_id: str, exact: bool = True
    ) -> List[UIElement]:
        """Finds elements by resource ID (supports short ID or full package:id/name)."""
        results: List[UIElement] = []
        target = resource_id.split(":id/")[-1] if ":id/" in resource_id else resource_id

        for elem in self.elements:
            elem_res = elem.resource_id
            if exact:
                if elem_res == target or elem_res == resource_id:
                    results.append(elem)
            else:
                if target in elem_res or resource_id in elem_res:
                    results.append(elem)
        return results

    def to_prompt_text(self, format_type: str = "markdown_table") -> str:
        """Formats the UI hierarchy into a compact string representation for LLM prompts."""
        from .formatters import format_json, format_line_dsl, format_markdown_table

        fmt = format_type.lower().strip()
        if fmt in ("markdown_table", "table", "markdown"):
            return format_markdown_table(self)
        elif fmt in ("line_dsl", "dsl", "compact"):
            return format_line_dsl(self)
        elif fmt in ("json", "compact_json"):
            return format_json(self)
        else:
            raise ValueError(
                f"Unknown format_type '{format_type}'. Expected 'markdown_table', 'line_dsl', or 'json'."
            )

    def to_markdown_table(self) -> str:
        """Convenience method for markdown table export."""
        return self.to_prompt_text("markdown_table")

    def to_line_dsl(self) -> str:
        """Convenience method for Line DSL export."""
        return self.to_prompt_text("line_dsl")

    def to_json(self, indent: Optional[int] = None) -> str:
        """Convenience method for JSON export."""
        from .formatters import format_json

        return format_json(self, indent=indent)

    def __len__(self) -> int:
        return len(self.elements)

    def __iter__(self) -> Iterator[UIElement]:
        return iter(self.elements)

    def __getitem__(self, index: int) -> UIElement:
        return self.elements[index]
