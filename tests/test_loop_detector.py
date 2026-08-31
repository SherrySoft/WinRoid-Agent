"""
Unit & Integration Tests for 3-Tier Infinite Loop and Stagnation Detection.
Validates Tier 1 (identical action repetition), Tier 2 (stagnant screen state),
Tier 3 (multi-step action and state oscillation), warning prompt injection, and recovery logic.
"""

from __future__ import annotations

import pytest

from android_gemini_agent.agent.loop_detector import LoopDetector
from android_gemini_agent.parser.models import UIHierarchy
from android_gemini_agent.parser.parser import UIHierarchyParser


class TestLoopDetector:
    """Tests for 3-Tier LoopDetector."""

    def test_compute_state_hash_deterministic(
        self, ui_parser: UIHierarchyParser, settings_xml: str, dialog_xml: str
    ):
        h1 = ui_parser.parse(settings_xml)
        h2 = ui_parser.parse(settings_xml)
        h_dialog = ui_parser.parse(dialog_xml)

        detector = LoopDetector()
        hash1 = detector.compute_state_hash(h1)
        hash2 = detector.compute_state_hash(h2)
        hash_dlg = detector.compute_state_hash(h_dialog)

        assert hash1 == hash2
        assert hash1 != hash_dlg
        assert len(hash1) == 32  # Standard MD5 hex length

    def test_tier1_identical_action_repetition(
        self, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        hierarchy = ui_parser.parse(settings_xml)
        detector = LoopDetector(threshold=3, max_warnings=2)

        # Step 1
        r1 = detector.record_step("tap", {"x": 500, "y": 500}, hierarchy)
        assert r1.detected is False
        assert detector.consecutive_loop_count == 0

        # Step 2
        r2 = detector.record_step("tap", {"x": 500, "y": 500}, hierarchy)
        assert r2.detected is False

        # Step 3 -> 3rd identical action triggers Tier 1 warning
        r3 = detector.record_step("tap", {"x": 500, "y": 500}, hierarchy)
        assert r3.detected is True
        assert r3.tier == 1
        assert "Tier 1" in r3.reason
        assert r3.warning_level == 1
        assert r3.should_abort is False
        assert "⚠️ WARNING" in r3.injection_prompt

        # Step 4 -> 4th identical action (warning level 2)
        r4 = detector.record_step("tap", {"x": 500, "y": 500}, hierarchy)
        assert r4.detected is True
        assert r4.warning_level == 2
        assert r4.should_abort is False

        # Step 5 -> 5th identical action (consecutive count 3 > max_warnings 2 -> should_abort)
        r5 = detector.record_step("tap", {"x": 500, "y": 500}, hierarchy)
        assert r5.detected is True
        assert r5.should_abort is True

    def test_tier1_wait_does_not_trigger_action_loop(
        self, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        hierarchy = ui_parser.parse(settings_xml)
        detector = LoopDetector(threshold=3)

        for _ in range(4):
            r = detector.record_step("wait", {"seconds": 1.0}, hierarchy)
            assert r.detected is False

    def test_tier2_stagnant_screen_state(
        self, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        hierarchy = ui_parser.parse(settings_xml)
        detector = LoopDetector(threshold=3)

        # 3 non-wait actions that result in the same screen state
        r1 = detector.record_step("press_key", {"key_name": "VOLUME_UP"}, hierarchy)
        assert r1.detected is False

        r2 = detector.record_step("press_key", {"key_name": "VOLUME_UP"}, hierarchy)
        assert r2.detected is False

        r3 = detector.record_step("press_key", {"key_name": "VOLUME_UP"}, hierarchy)
        assert r3.detected is True
        # Either Tier 1 (identical action) or Tier 2 (stagnant state)
        assert r3.tier in (1, 2)

    def test_tier3_two_step_action_oscillation(
        self, ui_parser: UIHierarchyParser, settings_xml: str, dialog_xml: str
    ):
        h_set = ui_parser.parse(settings_xml)
        h_dlg = ui_parser.parse(dialog_xml)
        detector = LoopDetector(threshold=3)

        # Oscillating pattern: tap(A) -> press_key(BACK) -> tap(A) -> press_key(BACK)
        detector.record_step("tap", {"x": 100, "y": 200}, h_set)
        detector.record_step("press_key", {"key_name": "BACK"}, h_dlg)
        detector.record_step("tap", {"x": 100, "y": 200}, h_set)
        r4 = detector.record_step("press_key", {"key_name": "BACK"}, h_dlg)

        assert r4.detected is True
        assert r4.tier == 3
        assert "2-step" in r4.reason
        assert "⚠️ WARNING" in r4.injection_prompt

    def test_tier3_three_step_action_oscillation(
        self, ui_parser: UIHierarchyParser, settings_xml: str
    ):
        h = ui_parser.parse(settings_xml)
        detector = LoopDetector(threshold=3)

        # 3-step cycle: A (tap) -> B (swipe) -> C (press_key) -> A -> B -> C
        detector.record_step("tap", {"x": 10, "y": 10}, h)
        detector.record_step("swipe", {"direction": "up"}, h)
        detector.record_step("press_key", {"key_name": "BACK"}, h)
        detector.record_step("tap", {"x": 10, "y": 10}, h)
        detector.record_step("swipe", {"direction": "up"}, h)
        r6 = detector.record_step("press_key", {"key_name": "BACK"}, h)

        assert r6.detected is True
        assert r6.tier == 3
        assert "3-step" in r6.reason

    def test_tier3_state_oscillation(
        self, ui_parser: UIHierarchyParser, settings_xml: str, dialog_xml: str
    ):
        h_set = ui_parser.parse(settings_xml)
        h_dlg = ui_parser.parse(dialog_xml)
        detector = LoopDetector(threshold=3)

        # Different actions, but alternating between State A and State B
        detector.record_step("tap", {"x": 100, "y": 100}, h_set)
        detector.record_step("tap", {"x": 200, "y": 200}, h_dlg)
        detector.record_step("swipe", {"direction": "up"}, h_set)
        r4 = detector.record_step("swipe", {"direction": "down"}, h_dlg)

        assert r4.detected is True
        assert r4.tier == 3
        assert "oscillation" in r4.reason.lower()

    def test_breaking_loop_resets_consecutive_counter(
        self, ui_parser: UIHierarchyParser, settings_xml: str, dialog_xml: str
    ):
        h_set = ui_parser.parse(settings_xml)
        h_dlg = ui_parser.parse(dialog_xml)
        detector = LoopDetector(threshold=3)

        # 3 identical taps -> triggers loop warning
        detector.record_step("tap", {"x": 500, "y": 500}, h_set)
        detector.record_step("tap", {"x": 500, "y": 500}, h_set)
        r3 = detector.record_step("tap", {"x": 500, "y": 500}, h_set)
        assert r3.detected is True
        assert detector.consecutive_loop_count == 1

        # Break loop with a different action on a new screen
        r4 = detector.record_step("swipe", {"direction": "up"}, h_dlg)
        assert r4.detected is False
        assert detector.consecutive_loop_count == 0

    def test_detector_reset(self, ui_parser: UIHierarchyParser, settings_xml: str):
        h = ui_parser.parse(settings_xml)
        detector = LoopDetector(threshold=3)

        detector.record_step("tap", {"x": 500, "y": 500}, h)
        detector.record_step("tap", {"x": 500, "y": 500}, h)
        assert len(detector.action_history) == 2

        detector.reset()
        assert len(detector.action_history) == 0
        assert len(detector.action_records) == 0
        assert len(detector.state_hashes) == 0
        assert detector.consecutive_loop_count == 0
        assert detector.warnings_issued == 0
