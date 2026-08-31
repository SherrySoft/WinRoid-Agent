"""
Windows UI Hierarchy extractor and parser.
Traverses Windows UIAutomation trees and generates compact UIHierarchy representations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    import uiautomation as auto
    HAS_UIAUTOMATION = True
except ImportError:
    HAS_UIAUTOMATION = False

from ..parser.models import BoundingBox, UIElement, UIHierarchy

logger = logging.getLogger(__name__)


class WindowsUIParser:
    """Extracts and compresses Windows desktop UI element trees into token-efficient UIHierarchy objects."""

    # Controls considered actionable / interactive by default
    ACTIONABLE_TYPES = {
        "ButtonControl",
        "EditControl",
        "CheckBoxControl",
        "RadioButtonControl",
        "ComboBoxControl",
        "MenuItemControl",
        "HyperlinkControl",
        "ListItemControl",
        "TabItemControl",
        "TreeItemControl",
        "SplitButtonControl",
    }

    # Controls considered informative (labels, values, headers, dialogs)
    INFORMATIVE_TYPES = {
        "TextControl",
        "HeaderItemControl",
        "StatusBarControl",
        "TitleBarControl",
        "ProgressBarControl",
        "ImageControl",
        "DocumentControl",
        "WindowControl",
        "PaneControl",
        "GroupControl",
        "ToolTipControl",
    }

    def __init__(self, max_depth: int = 8, max_elements: int = 120):
        self.max_depth = max_depth
        self.max_elements = max_elements

    def extract_hierarchy(self, root_control: Optional[Any] = None) -> UIHierarchy:
        """
        Extracts visible, interactive and informative controls from the active window,
        modal error dialogs, or root desktop.
        """
        elements: List[UIElement] = []
        if not HAS_UIAUTOMATION:
            return UIHierarchy(elements=[])

        try:
            target = root_control or auto.GetForegroundControl() or auto.GetRootControl()
            if not target:
                return UIHierarchy(elements=[])

            self._traverse_control(target, depth=0, elements=elements)

            # If target is small or active window has few controls, also inspect top-level popup dialogs
            if len(elements) < 15 and not root_control:
                try:
                    root = auto.GetRootControl()
                    for child in root.GetChildren():
                        if child and child != target and getattr(child, "Name", "") and not getattr(child, "IsOffscreen", False):
                            c_type = getattr(child, "ControlTypeName", "")
                            if c_type in ("WindowControl", "PaneControl") and getattr(child, "BoundingRectangle", None):
                                self._traverse_control(child, depth=0, elements=elements)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning(f"Error during Windows UI extraction: {exc}")

        return UIHierarchy(elements=elements[:self.max_elements])

    def _traverse_control(self, control: Any, depth: int, elements: List[UIElement]) -> None:
        if depth > self.max_depth or len(elements) >= self.max_elements:
            return

        try:
            # Check bounding rectangle
            rect = getattr(control, "BoundingRectangle", None)
            if not rect or rect.width() <= 0 or rect.height() <= 0:
                pass
            else:
                name = getattr(control, "Name", "") or ""
                ctrl_type = getattr(control, "ControlTypeName", "Control")
                class_name = getattr(control, "ClassName", "") or ""
                auto_id = getattr(control, "AutomationId", "") or ""
                is_enabled = getattr(control, "IsEnabled", True)
                is_visible = getattr(control, "IsOffscreen", False) is False

                # Value pattern if available
                value = ""
                try:
                    val_pattern = control.GetValuePattern()
                    if val_pattern:
                        value = val_pattern.Value
                except Exception:
                    pass

                text_content = name if not value else f"{name} ({value})" if name else value

                # Determine if element should be kept
                is_actionable = ctrl_type in self.ACTIONABLE_TYPES
                is_informative = ctrl_type in self.INFORMATIVE_TYPES and bool(text_content.strip())

                if (is_actionable or is_informative) and is_visible and is_enabled:
                    x1 = max(0, rect.left)
                    y1 = max(0, rect.top)
                    x2 = max(0, rect.right)
                    y2 = max(0, rect.bottom)
                    bounds = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

                    element = UIElement(
                        elem_id=len(elements) + 1,
                        node_class=class_name or ctrl_type,
                        element_type=ctrl_type.replace("Control", "") or "Control",
                        resource_id=auto_id,
                        text=text_content.strip(),
                        content_desc=class_name,
                        package="windows",
                        bounds=bounds,
                        center=bounds.center,
                        clickable=is_actionable,
                        scrollable=(ctrl_type in ("ScrollBarControl", "ListControl", "TreeControl")),
                        editable=(ctrl_type == "EditControl"),
                        enabled=is_enabled,
                        focused=getattr(control, "HasKeyboardFocus", False),
                        selected=getattr(control, "IsSelected", False),
                        password=getattr(control, "IsPassword", False),
                    )
                    elements.append(element)

            # Traverse children
            children = getattr(control, "GetChildren", lambda: [])()
            for child in children:
                self._traverse_control(child, depth + 1, elements)
        except Exception:
            return
