# automation-app-damai

Damai-specific workflows live here, not in `automation-kit`.
This repository consumes the public `automation_runner.workflows` surface.

This repository owns:

- Damai workflow names
- Damai URLs and package identifiers
- Damai config validation
- Damai-facing CLI glue

Optional visual challenge capabilities, including OCR and captcha solving,
are injected through `automation_core.capabilities`. Slidex is the recommended
provider, but the workflow only depends on the platform request/result
contract. Default offline tests do not require `slidex`, browsers, devices, or
network access.

When a production workflow owns a real Playwright page, call
`solve_slider_capability(...)` with an injected `CapabilityExecutor`. Register
`SlidexVisualCapability` at the application composition root when Slidex is the
selected implementation. The older `solve_slider_visual_challenge(...)` entry
remains available for compatibility.

GitHub repository: `https://github.com/dengyie/automation-app-damai`

Development baseline:
`https://github.com/dengyie/automation-kit/blob/main/docs/development.md`
