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
selected implementation.

GitHub repository: `https://github.com/dengyie/automation-app-damai`

Development baseline:
`https://github.com/dengyie/automation-kit/blob/main/docs/development.md`

## Authorized network inspection (task 13)

`tools/inspect_network.py` records a Playwright HAR for one authorized URL,
replaces every value the kit redaction vocabulary names
(`automation_core.redaction`), and keeps only the cleaned artifact:

```bash
python tools/inspect_network.py \
    --url "https://detail.damai.cn/item.htm?id=..." \
    --output artifacts/damai-network/detail.har \
    --wait-seconds 3
```

Raw HARs live only in a local temporary directory and are deleted before the
run returns, so nothing unredacted is ever retained. Response bodies are not
recorded (`record_har_content="omit"` is fixed, not a flag), and the tool also
prints a deduplicated `METHOD path -> status` digest built from the cleaned
document.

The redaction vocabulary is a key-name vocabulary: header/query names
containing cookie, authorization, token or x5sec are replaced, HAR cookie
values are always replaced, but platform-specific signatures (for example
MTOP's `x-sgext` or `_m_h5_tk`) are preserved. Review the artifact before
sharing it.

This is an operator script, not a capability or provider: no workflow imports
it, and production runs never depend on it.
