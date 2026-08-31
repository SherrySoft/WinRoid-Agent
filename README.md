# 🤖 WinRoid-Agent: Autonomous Android & Windows Gemini Automation Engine

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/SherrySoft/WinRoid-Agent?style=social)](https://github.com/SherrySoft/WinRoid-Agent)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Gemini API](https://img.shields.io/badge/Gemini_API-google--genai_v2.0%2B-4285F4?logo=google&logoColor=white)](https://ai.google.dev/)
[![Platforms](https://img.shields.io/badge/Platforms-Android%20%7C%20Windows-0078D6?logo=windows&logoColor=white)](https://github.com/SherrySoft/WinRoid-Agent)
[![Tests Passing](https://img.shields.io/badge/Tests-255%2F255%20Passed-brightgreen.svg?logo=pytest&logoColor=white)](tests/)
[![CI Status](https://img.shields.io/badge/CI-Passing-brightgreen?logo=github-actions&logoColor=white)](https://github.com/SherrySoft/WinRoid-Agent/actions)
[![UI Engine](https://img.shields.io/badge/UI-Rich_Terminal-magenta.svg?logo=gnometerminal&logoColor=white)](https://github.com/Textualize/rich)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/Code_Style-Black-000000.svg)](https://github.com/psf/black)

**Visionless, token-optimized, high-performance autonomous GUI agent for Android phones and Windows desktops powered by Google Gemini 2.5/3.5 models and native OS accessibility hierarchies.**

[Key Features](#-key-features) •
[Architecture](#-system-architecture) •
[Visionless vs VLM](#-visionless-fast-path-vs-multimodal-vlm) •
[Quickstart](#-quickstart-guide) •
[Android Setup](#-android-wireless-setup-android-11) •
[Windows Setup](#-windows-desktop-automation-setup) •
[REPL Cheat Sheet](#-interactive-repl--cli-cheat-sheet) •
[Rate Limits & Quota](#-rate-limit--quota-resilience) •
[Troubleshooting](#-troubleshooting--faq) •
[Contributing](#-contributing--community)

</div>

---

## 💡 Overview

Most modern GUI agents rely on **Multimodal Vision-Language Models (VLMs)**: streaming full-resolution screenshots every turn, consuming 2,000–4,000+ tokens per step, incurring 3–6 second network latencies, and burning through API rate limits in a handful of turns.

**WinRoid-Agent** takes a radically faster, cheaper, and more accurate approach:

1. **Native Accessibility Extraction**: Directly inspects native OS accessibility trees (**Android UI Automator XML** via Wi-Fi ADB or **Windows UI Automation** via COM).
2. **AST Container Pruning**: Filters out redundant layout wrappers and offscreen containers, pruning raw hierarchies by **80–90%**.
3. **Compact Coordinate Mapping**: Maps actionable and informative controls into ultra-lean token representations (Markdown tables or Line DSL) with **100% exact pixel-center click coordinates**.
4. **Structured Gemini Tool Calling**: Feeds compact state (<1,500 prompt tokens/turn) to **Google Gemini 2.5 / 3.5 Flash** using deterministic function schemas.
5. **Modal Dialog & Error Parsing**: Automatically reads and handles top-level modal popups, error alerts (e.g. *"Windows cannot find..."*), and dismissal buttons.
6. **Native OS Execution**: Injects actions instantly via low-latency native drivers (`input tap/swipe/text` on Android, `pyautogui`/COM on Windows).

> 🚀 **Result**: **Sub-second decision cycles (~0.68s)**, **80–90% token reduction**, **zero visual grounding hallucinations**, and **24/7 sustainable operation** within standard free-tier quotas.

---

## 🚀 Key Features

<table>
  <tr>
    <td width="50%">
      <h3>⚡ Visionless AST Compactor</h3>
      <p>Reduces token usage by 80–90% compared to raw XML and 95%+ compared to vision models. Typical turns consume only <b>300–800 tokens</b>.</p>
    </td>
    <td width="50%">
      <h3>📱 Dual-Platform Native Control</h3>
      <p>Seamlessly controls <b>Android 11+ phones</b> (via wireless ADB or USB) and <b>Windows 10/11 desktops</b> (via UI Automation COM & PyAutoGUI).</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🎯 Deterministic Coordinate Targeting</h3>
      <p>Extracts exact <code>bounds="[x1,y1][x2,y2]"</code> pixel centers directly from OS layout engines, eliminating visual grounding errors and DPI distortion.</p>
    </td>
    <td width="50%">
      <h3>🛡️ Quota & Rate Limit Resilience</h3>
      <p>Automatic 429 exponential backoff retry engine extracting server <code>retryDelay</code> paired with a dynamic model fallback cascade (<code>3.5-flash-lite</code> &rarr; <code>3.1-flash-lite</code> &rarr; <code>2.5-flash-lite</code>).</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>🔄 3-Tier Deadlock & Oscillation Guard</h3>
      <p>Real-time cycle detector flags repetitive actions, stagnant screens, and multi-step oscillation loops ($A \to B \to A \to B$), injecting adaptive recovery prompts.</p>
    </td>
    <td width="50%">
      <h3>🛑 Modal Error & Alert Inspection</h3>
      <p>Natively extracts top-level error popups, dialog boxes, and permission warnings, reading the message text and dismissing or failing gracefully.</p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <h3>💻 Interactive Rich REPL & Inspector</h3>
      <p>Beautiful terminal UI with live reasoning spinners, syntax-highlighted step cards, dynamic prompt badges (<code>windows-gemini &gt;</code> / <code>android-gemini &gt;</code>), and safe <code>Ctrl+C</code> interruption.</p>
    </td>
    <td width="50%">
      <h3>🔌 Zero-Cable Android Pairing</h3>
      <p>Native support for Android 11+ Wi-Fi pairing codes (<code>adb pair</code>) and automatic persistent connection discovery.</p>
    </td>
  </tr>
</table>

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                        Interactive Multi-Platform REPL Shell                            │
│                        (src/android_gemini_agent/cli/app.py)                            │
│   • Android (Wi-Fi ADB / USB)                    • Windows Desktop (UIAutomation)       │
│   • Tabular Screen Node Inspector                • Live Spinners & Step Execution Cards │
│   • On-the-fly Platform Switcher (:windows / :android)                                  │
└────────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              Gemini Decision Engine Core                                │
│                       (src/android_gemini_agent/agent/loop.py)                          │
│   • Google GenAI SDK v2.0+ (gemini-3.5-flash-lite / gemini-2.5-flash)                   │
│   • Structured Tool Schema Calling (tap, click, type_text, hotkey, swipe, launch_app)   │
│   • History Compactor (<1,500 prompt tokens/turn bounded sliding window)                │
│   • 3-Tier Deadlock & Oscillation Detector (loop_detector.py)                           │
│   • 429 Quota Auto-Backoff & Model Fallback Cascade                                     │
└──────────────────────┬───────────────────────────────────────────┬──────────────────────┘
                       │                                           │
                       ▼ (Target: Android)                         ▼ (Target: Windows)
┌───────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│         Android Wireless Manager          │   │        Windows Desktop Controller       │
│      (src/android_gemini_agent/adb/)      │   │    (src/android_gemini_agent/windows/)  │
│  • Android 11+ Pairing (adb pair)         │   │  • UI Automation COM Tree Traversal     │
│  • Wi-Fi Connect & Auto-Reconnect Backoff │   │  • PyAutoGUI Mouse & Keyboard Engine    │
│  • UiAutomator XML Dump & AST Pruner      │   │  • Modal Error Dialog & Popup Inspector │
│  • Shell Escaping & Non-ASCII Fallback    │   │  • Unicode & Emoji Clipboard Injection  │
│                                           │   │  • Win+R / Executable Launching Cascade │
└───────────────────────────────────────────┘   └─────────────────────────────────────────┘
```

---

## 📊 Visionless Fast-Path vs Multimodal VLM

| Metric / Dimension | Visionless Fast-Path (WinRoid-Agent) | Multimodal VLM (Screenshot-Based) |
|---|---|---|
| **Input Modality** | Compact UTF-8 Accessibility Table / Line DSL | Base64 PNG/JPEG Compressed Images |
| **Token Cost / Turn** | **~300 – 1,200 tokens** (80–90% savings) | **1,500 – 4,000+ tokens** |
| **Turn Latency** | **400ms – 1,000ms** (Instant inference) | **2,500ms – 6,000ms** (Image upload + tokenization) |
| **Coordinate Accuracy** | **100% exact** (Native OS layout bounding boxes) | Subject to visual hallucinations & scaling error |
| **Display Scaling & DPI** | Native pixel coordinates, DPI-immune | Requires DPI normalization & coordinate re-scaling |
| **Free-Tier Longevity** | Sustains **15–30+ turns/min** without 429 quota exhaustion | Exhausts free tier (15 RPM / 1M TPM) in 2–4 turns |
| **Bandwidth & Privacy** | Tiny text payload (~2 KB/turn), no visual data sent | Heavy image uploads (~500 KB–2 MB/turn), visual leaks |
| **Offline Testability** | **100% deterministic** via static XML/AST fixtures | Requires brittle image-diffing test pipelines |
| **Canvas / Game Support** | Requires accessibility nodes (limited on raw OpenGL) | Natively observes pixels on raw canvas/games |

---

## 📦 Quickstart Guide

### 1. Prerequisites
- **Python**: 3.10, 3.11, 3.12, 3.13, or 3.14.
- **Android Target**: Android device with Developer Options enabled and `adb` in `PATH` (optional if using Windows automation or `--mock`).
- **Windows Target**: Windows 10/11 desktop.
- **Gemini API Key**: Free API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Installation

Clone the repository and install in editable development mode:

```bash
# Clone the repository
git clone https://github.com/SherrySoft/WinRoid-Agent.git
cd WinRoid-Agent

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install base package with dev dependencies
pip install -e ".[dev]"

# (Optional) For Windows desktop automation support on Windows:
pip install -e ".[windows]"
```

### 3. Environment Configuration

Copy `.env.example` to `.env` and configure your API key:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
# Required: Google AI Studio Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Target Platform ('android' or 'windows')
DEFAULT_PLATFORM=windows

# Android Default Wireless Endpoint
ADB_DEVICE_IP=192.168.1.100
ADB_DEVICE_PORT=5555

# Model Selection & Execution Limits
GEMINI_MODEL=gemini-3.5-flash-lite
MAX_AGENT_STEPS=20
ACTION_DELAY_SECONDS=0.5
```

---

## 📱 Android Wireless Setup (Android 11+)

Android 11 introduced native **Wireless Debugging** with pairing codes, eliminating USB cables entirely.

```
       [ Android Device ]                                [ Host Computer ]
               │                                                 │
 1. Open Developer Options                                       │
 2. Toggle 'Wireless Debugging' ON                               │
 3. Tap 'Pair device with pairing code'                          │
    Shows: IP:Port (e.g. 192.168.1.45:38912)                     │
           Code    (e.g. 654321)                                 │
               │ ─── 4. Run 'pair 192.168.1.45:38912 654321' ───▶ │
               │ ◀── Successfully paired! ────────────────────── │
               │                                                 │
 5. Return to Wireless Debugging screen                          │
    Shows: IP:Port (e.g. 192.168.1.45:41253)                     │
               │ ─── 6. Run 'connect 192.168.1.45:41253' ───────▶ │
               │ ◀── Connected to device! ─────────────────────── │
```

### Step-by-Step Pairing Workflow:
1. **Enable Developer Options**: Go to **Settings > About Phone** and tap **Build Number** 7 times.
2. **Enable Wireless Debugging**: Open **Settings > System > Developer Options > Wireless Debugging** and toggle it **ON**.
3. **Get Pairing Code**: Tap **"Pair device with pairing code"**. Note the ephemeral pairing port (e.g., `192.168.1.45:38912`) and 6-digit code (e.g., `654321`).
4. **Execute Pairing**:
   ```bash
   python main.py --pair 192.168.1.45:38912 654321
   ```
5. **Connect**: Return to the main Wireless Debugging page, note the persistent connection port (e.g., `41253`), and run:
   ```bash
   python main.py --connect 192.168.1.45:41253
   ```

---

## 🖥️ Windows Desktop Automation Setup

To automate your local Windows desktop:
```bash
# Launch interactive REPL directly in Windows mode
python main.py --platform windows

# Or run a single desktop task directly
python main.py --platform windows --task "Open Notepad, type 'Hello from WinRoid-Agent!', and save to Desktop"
```

> 💡 **Tip**: When running inside the REPL, switch between platforms on the fly anytime by typing `:windows` or `:android`.

---

## 🎮 Interactive REPL & CLI Cheat Sheet

### Interactive REPL Commands

| Command | Syntax / Arguments | Description | Example |
|---|---|---|---|
| `:windows` | None | Switch active target platform to Windows Desktop. | `:windows` |
| `:android` | None | Switch active target platform to Android Phone. | `:android` |
| `platform` | `platform <android\|windows>` | Switch active target platform dynamically. | `platform windows` |
| `connect` | `connect [ip:port]` | Connects to wireless target. Uses `.env` default if omitted. | `connect 192.168.1.45:41253` |
| `pair` | `pair <ip:port> <code>` | Pairs device via Android 11+ pairing code protocol. | `pair 192.168.1.45:38912 654321` |
| `devices` / `ls`| None | Lists all attached ADB devices with active target indicator. | `devices` |
| `use` | `use <serial>` | Selects active target device serial / endpoint. | `use 192.168.1.45:5555` |
| `status` | None | Displays connection state, active platform, model, API key, and safety limits. | `status` |
| `dump_ui` | None | Dumps and renders the current screen UI accessibility elements table. | `dump_ui` |
| `run` | `run <task>` | Dispatches a natural language automation instruction to Gemini. | `run Open Spotify and play Discover Weekly` |
| `<prompt>` | `<natural language>` | Direct fallback: any unrecognised prompt routes directly to `run`. | `Open Settings and enable Dark theme` |
| `settings` | `settings [key=val]` | Displays active settings or updates a configuration at runtime. | `settings max_agent_steps=25` |
| `help` | None | Renders interactive command reference table. | `help` |
| `exit` / `quit` | None | Cleans up controllers and terminates the session. | `exit` |

### CLI One-Shot Command Flags

```bash
# Execute a single task on Android
python main.py --task "Open Clock, set timer for 5 minutes, and start"

# Execute a single task on Windows Desktop
python main.py --platform windows --task "Open Calculator and compute 256 * 16"

# Pair an Android device over Wi-Fi
python main.py --pair 192.168.1.45:38912 654321

# Connect to device and inspect current UI elements
python main.py --connect 192.168.1.45:41253 --dump-ui

# Inspect status and verify API connectivity
python main.py --status

# Override the Gemini model identifier
python main.py --model gemini-3.5-flash-lite --task "Search for nearby coffee shops in Maps"
```

---

## 🛡️ Rate Limit & Quota Resilience

Google AI Studio free-tier quotas are subject to **15 Requests Per Minute (RPM)** and **1,000,000 Tokens Per Minute (TPM)**.

```
                  ┌─────────────────────────────────────┐
                  │    Gemini API Call (Primary Model)  │
                  └──────────────────┬──────────────────┘
                                     │
                             [ 429 Quota Error? ]
                                ├── No ──▶ Success (Execute Tool)
                                │
                                ▼ Yes
                  ┌─────────────────────────────────────┐
                  │  Extract retry-after delay header   │
                  │  (e.g. 'retry in 24s' -> sleep 25s) │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │        Model Fallback Cascade       │
                  │    1. gemini-3.5-flash-lite         │
                  │    2. gemini-3.1-flash-lite         │
                  │    3. gemini-2.5-flash-lite         │
                  └─────────────────────────────────────┘
```

1. **Compact Turn Footprint**: Because each turn consumes only ~400 tokens, you will **never** exceed the 1M TPM threshold under standard automation.
2. **Automatic 429 Backoff**: If rate limits are encountered, the engine intercepts the exception, parses the server `retryDelay` (e.g. `24s`), and retries transparently without crashing your session.
3. **Model Fallback Cascade**: If the primary model encounters temporary capacity exhaustion, the engine automatically attempts the request against secondary lite models before reporting an error.

---

## 🔄 3-Tier Infinite Loop & Deadlock Prevention

GUI automation agents often risk falling into infinite action cycles. The built-in **`LoopDetector`** continuously computes MD5 structural state hashes of visible screen elements and evaluates history across 3 tiers:

```
[ Step Executed ] ──▶ [ Compute UI State Hash ]
                             │
                             ├─ Tier 1: ≥3 Identical Actions? ──────────┐
                             ├─ Tier 2: ≥3 Stagnant Screen States? ────┼─▶ [ Inject Recovery Warning ]
                             └─ Tier 3: 2-step / 3-step Oscillation? ───┘         │
                                                                                 ▼
                                                                 [ >2 Consecutive Warnings? ]
                                                                       ├── No  ──▶ Continue with new plan
                                                                       └── Yes ──▶ Abort safely (Save tokens)
```

- **Tier 1 (Identical Action Repetition)**: Detects when the model taps the same coordinates $\ge 3$ consecutive times without progress.
- **Tier 2 (Stagnant Screen State)**: Detects when the screen state hash remains identical across $\ge 3$ consecutive turns despite executing actions.
- **Tier 3 (Multi-Step Oscillation)**: Detects $A \to B \to A \to B$ or $A \to B \to C \to A \to B \to C$ loops (e.g. repeatedly opening and closing a dialog).
- **Recovery Prompt Injection**: Injects targeted guidance instructing Gemini to re-evaluate visible IDs, dismiss dialogs, or backtrack. If the deadlock persists for $>2$ consecutive cycles, execution is aborted safely to prevent wasted tokens.

---

## 📁 Repository Structure

```
WinRoid-Agent/
├── src/android_gemini_agent/
│   ├── adb/                    # Android ADB client, protocol, controller, text escaper
│   │   ├── client.py           # Subprocess ADB execution & auto-discovery
│   │   ├── controller.py       # Touch gestures, taps, swipes, auto-reconnect
│   │   ├── mock_client.py      # Offline mock device simulator for testing
│   │   ├── models.py           # ConnectionResult, DeviceInfo, DeviceState
│   │   ├── protocol.py         # AdbClientProtocol interface
│   │   └── text_escaper.py     # Shell metacharacter escaping & clipboard fallback
│   ├── agent/                  # Gemini decision loop & prompt compactor
│   │   ├── compactor.py        # Sliding window history compactor (<1500 tokens)
│   │   ├── loop.py             # AgentDecisionEngine multi-turn execution loop
│   │   ├── loop_detector.py    # 3-tier cycle & stagnation detector
│   │   ├── models.py           # AgentStep, TaskResult, ExecutionStatus
│   │   └── tools.py            # Google GenAI Tool & FunctionDeclaration schemas
│   ├── cli/                    # Interactive Rich REPL & visual shell
│   │   ├── app.py              # AndroidAgentCLI REPL shell & CLI argument parsing
│   │   └── console.py          # Rich themes, step cards, spinners, and panels
│   ├── parser/                 # UI hierarchy XML parser & token formatters
│   │   ├── formatters.py       # Markdown table, Line DSL, JSON formatters
│   │   ├── models.py           # BoundingBox, UIElement, UIHierarchy
│   │   └── parser.py           # XML AST parser, container pruning, bounds math
│   ├── windows/                # Native Windows desktop automation
│   │   ├── controller.py       # PyAutoGUI & UIAutomation desktop controller
│   │   ├── parser.py           # Windows UIAutomation COM tree & dialog extractor
│   │   └── tools.py            # Windows tool schemas (click, hotkey, type_text, launch_app)
│   └── config.py               # Pydantic Settings & environment manager
├── examples/                   # Standalone runnable developer examples
│   ├── README.md               # Developer examples execution guide
│   ├── android_wireless_demo.py # Complete Android wireless automation script
│   ├── windows_desktop_demo.py  # Windows desktop automation script
│   └── custom_prompt_task.py   # Custom prompt formatter & telemetry export
├── tests/                      # Pytest offline test suite (255 tests)
│   ├── fixtures/               # XML screen hierarchy fixtures
│   ├── conftest.py             # Deterministic mock Gemini response factories
│   └── test_*.py               # 12 test modules covering all subsystems
├── .github/                    # Community health & CI/CD workflows
│   ├── ISSUE_TEMPLATE/         # Bug report & feature request YAML forms
│   ├── PULL_REQUEST_TEMPLATE.md # PR template & quality checklist
│   └── workflows/ci.yml        # GitHub Actions CI matrix
├── CONTRIBUTING.md             # Contributor setup, standards, & PR workflow
├── CODE_OF_CONDUCT.md          # Contributor Covenant v2.1
├── pyproject.toml              # Build metadata & entrypoint configuration
└── README.md                   # This documentation
```

---

## 🧪 Developer Examples

Check the [`examples/`](examples/) directory for standalone, runnable scripts:

```bash
# Run Android wireless demo in mock mode (no hardware required)
python examples/android_wireless_demo.py --mock

# Run Windows desktop demo in mock mode
python examples/windows_desktop_demo.py --mock

# Compare token formatters and export telemetry
python examples/custom_prompt_task.py --mock
```

---

## 🛠️ Troubleshooting & FAQ

<details>
<summary><b>1. ADB says <code>device unauthorized</code> or connection fails</b></summary>
<br>
<b>Cause:</b> RSA security key not accepted or expired.<br>
<b>Fix:</b>
1. On your phone, go to <b>Developer Options</b>.
2. Tap <b>Revoke USB debugging authorizations</b>.
3. Toggle <b>Wireless debugging</b> OFF and ON.
4. Tap <i>Pair device with pairing code</i> and run <code>python main.py --pair <ip:port> <code></code>.
</details>

<details>
<summary><b>2. ADB reports <code>actively refused</code> or <code>timed out</code></b></summary>
<br>
<b>Cause:</b> Android assigns a dynamic port every time Wireless Debugging is re-enabled, or host PC and phone are on different Wi-Fi bands.<br>
<b>Fix:</b>
1. Check the active connection port on the main Wireless Debugging screen (it differs from the pairing port).
2. Verify both PC and phone are on the same Wi-Fi subnet (disable AP Isolation on your router).
3. Reconnect with <code>connect <ip:new_port></code>.
</details>

<details>
<summary><b>3. Windows automation: UI dump returns 0 controls or clicks don't register</b></summary>
<br>
<b>Cause:</b> Target window is elevated (Run as Administrator) or running in an isolated desktop session.<br>
<b>Fix:</b>
1. Launch your terminal/IDE as Administrator if targeting elevated applications (Task Manager, Registry Editor, Installers).
2. Ensure Windows Display Scaling is set consistently (100% or standard scaling recommended).
</details>

<details>
<summary><b>4. Quota exceeded (HTTP 429) during heavy testing</b></summary>
<br>
<b>Cause:</b> Hitting free-tier 15 RPM limit during tight loops.<br>
<b>Fix:</b>
1. The agent automatically executes exponential backoff and model cascade retries.
2. Increase <code>ACTION_DELAY_SECONDS=1.0</code> in <code>.env</code> if running long multi-step flows.
3. Or switch to a pay-as-you-go key on Google AI Studio.
</details>

---

## 🧪 Testing & Verification

The test suite runs **100% offline** without physical devices or active API keys:

```bash
# Run all 255 offline tests
python -m pytest

# Run with verbose output and duration reporting
python -m pytest -v --durations=10

# Run specific test modules
python -m pytest tests/test_ui_parser.py tests/test_formatters.py -v
python -m pytest tests/test_windows_automation.py -v
python -m pytest tests/test_e2e_scenarios.py -v
```

---

## 🤝 Contributing & Community

We welcome contributions from the community! Please see our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md).

- **Found a bug?** Open a [Bug Report](https://github.com/SherrySoft/WinRoid-Agent/issues/new?template=bug_report.yml).
- **Have an idea?** Submit a [Feature Request](https://github.com/SherrySoft/WinRoid-Agent/issues/new?template=feature_request.yml).
- **Questions?** Join the discussion in [GitHub Discussions](https://github.com/SherrySoft/WinRoid-Agent/discussions).

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.
