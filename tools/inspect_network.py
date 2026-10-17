#!/usr/bin/env python3
"""Authorized network inspection for damai (task 13, L4 operator tool).

Records a Playwright HAR for one authorized URL, replaces every value the kit
redaction vocabulary names as sensitive, and writes only the cleaned artifact.
The raw HAR exists solely inside a local temporary directory and is deleted
before the call returns.

Two consequences of that design, both deliberate:

* This is not a capability and not a provider. A single inspection need does
  not justify an abstraction, and production workflows must not import it.
* Response bodies are never recorded (``HAR_RECORD_OPTIONS`` is fixed, not a
  CLI flag), so the cleaner never has to scan arbitrary body text. Do not
  re-record with ``record_har_content="embed"`` and reuse this cleaner - the
  body would pass through untouched.

The redaction vocabulary itself lives in ``automation_core.redaction`` and is
imported here rather than restated, so the term list stays single-source. It is
a key-name vocabulary: header/query names containing cookie, authorization,
token or x5sec are replaced, HAR cookie values are always replaced, and other
platform-specific signatures are preserved - review the artifact before
sharing it.
"""

import argparse
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote_plus, urlsplit, urlunsplit

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:  # runnable as `python tools/inspect_network.py`
    sys.path.insert(0, str(_REPO_ROOT))

from automation_app_damai.config import validate_browser_engine  # noqa: E402
from automation_app_damai.live_factory import (  # noqa: E402
    HAR_RECORD_OPTIONS,
    create_live_session_factory,
)
from automation_core.redaction import REDACTED, SENSITIVE_KEY_TERMS  # noqa: E402

INSPECTABLE_SCHEMES = ("http", "https")

_SUMMARY_LIMIT = 20
_URL_KEYS = ("url", "redirectURL")
_NAMED_VALUE_KEYS = ("queryString", "params")
_QUERY_PARAM_RE = re.compile(r"([^&=#]+)=([^&#]*)")


def is_sensitive_name(name: Any) -> bool:
    """Return True when ``name`` matches the kit's sensitive term list."""
    lowered = str(name).lower()
    return any(term in lowered for term in SENSITIVE_KEY_TERMS)


def _redact_query(query: str) -> Tuple[str, int]:
    """Redact the values of form/query pairs whose name is a sensitive term."""
    count = 0

    def replace(match: "re.Match") -> str:
        nonlocal count
        if is_sensitive_name(unquote_plus(match.group(1))):
            count += 1
            return match.group(1) + "=" + REDACTED
        return match.group(0)

    return _QUERY_PARAM_RE.sub(replace, query), count


def _redact_url(url: str) -> Tuple[str, int]:
    """Redact sensitive query values inside ``url``, leaving it otherwise intact."""
    parts = urlsplit(url)
    if not parts.query:
        return url, 0
    query, count = _redact_query(parts.query)
    if not count:
        return url, 0
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment)), count


def _try_json(text: str) -> Optional[Any]:
    stripped = text.lstrip()
    if not stripped or stripped[0] not in ("{", "["):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _reject_response_bodies(har: Any) -> None:
    """Fail loudly when a recording kept response bodies.

    The cleaner is a key/pair vocabulary, so it cannot sanitize arbitrary body
    text. The tool therefore refuses to produce an artifact from any recording
    that carries bodies, instead of quietly copying them through.
    """
    entries = har.get("log", {}).get("entries", []) if isinstance(har, dict) else []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        response = entry.get("response")
        if not isinstance(response, dict):
            continue
        content = response.get("content")
        if isinstance(content, dict) and isinstance(content.get("text"), str):
            raise RuntimeError(
                "recording kept response bodies; expected record_har_content=%r"
                % HAR_RECORD_OPTIONS.get("record_har_content")
            )


@dataclass(frozen=True)
class RedactionStats:
    """How many values the cleaner replaced, by HAR location."""

    headers: int = 0
    cookies: int = 0
    query_params: int = 0
    keys: int = 0
    urls: int = 0

    @property
    def total(self) -> int:
        return self.headers + self.cookies + self.query_params + self.keys + self.urls


