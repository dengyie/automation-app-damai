# Development Log

## 2026-06-17: Phase 2 Damai Application Consumer

### Completed

- Created `automation-app-damai` as the first business application repository
  consuming `automation-kit`.
- Added package metadata, pytest coverage configuration, and local venv-based
  verification support.
- Added `automation_app_damai.workflow.create_workflow(...)` as the first real
  external consumer of `automation_runner.workflows`.
- Added `DamaiAppConfig` to keep Damai channel-specific config validation in
  the application layer.
- Added `build_context_and_options(...)` as a minimal app-side runner bridge.
- Added offline tests for imports, workflow creation, config validation, and
  CLI context/options wiring.

### Decision Record

#### Decision: keep the first consumer deliberately small

- Problem: Phase 2 could easily drift into full Damai business migration and
  obscure whether the new public runner surface is actually reusable.
- Choice: implement a thin external consumer first, with offline smoke-level
  behavior only.
- Reason: this phase needs to prove repository boundaries and public contracts
  before migrating real production business flows.
- Risk: the repository is not yet feature-complete for Damai production usage,
  so later phases must expand workflows without moving shared logic back into
  `automation-kit`.

#### Decision: bootstrap the repo with local virtualenv commands

- Problem: the environment does not expose a ready-to-use global Poetry
  command.
- Choice: create `.venv` locally and install `pytest`, `pytest-cov`, and the
  editable `automation-kit` dependency directly.
- Reason: this gives deterministic, isolated verification for the new sibling
  repository and keeps execution moving.
- Risk: Poetry remains the documented package manager, so CI should later
  verify the same setup through Poetry as well.

#### Decision: keep `poetry.lock` after the final verification pass

- Problem: the final completion audit needs stronger proof than raw venv runs;
  it must show that the documented `poetry install && poetry run pytest` path
  works too.
- Choice: install Poetry in the local venv, run the Poetry-managed path, and
  keep the resulting `poetry.lock`.
- Reason: the repository now has CI based on Poetry, so the lockfile improves
  reproducibility instead of being incidental noise.
- Risk: dependency upgrades now need intentional lockfile changes rather than
  loose dev-environment drift.

### Verification

```bash
/Users/mango/project/codex/automation-app-damai/.venv/bin/python -m pytest -q
```

Result:

```text
6 passed
Total coverage: 95.45%
Required coverage: 80%
```

### Follow-up Note

- Optional plugin integration checks should run with the repository's full test
  suite instead of a single test file so coverage thresholds remain meaningful
  and do not create false failures.
- Final audit also confirmed the documented Poetry path:
  `poetry install && poetry run pytest -q`.

## 2026-06-18: Slidex Visual Platform Alignment

### Completed

- Replaced the app-side optional OCR capability label with a generic
  `visual_challenges` capability.
- Removed test-time usage of `automation_plugin_ocr`.
- Documented `slidex` as the future source for OCR and captcha visual
  challenge capabilities.

### Decision Record

#### Decision: consume visual challenge solvers by injection

- Problem: `slidex` is becoming the ecosystem visual platform, but its new OCR
  and unified vision APIs are being developed independently.
- Choice: keep this application dependency-free for now and expose a generic
  `visual_solver` capability slot.
- Reason: Damai can adopt `slidex.vision` as soon as that API lands without
  taking a hard dependency on an unfinished interface today.
- Risk: a later integration pass must wire the concrete `slidex` solver and
  add compatibility tests.
