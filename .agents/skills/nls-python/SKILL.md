---
name: nls-python
description: NLS Python coding conventions for .py changes, including type hints, docstring and comment rules, and pytest testing patterns.
---

## Type hints  <!-- markdownlint-disable-line MD041 -->

- All functions must have type hints for parameters and return value.
- Use modern union syntax, for example `str | None` instead of `Optional[str]`.
- Use the `typing` module for complex type definitions.

## Comments

- Keep comments minimal.
- Public functions and methods should include a concise docstring.
- Do not add comments in tests.
- Never write comments that explain obvious code behavior; refactor the code instead.
- Never document parameters in comments; rely on type hints.
- Never use section-separator comments; extract code into functions.

## Testing

- Use module-level test functions only; do not use test classes.
- Use descriptive names in the form `test_<action>_<condition>_<expected_result>`.
- Do not add comments in test code.
- Use `pytest` fixtures for setup and teardown.
- Use `pytest.mark.parametrize` when testing multiple input values.
- Prefer pytest-mock's `mocker.patch` over `mocker.patch.object` and
 `monkeypatch.setattr`; annotate `mocker` as `pytest_mock.MockerFixture`.
- When only observing whether or how a function or method is called, prefer
 `mocker.spy` if running its real implementation is safe and appropriate; a spy
 records calls while preserving that behavior.
- Use `mocker.patch` when the test needs to replace behavior, isolate side effects,
 or control return values or exceptions.
- Patch dependencies where they are looked up by the module under test, usually the
 imported symbol or module, rather than at their original definition.
- Use `MagicMock` imported from `unittest.mock` instead of `Mock`.
