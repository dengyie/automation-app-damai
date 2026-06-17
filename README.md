# automation-app-damai

Damai-specific workflows live here, not in `automation-kit`.
This repository consumes the public `automation_runner.workflows` surface.

This repository owns:

- Damai workflow names
- Damai URLs and package identifiers
- Damai config validation
- Damai-facing CLI glue

Optional visual challenge capabilities, including OCR and captcha solving,
should be injected from `slidex` when needed. This repository must not depend
on the archived `automation-plugin-ocr` package.

GitHub repository: `https://github.com/dengyie/automation-app-damai`
