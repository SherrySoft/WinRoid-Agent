"""
UI Hierarchy State Formatters
Provides Markdown Table, Compact Line DSL, and JSON formatters optimized for LLM token efficiency.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .models import UIHierarchy


def estimate_tokens(text: str) -> int:
    """Heuristic token estimator (approx 4 chars / 0.75 words per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def format_markdown_table(hierarchy: UIHierarchy) -> str:
    """Formats UIHierarchy as a structured Markdown table."""
    lines: List[str] = [
        "| ID | Type | Label / Text | Resource ID | Center (X,Y) | Properties |",
        "|:---|:---|:---|:---|:---|:---|",
    ]

    if not hierarchy.elements:
        lines.append("| - | - | (empty screen) | - | - | - |")
        return "\n".join(lines)

    for elem in hierarchy.elements:
        label = elem.label().replace("|", "\\|").replace("\r", "").replace("\n", " ")
        res_id = elem.resource_id.replace("|", "\\|")
        props = elem.properties().replace("|", "\\|")
        cx, cy = elem.center

        lines.append(
            f"| [{elem.elem_id}] | {elem.element_type} | {label} | {res_id} | ({cx}, {cy}) | {props} |"
        )

    return "\n".join(lines)


def format_line_dsl(hierarchy: UIHierarchy) -> str:
    """Formats UIHierarchy as ultra token-efficient single-line DSL."""
    if not hierarchy.elements:
        return "(empty screen)"

    lines: List[str] = []
    for elem in hierarchy.elements:
        parts: List[str] = [f"[{elem.elem_id}] {elem.element_type}"]
        label = elem.label().replace("\r", "").replace("\n", " ")
        if label and label != '""':
            parts.append(label)
        if elem.resource_id:
            parts.append(f"id={elem.resource_id}")
        cx, cy = elem.center
        parts.append(f"pos=({cx},{cy})")
        props = elem.properties()
        if props and props != "view":
            parts.append(f"[{props}]")

        lines.append(" ".join(parts))

    return "\n".join(lines)


def format_json(hierarchy: UIHierarchy, indent: Optional[int] = None) -> str:
    """Formats UIHierarchy as a structured JSON string."""
    payload: Dict[str, Any] = {
        "rotation": hierarchy.rotation,
        "screen_size": list(hierarchy.screen_size),
        "element_count": len(hierarchy.elements),
        "elements": [elem.to_dict() for elem in hierarchy.elements],
    }
    if indent is not None:
        return json.dumps(payload, indent=indent, ensure_ascii=False)
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
