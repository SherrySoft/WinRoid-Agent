## 📝 Description
<!-- Provide a clear, concise summary of the changes introduced in this pull request. -->

## 🎯 Motivation and Context
<!-- Why is this change required? What problem or feature does it address? -->
<!-- If fixing an open issue, link it here: e.g., 'Fixes #123' or 'Closes #456' -->

## 🔀 Type of Change
<!-- Check all that apply: -->
- [ ] 🐛 Bug fix (non-breaking change fixing an issue)
- [ ] ✨ New feature (non-breaking change adding functionality)
- [ ] 💥 Breaking change (fix or feature causing existing functionality to change)
- [ ] 📚 Documentation update (README, docstrings, examples, architecture guides)
- [ ] 🛠️ Refactoring / Performance improvement / Code cleanup
- [ ] 🧪 Testing & CI/CD workflow improvement

## 📦 Subsystems Affected
<!-- Check all components touched by this PR: -->
- [ ] `adb` (Wireless pairing, socket connection, gestures, text escaping)
- [ ] `parser` (XML UI hierarchy parsing, bounding boxes, AST formatters)
- [ ] `agent` (Gemini decision loop, loop detector, compactor, tool declarations)
- [ ] `windows` (Windows desktop controller, COM UIAutomation, tools)
- [ ] `cli` (Rich interactive REPL, spinners, tables, cards)
- [ ] `examples` (Developer sample scripts)
- [ ] `tests` (Unit, boundary, cross-feature, or E2E tests)

## ✅ Quality & Verification Checklist
<!-- Confirm each item before requesting a review: -->
- [ ] My code follows the repository's coding style guidelines (PEP 8, Black 100 char, Ruff).
- [ ] I have executed `python -m pytest -v` locally and confirmed all **255+ tests pass** (100% pass rate).
- [ ] I have added new unit and/or integration tests for new code paths using offline mocks.
- [ ] I have verified that no live API keys or hardware dependencies are required for tests.
- [ ] I have updated relevant documentation (`README.md`, `CONTRIBUTING.md`, or docstrings) if applicable.

## 📸 Screenshots / Terminal Output (if applicable)
<!-- Paste terminal snippets or screenshots demonstrating the new capability or fix. -->
