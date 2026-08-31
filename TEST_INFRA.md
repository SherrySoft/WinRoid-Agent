# E2E Test Infra: Android Gemini Automation Agent

## Test Philosophy
- Opaque-box, requirement-driven testing.
- Offline execution without requiring a physical Android device or active internet connection.
- In-memory mock device simulation and mocked Gemini API responses.
- Methodology: Category-Partition + Boundary Value Analysis (BVA) + Pairwise Combinatorial Testing + Real-World Workload Scenarios.

## Feature Inventory Mapping
| # | Feature | Source | Tier 1 (Coverage) | Tier 2 (Boundary) | Tier 3 (Cross-Feature) | Tier 4 (Real-World) |
|---|---------|--------|:-----------------:|:-----------------:|:----------------------:|:-------------------:|
| 1 | Wireless Pairing Workflow | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 2 | Wireless Connect & Disconnect | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 3 | Auto-Reconnect on Wi-Fi Drop | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 4 | ADB Path Discovery | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 5 | Touch & Gesture Commands | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 6 | Navigation & Keyevents | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 7 | Shell Text Input & Escaping | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 8 | App Launching | ORIGINAL_REQUEST §R3 | ≥5 | ≥5 | ✓ | ✓ |
| 9 | Mock ADB Client | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| 10 | UI Hierarchy Dump Pipeline | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| 11 | Bounds Coordinate Mathematics | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| 12 | Container Pruning Algorithm | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| 13 | Compact State Formatting | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| 14 | Mock XML Screen Fixtures | ORIGINAL_REQUEST §R1 | ≥5 | ≥5 | ✓ | ✓ |
| 15 | Gemini Client Configuration | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| 16 | Function/Tool Declarations | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| 17 | Multi-Turn Agent Loop | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| 18 | History Pruning & Token Budget | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| 19 | Loop & Stagnation Detection | ORIGINAL_REQUEST §R2 | ≥5 | ≥5 | ✓ | ✓ |
| 20 | Interactive Rich REPL CLI | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| 21 | Rich UI Panels & Spinners | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| 22 | Graceful Interruption (Ctrl+C)| ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| 23 | Environment & Config Loading | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |
| 24 | Documentation & Setup Guide | ORIGINAL_REQUEST §R4 | ≥5 | ≥5 | ✓ | ✓ |

## Test Architecture
- Test Runner: `pytest` executed against `tests/` directory.
- Mock Environment:
  - `MockAdbClient` simulating ADB wireless states, shell outputs, and UI hierarchy dumps.
  - Mock Gemini Client simulating `google-genai` multi-turn conversation and function calls.
- XML Fixtures: `tests/fixtures/` containing realistic mobile layouts.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Expected Outcome |
|---|----------|--------------------|------------------|
| 1 | Connect to Device & Open Settings Dark Mode | F1, F2, F5, F8, F10, F11, F12, F16, F17 | Agent launches Settings, scrolls to Display, taps Dark Theme, finishes with SUCCESS |
| 2 | Wi-Fi Drop Recovery During Multi-Step Task | F2, F3, F5, F17, F19 | ADB drops on step 2, auto-reconnect restores connection without agent aborting |
| 3 | Text Search with Special Characters | F5, F7, F10, F11, F16, F17 | Taps search bar, types complex query `"Gemini 2.5 & Android"`, presses ENTER |
| 4 | Infinite Loop Detection & Recovery | F16, F17, F18, F19 | Model repeats same tap 3 times -> detector triggers warning -> agent tries scroll or exits |
| 5 | Complete CLI REPL Session | F1, F2, F9, F20, F21, F22, F23 | User pairs device, connects, dumps UI, runs natural language task, exits cleanly |

## Coverage Thresholds
- Tier 1: Feature Coverage (≥ 5 per feature)
- Tier 2: Boundary & Corner Cases (≥ 5 per feature)
- Tier 3: Cross-Feature Combinations (pairwise interactions)
- Tier 4: Real-World Scenarios (≥ 5 scenarios)
- Target: 100% test pass rate with exit code 0.
