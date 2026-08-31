# Developer Examples & Quickstart Guide

This directory contains production-ready, standalone Python example scripts demonstrating how to build, customize, and extend autonomous automation workflows with **Android Gemini Agent**.

All examples are fully functional out-of-the-box and support **offline simulation mode (`--mock`)**, allowing developers to test and explore features without physical hardware or active Gemini API keys.

---

## Table of Examples

| Example Script | Platform | Key Capabilities Demonstrated | Offline Command |
|---|---|---|---|
| [`android_wireless_demo.py`](#1-android-wireless-automation-demo) | Android | Settings loading, wireless pairing & connect, UI dump & AST pruning, autonomous task execution | `python examples/android_wireless_demo.py --mock` |
| [`windows_desktop_demo.py`](#2-windows-desktop-automation-demo) | Windows | Native UIAutomation tree extraction, window focus, safe clicks/typing/hotkeys, desktop agent loop | `python examples/windows_desktop_demo.py --mock` |
| [`custom_prompt_task.py`](#3-custom-prompts--callbacks-demo) | Cross-platform | Custom system instructions, prompt hooks, real-time step callbacks, token tracking, strategy switching | `python examples/custom_prompt_task.py --mock` |

---

## Hardware Requirements vs. `--mock` Offline Mode

| Requirement | Live Execution Mode | Offline Simulation (`--mock`) |
|---|---|---|
| **Android Device** | Physical phone/tablet (Android 11+) on the same Wi-Fi network, or USB-connected emulator | **None** (uses in-memory `MockAdbClient`) |
| **Windows Desktop** | Windows 10/11 with `pyautogui` and `uiautomation` | **Cross-platform** (runs on Linux, macOS, or Windows via mock desktop tree) |
| **Gemini API Key** | Valid `GEMINI_API_KEY` with access to Gemini 2.5 / 3.5 models | **None** (uses simulated GenAI decision engine) |
| **Network Access** | Local Wi-Fi (for ADB) + Internet (for Google GenAI API) | **100% Offline** (no network packets sent) |

---

## 1. Android Wireless Automation Demo

**File**: `examples/android_wireless_demo.py`

### What it Demonstrates
- Loading settings dynamically from `.env` and environment variables.
- Establishing an ADB connection:
  - **Android 11+ Pairing**: Ephemeral pairing port + 6-digit PIN (`adb pair <ip>:<pair_port> <code>`).
  - **Wireless Connection**: Persistent connection port (`adb connect <ip>:<port>`).
- Dumping raw `uiautomator` XML and applying **AST container pruning** to extract actionable UI elements.
- Rendering formatted UI hierarchy previews (Markdown Table or Compact Line DSL).
- Running an autonomous agent decision loop using `AgentDecisionEngine`.

### Command-Line Arguments
```bash
python examples/android_wireless_demo.py [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--mock` | flag | `False` | Run in offline simulation mode using `MockAdbClient` and mock LLM |
| `--connect` | string | From `.env` (`192.168.1.100:5555`) | Target device `IP:PORT` to connect |
| `--pair` | string | `None` | Pairing endpoint `IP:PORT` (e.g. `192.168.1.100:38912`) |
| `--code` | string | `None` | 6-digit numeric pairing code (required if `--pair` is provided) |
| `--task` | string | `"Open Settings and navigate to Display to enable Dark Theme"` | Natural language automation objective |
| `--model` | string | `"gemini-2.5-flash"` | Gemini model identifier |
| `--format` | string | `"markdown_table"` | UI hierarchy preview format (`markdown_table` or `line_dsl`) |
| `--max-steps` | integer | `10` | Maximum agent turns allowed before timeout |

### Example Usages

#### A. Offline Simulation (No Phone Needed)
```bash
python examples/android_wireless_demo.py --mock
```

#### B. Connect to an Existing Wireless Device
```bash
python examples/android_wireless_demo.py --connect 192.168.1.50:5555 --task "Open Settings and search for Wi-Fi"
```

#### C. Pair a New Android 11+ Device Over Wi-Fi
```bash
python examples/android_wireless_demo.py \
  --pair 192.168.1.50:39481 \
  --code 482910 \
  --connect 192.168.1.50:5555 \
  --task "Enable Dark Mode"
```

---

## 2. Windows Desktop Automation Demo

**File**: `examples/windows_desktop_demo.py`

### What it Demonstrates
- Initializing `WindowsController` and `WindowsUIParser` (or mock desktop simulator).
- Querying active desktop windows and extracting visible, interactive accessibility elements.
- Performing safe desktop actions (launching applications, typing text with clipboard fallback, clicking buttons, executing hotkeys like `Win+R`, `Ctrl+C`).
- Running an autonomous desktop task via `AgentDecisionEngine(platform="windows")`.

### Command-Line Arguments
```bash
python examples/windows_desktop_demo.py [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--mock` | flag | `False` | Run in offline simulation mode (works on macOS/Linux as well) |
| `--task` | string | `"Open Notepad and type 'Hello from Gemini Agent!'"` | Natural language automation objective |
| `--app` | string | `"notepad"` | Target application to demonstrate launch and inspection |
| `--model` | string | `"gemini-2.5-flash"` | Gemini model identifier |
| `--max-steps` | integer | `10` | Maximum agent turns allowed |

### Example Usages

#### A. Offline Simulation (Cross-Platform)
```bash
python examples/windows_desktop_demo.py --mock
```

#### B. Live Windows Automation
```bash
python examples/windows_desktop_demo.py --app notepad --task "Open Notepad and type 'Agent Test' and save"
```

---

## 3. Custom Prompts & Callbacks Demo

**File**: `examples/custom_prompt_task.py`

### What it Demonstrates
- Extending `HistoryCompactor` with custom system instructions (e.g. strict JSON output, domain persona, safety boundaries).
- Injecting custom prompt hooks and dynamic context (e.g. user credentials, application state).
- Subscribing to real-time **step callbacks** to capture latency, token consumption, and action logs per turn.
- Implementing dynamic model strategy switching (e.g. switching from fast flash model to high-reasoning model upon retries).
- Parsing structured metrics and exporting task summaries to JSON.

### Command-Line Arguments
```bash
python examples/custom_prompt_task.py [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--mock` | flag | `False` | Run in offline simulation mode |
| `--task` | string | `"Perform security audit on Settings screen and verify encryption status"` | Custom task objective |
| `--model` | string | `"gemini-2.5-flash"` | Primary Gemini model |
| `--persona` | string | `"QA Engineer"` | Custom persona for system instructions (`QA Engineer`, `Accessibility Auditor`, `Speedrunner`) |
| `--output-json` | string | `None` | Optional file path to export structured telemetry report |

### Example Usages

#### A. Run with Custom Persona in Mock Mode
```bash
python examples/custom_prompt_task.py --mock --persona "Accessibility Auditor"
```

#### B. Run with JSON Telemetry Export
```bash
python examples/custom_prompt_task.py --mock --output-json audit_report.json
```

---

## Custom Scenario Tips

### 1. Creating Custom Mock Screen Fixtures
You can register custom XML hierarchy fixtures in `MockAdbClient` to test specific application screens without hardware:

```python
from android_gemini_agent.adb.mock_client import MockAdbClient

mock_adb = MockAdbClient()

CUSTOM_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.myapp" bounds="[0,0][1080,2400]">
    <node index="0" text="Transfer Funds" resource-id="com.myapp:id/btn_transfer" class="android.widget.Button" package="com.myapp" bounds="[100,500][980,620]" clickable="true"/>
  </node>
</hierarchy>"""

mock_adb.set_fixture("transfer_screen", CUSTOM_XML)
mock_adb.switch_fixture("transfer_screen")
```

### 2. Attaching Custom Telemetry Callbacks
You can attach an event listener to `AgentDecisionEngine.run_task` to stream telemetry to logging systems or dashboards:

```python
def my_telemetry_listener(step):
    print(f"Turn {step.step_number}: Tool {step.tool_name} executed in {step.latency_ms:.1f}ms")

result = engine.run_task(
    task="Search for flight to Tokyo",
    on_step_callback=my_telemetry_listener,
)
```

### 3. Handling Rate Limits (429) & Model Fallbacks
The decision engine includes built-in 429 quota exhaustion handling with exponential backoff and model cascade (`gemini-3.5-flash-lite` $\to$ `gemini-3.1-flash-lite` $\to$ `gemini-2.5-flash-lite`). You can configure timeouts and thresholds in `Settings`:

```python
from android_gemini_agent.config import get_config

settings = get_config()
settings.update_setting("max_agent_steps", 15)
settings.update_setting("action_delay_seconds", 0.5)
```

---

## Troubleshooting & FAQ

- **Q: `ADB executable not found` error on physical run?**  
  *A:* Ensure Android SDK platform-tools is installed. You can set the path explicitly via the `ADB_PATH` environment variable:
  ```bash
  export ADB_PATH=/path/to/platform-tools/adb
  ```

- **Q: Wireless connection times out or gets refused?**  
  *A:* Confirm the device and PC are on the same local subnet. Android 11+ generates a new port every time Wireless Debugging is toggled on/off—verify the port displayed on the phone's Wireless Debugging screen.

- **Q: How can I run the full test suite?**  
  *A:* Run `pytest` from the root directory:
  ```bash
  pytest
  ```
