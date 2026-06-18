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

## 2026-06-18: Phase 4 Damai Slidex Injection Baseline

### Completed

- Added lazy slidex integration helpers in `automation_app_damai.workflow`:
  - `build_slider_visual_request(...)`
  - `visual_result_to_workflow_payload(...)`
- Extended `create_workflow(...)` with an optional `visual_solver` parameter
  while preserving the offline runner behavior.
- Added app-level compatibility tests for the latest slidex
  `PLAYWRIGHT_PAGE` slider request contract and JSON-safe adapter payloads.
- Kept default tests independent from slidex, browsers, devices, and network by
  skipping real slidex checks when slidex is not import-visible.
- Updated `README.md` to describe the current app-layer visual helper path.

### Decision Record

#### Decision: expose helpers instead of running async visual solving inside the smoke workflow

- Problem: slidex visual solving is async and may need a real Playwright page,
  while the current Damai smoke workflow is a synchronous offline
  `ManagedWorkflow`.
- Choice: add request-building and result-conversion helpers at the app layer,
  and let production workflows call them where a real page exists.
- Reason: this satisfies the automation-kit boundary without making the default
  smoke workflow depend on browser runtime state.
- Risk: production Damai flows still need a later live-browser integration pass
  to call the helpers during a real visual challenge.

### Verification

Default offline suite:

```bash
.venv/bin/python -m pytest -q
```

Result:

```text
9 passed, 2 skipped
Total coverage: 85.29%
Required coverage: 80%
```

Slidex compatibility slice:

```bash
PYTHONPATH=/Users/mango/project/codex/automation-app-damai:/Users/mango/project/codex/automation-kit:/Users/mango/project/codex/slidex /opt/homebrew/bin/pytest -q -o addopts='' tests/test_workflow.py -k 'visual_request or visual_result'
```

Result:

```text
2 passed, 4 deselected
```

### Production Code Quality Review

Mode: checkpoint.

Findings: no P0/P1/P2 correctness, boundary, safety, or irreversible operation
issues found in the current diff.

Improvement suggestions:

- Add a later live-browser Damai workflow test when production page ownership is
  available.

Quality score: 90/100.

Status: passed.

### Todo Status

- Damai app-level slidex request helper: done.
- Damai app-level slidex adapter payload helper: done.
- Default offline test independence: done.
- Live browser challenge execution: pending future production workflow phase.

### Next Phase Risk

Real Damai browser flows still need to provide the concrete Playwright page and
decide where visual challenge results enter the user-facing report.

## 2026-06-18: Phase 5 Damai Live Visual Helper

### Completed

- Added `solve_slider_visual_challenge(...)` to connect the existing
  `PLAYWRIGHT_PAGE` request builder, injected slidex visual solver, and workflow
  payload conversion in one production-callable async helper.
- Added offline tests with a fake visual solver and fake page object, proving
  the helper passes page ownership through without starting a browser.
- Kept `create_workflow(...)` unchanged so the default smoke workflow remains
  synchronous and independent from slidex/browser/network requirements.
- Updated README usage guidance for production workflows that already own a
  Playwright page.

### Decision Record

#### Decision: expose an async production helper instead of changing the smoke workflow

- Problem: the current smoke workflow is synchronous and offline, while slidex
  solving is async and requires a real Playwright page in production.
- Choice: add `solve_slider_visual_challenge(...)` as an app-layer helper that
  production flows can call at the point where they own a page.
- Reason: this completes the live-browser call boundary without weakening the
  no-live-default test policy or moving browser concepts into automation-kit.
- Risk: real target-site behavior still needs an opt-in browser E2E run with an
  actual Damai challenge page.

### Verification

Focused live-helper slice:

```bash
PYTHONPATH=/Users/mango/project/codex/automation-app-damai:/Users/mango/project/codex/automation-kit:/Users/mango/project/codex/slidex /opt/homebrew/bin/pytest -q -o addopts='' tests/test_workflow.py -k 'solve_slider_visual_challenge'
```

Result:

```text
2 passed, 6 deselected
```

Default offline suite:

```bash
.venv/bin/python -m pytest -q
```

Result:

```text
11 passed, 3 skipped
Total coverage: 97.62%
Required coverage: 80%
```

### Production Code Quality Review

Mode: checkpoint.

Findings: no P0/P1/P2 correctness, boundary, safety, or irreversible operation
issues found in the current diff.

Improvement suggestions:

- Keep the eventual real browser E2E run opt-in because it depends on target
  site state and CAPTCHA availability.

Quality score: 91/100.

Status: passed.

### Todo Status

- Live browser challenge helper: done.
- Real target-site Playwright E2E: pending opt-in production validation.
