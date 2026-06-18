# automation-app-damai

Damai-specific workflows live here, not in `automation-kit`.
This repository consumes the public `automation_runner.workflows` surface.

This repository owns:

- Damai workflow names
- Damai URLs and package identifiers
- Damai config validation
- Damai-facing CLI glue

Optional visual challenge capabilities, including OCR and captcha solving,
are injected from `slidex` when needed through the app-layer visual helper
functions in `automation_app_damai.workflow`. Default offline tests do not
require `slidex`, browsers, devices, or network access.

When a production workflow owns a real Playwright page, call
`solve_slider_visual_challenge(...)` with an injected slidex
`VisualChallengeSolver` to build the `PLAYWRIGHT_PAGE` request, solve it, and
convert the result into workflow payload shapes.

GitHub repository: `https://github.com/dengyie/automation-app-damai`
