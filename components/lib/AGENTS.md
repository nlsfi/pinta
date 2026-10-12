<!-- markdownlint-disable MD041 -->
See root AGENTS.md for shared conventions.

# Agent Instructions — lib

Shared utilities (`pinta_common`: settings, constants, exceptions, feature
flags) used by every other component. It is the lowest layer; it must not
import any other `pinta_*` package.

## Rules

- Declare feature flags in `src/pinta_common/flags.py` and use them with
  `if flags.FLAG_X:`. Outside development mode every declared flag must
  exist in the JSON file referenced by `PINTA_FEATURE_FLAG_CONFIG`; see
  `test_lib/data/feature_flags.json` for an example.
- Changes here affect all components; run `make test` from the repo root.

## Tests

- Unit: `uv run pytest test_lib`
