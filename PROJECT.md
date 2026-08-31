# Project: Android Gemini Automation Agent

## Architecture
An interactive Python CLI Android automation agent powered by the Gemini API (`google-genai` SDK) and ADB UI hierarchy extraction (XML parsing) with native Android Wireless Debugging support.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Interactive Rich CLI                             │
│                     (src/android_gemini_agent/cli/app.py)                   │
│   - REPL Shell: connect, pair, status, run, dump_ui, settings, exit         │
│   - Rich Spinners, Live Panels, Formatted UI Node Inspector                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Gemini Agent Decision Engine                         │
│                    (src/android_gemini_agent/agent/loop.py)                 │
│   - google-genai SDK Client (gemini-2.5-flash)                              │
│   - Structured Tool Declarations: tap, type_text, press_key, swipe, etc.    │
│   - History Summarization & Context Pruning (<1500 tokens/turn)             │
│   - 3-Tier Infinite Loop & Oscillation Detection (loop_detector.py)         │
└──────────────────┬───────────────────────────────────────┬──────────────────┘
                   │                                       │
                   ▼                                       ▼
┌──────────────────────────────────────┐ ┌────────────────────────────────────┐
│      UI Hierarchy & XML Parser       │ │  ADB Controller & Wireless Manager │
│ (src/android_gemini_agent/parser/)   │ │ (src/android_gemini_agent/adb/)    │
│  - XML node parser & regex bounds    │ │  - AdbClientProtocol & discovery   │
│  - Center point coordinate math      │ │  - RealAdbClient & MockAdbClient   │
│  - AST container pruning (80-90%)    │ │  - Android 11+ Pairing & Connect   │
│  - Markdown / Line DSL Formatters    │ │  - Auto-reconnect & Text Escaping  │
└──────────────────────────────────────┘ └────────────────────────────────────┘
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Wireless Pairing Workflow | Android 11+ `adb pair <ip>:<port> <code>` with ephemeral port handling and error diagnostics | M1 | ORIGINAL_REQUEST §R3 |
| 2 | Wireless Connect & Disconnect | `adb connect <ip>:<port>` and `adb disconnect` with stdout exit code anomaly parsing | M1 | ORIGINAL_REQUEST §R3 |
| 3 | Auto-Reconnect on Wi-Fi Drop | Exponential backoff auto-reconnect logic upon connection drop or timeout | M1 | ORIGINAL_REQUEST §R3 |
| 4 | ADB Path Discovery | Auto-locating adb binary across standard OS SDK paths & PATH env | M1 | ORIGINAL_REQUEST §R3 |
| 5 | Touch & Gesture Commands | `tap(x, y)` at element center, directional `swipe(direction)` / scroll with screen bounds | M1 | ORIGINAL_REQUEST §R3 |
| 6 | Navigation & Hardware Keyevents | `press_key(key_name)` mapping to Android keycodes (BACK, HOME, APP_SWITCH, ENTER, etc.) | M1 | ORIGINAL_REQUEST §R3 |
| 7 | Shell Text Input & Escaping | `type_text(text)` handling spaces (%s) and shell metacharacters, with clipboard fallback | M1 | ORIGINAL_REQUEST §R3 |
| 8 | App Package Launching | Zero-config launch via `monkey -p <pkg> -c android.intent.category.LAUNCHER 1` and `am start` | M1 | ORIGINAL_REQUEST §R3 |
| 9 | Mock ADB Client & Simulator | In-memory `MockAdbClient` implementing `AdbClientProtocol` for offline simulation | M1 | ORIGINAL_REQUEST §R4 |
| 10 | UI Hierarchy Dump Pipeline | `uiautomator dump --compressed` compound single pipeline with fallback cascade | M2 | ORIGINAL_REQUEST §R1 |
| 11 | Bounds Coordinate Mathematics | Regex parsing of `bounds="[x1,y1][x2,y2]"` into numerical coordinates & center point math | M2 | ORIGINAL_REQUEST §R1 |
| 12 | Non-Actionable Container Pruning | AST pruning of empty structural wrappers while preserving interactive/informative nodes | M2 | ORIGINAL_REQUEST §R1 |
| 13 | Compact State Formatting | Markdown Table and Compact Line DSL token formatters (< 1,500 tokens per state) | M2 | ORIGINAL_REQUEST §R1 |
| 14 | Mock XML Fixtures & Edge Cases | Offline fixtures covering settings, login, dialogs, media feeds, RTL text, and unicode | M2 | ORIGINAL_REQUEST §R1 |
| 15 | Gemini Client & SDK Configuration | `google-genai` SDK v2+ initialization with `gemini-2.5-flash` and user API key | M3 | ORIGINAL_REQUEST §R2 |
| 16 | Structured Function/Tool Declarations | `types.Tool` schemas for `tap`, `type_text`, `press_key`, `swipe`, `wait`, `finish_task` | M3 | ORIGINAL_REQUEST §R2 |
| 17 | Multi-Turn Agent Decision Loop | Turn execution feeding compact UI state + action summary, dispatching tool calls | M3 | ORIGINAL_REQUEST §R2 |
| 18 | Context Pruning & History Compactor | Rolling compact action log avoiding raw XML accumulation across turns | M3 | ORIGINAL_REQUEST §R2 |
| 19 | Infinite Loop & Oscillation Detector | State hash and action signature cycle detection with prompt recovery injection | M3 | ORIGINAL_REQUEST §R2 |
| 20 | Interactive Rich REPL CLI | REPL shell with `connect`, `pair`, `status`, `run`, `dump_ui`, `settings`, `exit` commands | M4 | ORIGINAL_REQUEST §R4 |
| 21 | Rich UI Elements & Live Spinners | Visual cards, spinners for Gemini thinking and ADB execution, tabular node viewer | M4 | ORIGINAL_REQUEST §R4 |
| 22 | Graceful Interruption Handling | Safe Ctrl+C handling aborting active tasks back to REPL without crashing | M4 | ORIGINAL_REQUEST §R4 |
| 23 | Environment & Config Setup | `.env` (with user's key configured), `.env.example`, and `requirements.txt` | M4 | ORIGINAL_REQUEST §R4 |
| 24 | Documentation & Wireless Guide | Complete `README.md` with step-by-step Android Developer Options Wireless Debugging guide | M4 | ORIGINAL_REQUEST §R4 |
| 25 | E2E Offline Test Suite & Runner | Comprehensive offline test suite (Tiers 1-4) validating 100% features without hardware | M-Final | ORIGINAL_REQUEST §R4 |
| 26 | Adversarial Hardening & Audit | Tier 5 adversarial stress testing and forensic integrity validation | M-Final | Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Requirement-driven test harness, mock device runner, Tiers 1-4 tests (`TEST_READY.md`) | none | IN_PROGRESS |
| M1 | ADB Controller & Wireless Manager | Wireless pair/connect, auto-reconnect, gestures, text escaping, keyevents, MockAdbClient | none | IN_PROGRESS |
| M2 | UI Hierarchy Dump & Compact XML Parser | XML extraction pipeline, bounds regex, center math, AST container pruning, formatting | none | IN_PROGRESS |
| M3 | Gemini Decision Engine & Tool Definitions | `google-genai` SDK integration, tool schemas, agent loop, loop detector, history compactor | M1, M2 | PLANNED |
| M4 | Interactive Rich CLI & Packaging | Rich REPL CLI, spinners, table viewer, `.env`, `.env.example`, `requirements.txt`, `README.md` | M1, M2, M3 | PLANNED |
| M-Final | E2E Verification & Adversarial Hardening | Pass 100% E2E tests (Tiers 1-4), Tier 5 adversarial coverage hardening, forensic audit | E2E, M1, M2, M3, M4 | PLANNED |

## Interface Contracts

### `src/android_gemini_agent/adb` ↔ `src/android_gemini_agent/parser`
- `AdbClientProtocol.dump_ui_hierarchy(serial: str) -> str`: Returns raw XML string of current screen.
- `DeviceController.get_screen_size() -> Tuple[int, int]`: Returns `(width, height)` in pixels.
- `UIHierarchyParser.parse(xml_str: str, screen_size: Tuple[int, int]) -> UIHierarchy`: Parses XML into indexed elements with valid bounding boxes and center coordinates.

### `src/android_gemini_agent/adb` ↔ `src/android_gemini_agent/agent`
- `DeviceController.tap(x: int, y: int) -> bool`
- `DeviceController.type_text(text: str, clear_first: bool = False, press_enter: bool = False) -> bool`
- `DeviceController.press_key(key_name: str) -> bool`
- `DeviceController.swipe(direction: str, distance: str = "normal") -> bool`
- `DeviceController.wait(seconds: float) -> None`

### `src/android_gemini_agent/parser` ↔ `src/android_gemini_agent/agent`
- `UIHierarchy.to_prompt_text(format_type: str = "markdown_table") -> str`: Produces compact representation (< 1,500 tokens).
- `UIHierarchy.find_element_by_id(elem_id: int) -> Optional[UIElement]`
- `UIHierarchy.find_element_by_coords(x: int, y: int) -> Optional[UIElement]`

### `src/android_gemini_agent/agent` ↔ `src/android_gemini_agent/cli`
- `AgentEngine.run_task(task: str, on_step_callback: Optional[Callable[[AgentStep], None]] = None) -> TaskResult`
- `TaskResult`: `status: str ("SUCCESS" | "FAILURE")`, `message: str`, `steps: List[AgentStep]`, `duration_seconds: float`.

## Code Layout
```
C:/Users/humai/teamwork_projects/android_gemini_agent/
├── src/
│   └── android_gemini_agent/
│       ├── __init__.py
│       ├── adb/
│       │   ├── __init__.py
│       │   ├── models.py           # DeviceInfo, DeviceState, ConnectionResult, PairingResult, ShellResult
│       │   ├── protocol.py         # AdbClientProtocol
│       │   ├── client.py           # RealAdbClient (subprocess management, path discovery, parsers)
│       │   ├── mock_client.py      # MockAdbClient (in-memory test simulator)
│       │   ├── controller.py       # DeviceController (tap, swipe, keyevent, text, app launch, auto-reconnect)
│       │   └── text_escaper.py     # TextEscaper (space %s and shell escaping)
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── models.py           # BoundingBox, UIElement, UIHierarchy
│       │   ├── parser.py           # ElementTree parsing, bounds regex, container pruning
│       │   └── formatters.py       # Markdown table, compact line DSL, and JSON formatters
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── models.py           # AgentStep, TaskResult, ActionRecord
│       │   ├── tools.py            # google-genai FunctionDeclaration & Tool schemas
│       │   ├── loop_detector.py    # 3-tier cycle & stagnation detector
│       │   ├── compactor.py        # History compactor & prompt builder
│       │   └── loop.py             # AgentDecisionEngine (multi-turn tool-calling loop)
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── console.py          # Rich console formatting, tables, panels, spinners
│       │   └── app.py              # Interactive REPL shell & CLI entrypoint
│       └── config.py               # Settings loader (.env loading, defaults)
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Shared fixtures & mock device factories
│   ├── fixtures/                   # Realistic XML hierarchy screen dumps
│   │   ├── settings_screen.xml
│   │   ├── login_screen.xml
│   │   ├── dialog_screen.xml
│   │   ├── media_feed_screen.xml
│   │   └── edge_cases.xml
│   ├── test_adb_client.py          # Unit tests for ADB client & path discovery
│   ├── test_device_controller.py   # Unit tests for controller commands & auto-reconnect
│   ├── test_text_escaper.py        # Unit tests for shell & text escaping
│   ├── test_ui_parser.py           # Unit tests for XML parsing, bounds math, pruning
│   ├── test_formatters.py          # Unit tests for markdown/DSL token formatters
│   ├── test_agent_tools.py         # Unit tests for tool schemas & parameters
│   ├── test_loop_detector.py       # Unit tests for loop & oscillation detection
│   ├── test_agent_engine.py        # Unit & mock integration tests for agent loop
│   ├── test_cli.py                 # Unit tests for REPL commands & graceful exit
│   └── test_e2e_scenarios.py       # Tier 1-4 comprehensive offline test scenarios
├── .env
├── .env.example
├── requirements.txt
├── README.md
└── pyproject.toml
```
