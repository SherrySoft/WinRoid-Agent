# Contributing to Android & Windows Gemini Automation Agent

First off, thank you for considering contributing to the **Android & Windows Gemini Automation Agent**! 🎉

We are building a blazing-fast, visionless, token-optimized autonomous agent ecosystem. Whether you are fixing bugs, improving documentation, adding new platform drivers, or enhancing our AST pruning heuristics, your contributions make a massive difference.

Please take a moment to review this document to ensure a smooth, productive collaboration.

---

## 📜 Table of Contents

1. [Code of Conduct](#-code-of-conduct)
2. [Development Environment Setup](#-development-environment-setup)
3. [Repository Architecture Map](#-repository-architecture-map)
4. [Development Workflow & Git Guidelines](#-development-workflow--git-guidelines)
5. [Coding Standards & Conventions](#-coding-standards--conventions)
6. [Offline-First Testing Philosophy](#-offline-first-testing-philosophy)
7. [Extensibility Guides](#-extensibility-guides)
   - [Adding a New Automation Tool](#adding-a-new-automation-tool)
   - [Adding a New Platform Adapter](#adding-a-new-platform-adapter)
8. [Submitting a Pull Request](#-submitting-a-pull-request)
9. [Community & Questions](#-community--questions)

---

## 🤝 Code of Conduct

This project and everyone participating in it is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [maintainers@gemini-agent.dev](mailto:maintainers@gemini-agent.dev).

---

## 🛠️ Development Environment Setup

### 1. Prerequisites
- **Python**: `3.10`, `3.11`, `3.12`, `3.13`, or `3.14`
- **Git**: Latest version installed
- **Android SDK Platform Tools** (`adb`): Optional for mock development, required for live Android hardware testing.
- **Google AI Studio API Key**: Optional for mock development, required for live Gemini testing.

### 2. Clone and Setup Virtual Environment

```bash
# Fork the repo on GitHub, then clone your fork:
git clone https://github.com/<your-username>/android-gemini-agent.git
cd android-gemini-agent

# Create a dedicated virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell / Command Prompt):
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Development Dependencies

Install the package in editable mode with development, linting, and testing extras:

```bash
# Install core package with dev dependencies (pytest, black, ruff, etc.)
pip install --upgrade pip
pip install -e ".[dev]"

# (Optional) On Windows, install native Windows automation dependencies:
pip install -e ".[windows]"
```

### 4. Verify Local Installation

Run the automated test suite to verify your environment:

```bash
python -m pytest -v
```
All **255+ tests** should execute in ~7 seconds and pass with a 100% success rate.

---

## 🗺️ Repository Architecture Map

Before making modifications, familiarize yourself with our clean modular structure:

```
src/android_gemini_agent/
├── adb/                    # Android ADB client, protocol, controller, and sanitization
│   ├── client.py           # Real ADB execution via subprocess & path resolution
│   ├── controller.py       # Touch gestures, taps, swipes, auto-reconnect logic
│   ├── mock_client.py      # Offline mock device simulator for testing
│   ├── models.py           # ConnectionResult, DeviceInfo, DeviceState
│   ├── protocol.py         # AdbClientProtocol interface definition
│   └── text_escaper.py     # Shell metacharacter escaping & clipboard paste fallback
├── agent/                  # Gemini AI decision engine & context management
│   ├── compactor.py        # Sliding window history compactor (<1500 tokens)
│   ├── loop.py             # AgentDecisionEngine multi-turn execution loop
│   ├── loop_detector.py    # 3-tier cycle, stagnation, and oscillation detector
│   ├── models.py           # AgentStep, TaskResult, ExecutionStatus
│   └── tools.py            # Google GenAI Tool & FunctionDeclaration schemas
├── cli/                    # Interactive Rich REPL & terminal visualizer
│   ├── app.py              # AndroidAgentCLI REPL shell & CLI argument parsing
│   └── console.py          # Rich themes, step cards, live spinners, and panels
├── parser/                 # UI hierarchy XML parser & token formatters
│   ├── formatters.py       # Markdown table, Line DSL, JSON formatters
│   ├── models.py           # BoundingBox, UIElement, UIHierarchy
│   └── parser.py           # XML AST parser, container pruning, bounds math
├── windows/                # Native Windows desktop automation
│   ├── controller.py       # PyAutoGUI & UIAutomation desktop controller
│   ├── parser.py           # Windows UIAutomation COM tree extractor
│   └── tools.py            # Windows tool schemas (click, hotkey, type_text)
└── config.py               # Pydantic Settings & environment manager
```

---

## 🌿 Development Workflow & Git Guidelines

### Branch Naming Conventions
Always create a descriptive branch for your work:
- `feature/<feature-name>`: New functionality or capabilities
- `bugfix/<issue-description>`: Bug fixes and patches
- `docs/<doc-topic>`: Documentation enhancements
- `refactor/<subsystem>`: Non-functional code improvements
- `test/<test-suite>`: Test coverage additions

### Commit Message Guidelines
We adhere to [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <short summary in imperative mood>

[optional body explaining motivation and architectural context]

[optional footer with issue reference, e.g. Fixes #42]
```

**Allowed Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`.

**Examples**:
- `feat(parser): add support for Compose semantics content-description nodes`
- `fix(adb): handle dynamic port randomization during auto-reconnect backoff`
- `docs(readme): add Windows desktop permission elevation guide`
- `test(loop_detector): add unit tests for 3-step action oscillation recovery`

---

## 🎨 Coding Standards & Conventions

### 1. Python Style & Formatting
- **PEP 8 Compliance**: Follow standard Python conventions.
- **Line Length**: Max 100 characters.
- **Formatting Tools**: We use `black` for formatting and `ruff` / `flake8` for linting.

```bash
# Format code automatically
black --line-length 100 src tests examples

# Run linter checks
ruff check src tests examples
```

### 2. Type Annotations
- Strict type hinting is enforced across all modules.
- Use Python 3.10+ union types (`X | None` or `Union[X, None]`).
- Always include `from __future__ import annotations` at the top of every file.
- Avoid raw `Any` where a specific protocol or model can be used.

### 3. Docstrings & Comments
- Provide clear docstrings for all public classes, methods, and functions using Google/Sphinx style.
- Include parameter descriptions, return types, and potential raised exceptions.

---

## 🧪 Offline-First Testing Philosophy

> 🔒 **Core Tenet**: The entire repository test suite MUST run **100% offline**, fast (<10s), and deterministically without requiring physical Android devices, Windows desktop focus, or active Gemini API billing keys.

### Running the Test Suite
```bash
# Run all tests
python -m pytest

# Run with verbose output and duration timing
python -m pytest -v --durations=10

# Run specific subsystem tests
python -m pytest tests/test_adb_client.py -v
python -m pytest tests/test_ui_parser.py -v
python -m pytest tests/test_loop_detector.py -v
python -m pytest tests/test_agent_engine.py -v
python -m pytest tests/test_windows_automation.py -v
python -m pytest tests/test_e2e_scenarios.py -v
```

### Test Suite Structure
1. **Unit Tests** (`tests/test_*.py`): Isolated tests for bounding boxes, text escaping, XML parsing, tool declarations, CLI renderers.
2. **Subsystem Integration** (`tests/test_device_controller.py`, `tests/test_agent_engine.py`): Multi-component flows using `MockAdbClient` and mock Gemini models.
3. **E2E Scenarios** (`tests/test_e2e_scenarios.py`):
   - *Tier 1*: 24 Core feature validations.
   - *Tier 2*: Boundary & corner cases (offscreen coordinates, metacharacter injections, malformed XML).
   - *Tier 3*: Cross-feature lifecycles (Pair &rarr; Connect &rarr; Hierarchy Dump &rarr; Parse &rarr; Tool Call &rarr; Dispatch).
   - *Tier 4*: Real-world end-to-end scenarios (Settings Dark Mode, Wi-Fi drops, cycle recovery).

### Writing New Tests
- When adding a feature, add corresponding tests in `tests/`.
- Use existing fixtures in `tests/fixtures/` (`settings_screen.xml`, `login_screen.xml`, `dialog_screen.xml`, `media_feed_screen.xml`, `edge_cases.xml`) or add new minimal fixtures.
- Use `MockGenerateContentResponse` from `tests/conftest.py` to mock Gemini AI responses.

---

## 🔌 Extensibility Guides

### Adding a New Automation Tool

1. **Define the Schema** in `src/android_gemini_agent/agent/tools.py`:
   Add a new `types.FunctionDeclaration` to `get_gemini_tools()` with clear parameter types and descriptions:
   ```python
   types.FunctionDeclaration(
       name="long_press",
       description="Performs a long press at exact screen pixel coordinates.",
       parameters=types.Schema(
           type=types.Type.OBJECT,
           properties={
               "x": types.Schema(type=types.Type.INTEGER, description="X center coordinate"),
               "y": types.Schema(type=types.Type.INTEGER, description="Y center coordinate"),
               "duration_ms": types.Schema(type=types.Type.INTEGER, description="Duration in milliseconds"),
           },
           required=["x", "y"],
       ),
   )
   ```
2. **Implement the Controller Action** in `src/android_gemini_agent/adb/controller.py` or `src/android_gemini_agent/windows/controller.py`.
3. **Handle Dispatch** in `execute_tool()` or `execute_windows_tool()`.
4. **Add Unit Tests** in `tests/test_agent_tools.py` and `tests/test_device_controller.py`.

---

### Adding a New Platform Adapter

To support an additional platform (e.g., macOS, Linux Wayland/X11, or iOS WebDriverAgent):

1. Implement a **Hierarchy Parser** that outputs a `UIHierarchy` containing `UIElement` instances with exact bounding boxes.
2. Implement a **Device / OS Controller** with gesture and text injection primitives (`click`, `type_text`, `scroll`, `launch_app`).
3. Define platform-specific **Tool Declarations** and a tool execution dispatcher.
4. Hook the platform switch into `AndroidAgentCLI.handle_platform()` in `src/android_gemini_agent/cli/app.py`.
5. Add unit and integration tests with offline mock fixtures in `tests/`.

---

## 🚀 Submitting a Pull Request

1. **Sync with Main**:
   ```bash
   git fetch origin
   git rebase origin/main
   ```
2. **Run Quality Checks**:
   ```bash
   black --check --line-length 100 src tests examples
   ruff check src tests examples
   python -m pytest -v
   ```
3. **Push to Your Fork**:
   ```bash
   git push origin feature/my-amazing-feature
   ```
4. **Open a Pull Request**:
   - Open a PR against the `main` branch.
   - Fill out the PR template thoroughly.
   - Link any related issues (`Fixes #123`).
   - A maintainer will review your code promptly.

---

## 💬 Community & Questions

- **GitHub Discussions**: Share ideas, workflows, and ask questions in [Discussions](https://github.com/android-gemini-agent/android-gemini-agent/discussions).
- **Issue Tracker**: Report defects or submit feature ideas in [Issues](https://github.com/android-gemini-agent/android-gemini-agent/issues).

Thank you for helping make the Android & Windows Gemini Automation Agent the best open-source GUI automation agent! 🚀