@dataclass(frozen=True)
class HarInspectionResult:
    """Outcome of one recorded inspection."""

    url: str
    output: Path
    entries: int
    redactions: RedactionStats
    endpoints: Tuple[str, ...] = ()


class _Cleaner:
    """Recursive HAR cleaner; never mutates the input document."""

    def __init__(self) -> None:
        self._counts = {
            "headers": 0,
            "cookies": 0,
            "query_params": 0,
            "keys": 0,
            "urls": 0,
        }

    def clean(self, node: Any) -> Any:
        if isinstance(node, dict):
            return self._clean_mapping(node)
        if isinstance(node, list):
            return [self.clean(item) for item in node]
        return node

    def _count(self, kind: str, amount: int = 1) -> None:
        self._counts[kind] += amount

    def _clean_mapping(self, node: Dict[Any, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for key, value in node.items():
            output_key = key if isinstance(key, str) else str(key)
            # Structural keys are matched before the vocabulary so the HAR
            # "cookies" key is treated as a cookie list, not as a scalar hit.
            if output_key == "headers":
                cleaned[output_key] = self._clean_named_values(value, "headers")
            elif output_key == "cookies":
                cleaned[output_key] = self._clean_named_values(
                    value, "cookies", redact_all=True
                )
            elif output_key in _NAMED_VALUE_KEYS:
                cleaned[output_key] = self._clean_named_values(value, "query_params")
            elif output_key in _URL_KEYS and isinstance(value, str):
                redacted, redacted_count = _redact_url(value)
                cleaned[output_key] = redacted
                self._count("urls", redacted_count)
            elif output_key == "postData" and isinstance(value, dict):
                cleaned[output_key] = self._clean_post_data(value)
            elif is_sensitive_name(output_key):
                cleaned[output_key] = REDACTED
                self._count("keys")
            else:
                cleaned[output_key] = self.clean(value)
        return cleaned

    def _clean_named_values(
        self, values: Any, kind: str, redact_all: bool = False
    ) -> Any:
        if not isinstance(values, list):
            return self.clean(values)
        cleaned: List[Any] = []
        for item in values:
            if not isinstance(item, dict):
                cleaned.append(self.clean(item))
                continue
            entry = self._clean_mapping(item)
            if "value" in entry and (redact_all or is_sensitive_name(entry.get("name"))):
                entry["value"] = REDACTED
                self._count(kind)
            elif isinstance(entry.get("value"), str):
                # Values such as the HTTP/2 ":path" pseudo-header or "Location"
                # carry the same query string as the URL; clean pairs here too.
                redacted, redacted_count = _redact_query(entry["value"])
                if redacted_count:
                    entry["value"] = redacted
                    self._count("query_params", redacted_count)
            cleaned.append(entry)
        return cleaned

    def _clean_post_data(self, data: Dict[Any, Any]) -> Dict[str, Any]:
        cleaned: Dict[str, Any] = {}
        for key, value in data.items():
            output_key = key if isinstance(key, str) else str(key)
            if output_key == "text" and isinstance(value, str):
                cleaned[output_key] = self._clean_body_text(value)
            elif output_key == "params":
                cleaned[output_key] = self._clean_named_values(value, "query_params")
            elif is_sensitive_name(output_key):
                cleaned[output_key] = REDACTED
                self._count("keys")
            else:
                cleaned[output_key] = self.clean(value)
        return cleaned

    def _clean_body_text(self, text: str) -> str:
        parsed = _try_json(text)
        if parsed is not None:
            return json.dumps(self.clean(parsed), ensure_ascii=False, separators=(",", ":"))
        redacted, count = _redact_query(text)
        self._count("query_params", count)
        return redacted

    def stats(self) -> RedactionStats:
        return RedactionStats(**self._counts)


def sanitize_har(har: Dict[str, Any]) -> Tuple[Dict[str, Any], RedactionStats]:
    """Return ``(cleaned_har, stats)``; ``har`` itself is left untouched."""
    if not isinstance(har, dict) or not isinstance(har.get("log"), dict):
        raise ValueError("HAR document must be an object with a 'log' object")
    cleaner = _Cleaner()
    return cleaner.clean(har), cleaner.stats()


def summarize_har(har: Dict[str, Any], limit: int = _SUMMARY_LIMIT) -> List[str]:
    """Return deduplicated ``METHOD path -> status`` lines from a cleaned HAR.

    This is the interface-semantics material the tool exists for; it is built
    from the cleaned document, so no sensitive query value can appear in it.
    """
    entries = har.get("log", {}).get("entries", [])
    lines: List[str] = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        parts = urlsplit(str(request.get("url", "")))
        method = str(request.get("method", "?"))
        status = response.get("status")
        shape = (method, parts.netloc + (parts.path or "/"), status)
        if shape in seen:
            continue
        seen.add(shape)
        suffix = " -> %s" % status if status else ""
        lines.append("%s %s%s" % (shape[0], shape[1], suffix))
        if len(lines) >= limit:
            break
    return lines


def inspect_url(
    url: str,
    *,
    output: Path,
    engine: str = "playwright",
    headless: bool = True,
    wait_seconds: float = 0.0,
    wait_until: str = "domcontentloaded",
) -> HarInspectionResult:
    """Record HAR for ``url``, clean it, and write the artifact to ``output``."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url is required")
    scheme = urlsplit(url).scheme.lower()
    if scheme not in INSPECTABLE_SCHEMES:
        raise ValueError(
            "only %s URLs can be inspected" % "/".join(INSPECTABLE_SCHEMES)
        )
    normalized_engine = validate_browser_engine(engine)
    output = Path(output)

    with tempfile.TemporaryDirectory(prefix="damai-har-") as raw_dir:
        raw_path = Path(raw_dir) / "network.har"
        factory = create_live_session_factory(
            engine=normalized_engine,
            headless=headless,
            record_har_path=raw_path,
        )
        session = factory()
        session.start()
        try:
            opened = session.execute_action("open", url=url, wait_until=wait_until)
            if not opened.success:
                raise RuntimeError("navigation failed: %s" % opened.message)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
        finally:
            # Closing the session closes the context, which flushes the HAR.
            session.stop()
        if not raw_path.is_file():
            raise RuntimeError("playwright did not write a HAR file")
        try:
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("unreadable HAR recording: %s" % exc) from exc
        _reject_response_bodies(raw)

    cleaned, stats = sanitize_har(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return HarInspectionResult(
        url=url,
        output=output,
        entries=len(cleaned["log"].get("entries", [])),
        redactions=stats,
        endpoints=tuple(summarize_har(cleaned)),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inspect_network",
        description=(
            "Record an authorized Playwright HAR, redact the kit's sensitive "
            "vocabulary, and write only the cleaned artifact."
        ),
    )
    parser.add_argument("--url", required=True, help="authorized page URL to record")
    parser.add_argument("--output", required=True, help="path for the cleaned HAR artifact")
    parser.add_argument(
        "--engine",
        default="playwright",
        choices=("playwright", "patchright"),
        help="browser engine used for the recording",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="run with a visible browser window (default headless)",
    )
    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=0.0,
        help="extra seconds to keep recording after the page loads (for XHR trails)",
    )
    parser.add_argument(
        "--wait-until",
        default="domcontentloaded",
        choices=("commit", "domcontentloaded", "load", "networkidle"),
        help="navigation readiness gate for the recorded page",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = inspect_url(
            args.url,
            output=Path(args.output),
            engine=args.engine,
            headless=not args.headed,
            wait_seconds=args.wait_seconds,
            wait_until=args.wait_until,
        )
    except (ValueError, RuntimeError, ImportError, OSError) as exc:
        print("inspect_network: %s" % exc, file=sys.stderr)
        return 2
    stats = result.redactions
    print(
        "entries=%d redacted(headers=%d cookies=%d query=%d keys=%d urls=%d)"
        % (
            result.entries,
            stats.headers,
            stats.cookies,
            stats.query_params,
            stats.keys,
            stats.urls,
        )
    )
    for line in result.endpoints:
        print("  %s" % line)
    print("cleaned HAR artifact: %s" % result.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
