"""HAR cleaning matrix for the authorized network inspection tool (task 13).

``tools/inspect_network.py`` is an operator script, not a package, so it is
loaded from its path. Every test here is offline: the recording test drives a
fake Playwright module and never launches a browser.
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "inspect_network.py"
_MODULE_NAME = "damai_inspect_network_under_test"


def _load_tool():
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


inspect_network = _load_tool()

SECRETS = ("SECRET-HEADER", "SECRET-COOKIE", "SECRET-TOKEN", "SECRET-BODY", "SECRET-REDIRECT")


def _sample_har():
    """A HAR shaped like the MTOP commerce calls the tool exists to inspect."""
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "playwright", "version": "1.60.0"},
            "entries": [
                {
                    "startedDateTime": "2026-10-18T00:00:00.000Z",
                    "time": 12.5,
                    "request": {
                        "method": "POST",
                        "url": (
                            "https://mtop.damai.cn/h5/mtop.trade.order.create/1.0/"
                            "?jsv=2.6.1&token=SECRET-TOKEN&page=1"
                        ),
                        "headers": [
                            {"name": "Authorization", "value": SECRETS[0]},
                            {"name": "Cookie", "value": SECRETS[1]},
                            {"name": "X5sec", "value": SECRETS[0]},
                            {
                                "name": ":path",
                                "value": "/h5/mtop.trade.order.create/1.0/?jsv=2.6.1"
                                "&token=SECRET-TOKEN&page=1",
                            },
                            {"name": "Content-Type", "value": "application/json"},
                            {"name": "Referer", "value": "https://detail.damai.cn/item.htm"},
                        ],
                        "queryString": [
                            {"name": "jsv", "value": "2.6.1"},
                            {"name": "token", "value": SECRETS[2]},
                        ],
                        "cookies": [
                            {"name": "cna", "value": "abc"},
                            {"name": "sid", "value": SECRETS[1]},
                        ],
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({"itemId": 123, "token": SECRETS[3]}),
                        },
                    },
                    "response": {
                        "status": 200,
                        "redirectURL": (
                            "https://mtop.damai.cn/next?token=SECRET-REDIRECT&ok=1"
                        ),
                        "headers": [{"name": "set-cookie", "value": SECRETS[1]}],
                        "cookies": [{"name": "sid", "value": SECRETS[1]}],
                        "content": {"size": 0, "mimeType": "application/json"},
                    },
                    "_meta": {"accessToken": SECRETS[2], "traceId": "keep-me"},
                },
                {
                    "startedDateTime": "2026-10-18T00:00:01.000Z",
                    "time": 3.0,
                    "request": {
                        "method": "GET",
                        "url": "https://mtop.damai.cn/h5/mtop.trade.order.create/1.0/?jsv=2.6.1",
                        "headers": [{"name": "Accept", "value": "*/*"}],
                        "queryString": [{"name": "jsv", "value": "2.6.1"}],
                        "cookies": [],
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "cookies": [],
                        "content": {"size": 0, "mimeType": "application/json"},
                    },
                },
            ],
        }
    }


def _dump(node):
    return json.dumps(node, ensure_ascii=False, sort_keys=True)


# --- vocabulary and cleaning matrix ----------------------------------------


def test_vocabulary_and_placeholder_come_from_kit_redaction():
    from automation_core import redaction

    assert inspect_network.SENSITIVE_KEY_TERMS is redaction.SENSITIVE_KEY_TERMS
    assert inspect_network.REDACTED is redaction.REDACTED


def test_sensitive_names_match_the_kit_substring_vocabulary():
    for name in ("Authorization", "cookie", "Set-Cookie", "X5sec", "x5secdata", "accessToken"):
        assert inspect_network.is_sensitive_name(name) is True
    for name in ("Content-Type", "Referer", "jsv", "page", ""):
        assert inspect_network.is_sensitive_name(name) is False


def test_headers_are_redacted_by_vocabulary_and_others_survive():
    cleaned, _ = inspect_network.sanitize_har(_sample_har())
    headers = cleaned["log"]["entries"][0]["request"]["headers"]
    by_name = {header["name"]: header["value"] for header in headers}

    assert by_name["Authorization"] == "[redacted]"
    assert by_name["Cookie"] == "[redacted]"
    assert by_name["X5sec"] == "[redacted]"
    assert by_name["Content-Type"] == "application/json"
    assert by_name["Referer"] == "https://detail.damai.cn/item.htm"

    response_headers = cleaned["log"]["entries"][0]["response"]["headers"]
    assert response_headers[0]["value"] == "[redacted]"


def test_cookie_values_are_always_redacted_regardless_of_name():
    cleaned, stats = inspect_network.sanitize_har(_sample_har())
    entry = cleaned["log"]["entries"][0]

    assert [cookie["value"] for cookie in entry["request"]["cookies"]] == [
        "[redacted]",
        "[redacted]",
    ]
    assert [cookie["value"] for cookie in entry["response"]["cookies"]] == ["[redacted]"]
    # Cookie names and non-credential fields are kept for interface analysis.
    assert [cookie["name"] for cookie in entry["request"]["cookies"]] == ["cna", "sid"]
    assert stats.cookies == 3


def test_query_string_sensitive_values_are_redacted():
    cleaned, _ = inspect_network.sanitize_har(_sample_har())
    pairs = cleaned["log"]["entries"][0]["request"]["queryString"]

    assert {"name": "jsv", "value": "2.6.1"} in pairs
    assert {"name": "token", "value": "[redacted]"} in pairs


def test_header_values_carrying_a_query_string_are_redacted_too():
    # Real chromium HARs expose the path+query as the HTTP/2 ":path"
    # pseudo-header, which is not sensitive by name but leaks by value.
    har = {
        "log": {
            "entries": [
                {
                    "request": {
                        "url": "https://mtop.damai.cn/h5/api/1.0/",
                        "headers": [
                            {
                                "name": ":path",
                                "value": "/h5/api/1.0/?jsv=2.6.1&token=SECRET-TOKEN",
                            },
                            {"name": "Location", "value": "/next?x5sec=SECRET-HEADER&ok=1"},
                            {"name": "Accept-Language", "value": "zh-CN,zh;q=0.9"},
                        ],
                    }
                }
            ]
        }
    }

    cleaned, stats = inspect_network.sanitize_har(har)
    headers = cleaned["log"]["entries"][0]["request"]["headers"]
    by_name = {header["name"]: header["value"] for header in headers}

    assert by_name[":path"] == "/h5/api/1.0/?jsv=2.6.1&token=[redacted]"
    assert by_name["Location"] == "/next?x5sec=[redacted]&ok=1"
    assert by_name["Accept-Language"] == "zh-CN,zh;q=0.9"
    assert stats.query_params == 2
    assert "SECRET" not in _dump(cleaned)


def test_url_and_redirect_url_query_values_are_redacted():
    cleaned, stats = inspect_network.sanitize_har(_sample_har())
    entry = cleaned["log"]["entries"][0]

    assert "token=[redacted]" in entry["request"]["url"]
    assert "page=1" in entry["request"]["url"]
    assert "jsv=2.6.1" in entry["request"]["url"]
    assert entry["response"]["redirectURL"].endswith("token=[redacted]&ok=1")
    assert stats.urls == 2


def test_nested_sensitive_keys_are_redacted_whole():
    cleaned, _ = inspect_network.sanitize_har(_sample_har())
    meta = cleaned["log"]["entries"][0]["_meta"]

    assert meta["accessToken"] == "[redacted]"
    assert meta["traceId"] == "keep-me"


def test_json_post_body_is_parsed_and_redacted():
    cleaned, stats = inspect_network.sanitize_har(_sample_har())
    text = cleaned["log"]["entries"][0]["request"]["postData"]["text"]
    parsed = json.loads(text)

    assert parsed == {"itemId": 123, "token": "[redacted]"}
    assert stats.keys >= 2  # _meta.accessToken plus the body token


def test_form_encoded_post_body_is_redacted_pairwise():
    har = _sample_har()
    har["log"]["entries"][0]["request"]["postData"] = {
        "mimeType": "application/x-www-form-urlencoded",
        "text": "itemId=123&token=SECRET-TOKEN&x5sec=SECRET-HEADER",
    }

    cleaned, _ = inspect_network.sanitize_har(har)
    text = cleaned["log"]["entries"][0]["request"]["postData"]["text"]

    assert text == "itemId=123&token=[redacted]&x5sec=[redacted]"


def test_unparseable_json_post_body_still_redacts_pairs():
    har = _sample_har()
    har["log"]["entries"][0]["request"]["postData"] = {
        "mimeType": "application/json",
        "text": "{broken&token=SECRET-TOKEN",
    }

    cleaned, _ = inspect_network.sanitize_har(har)
    text = cleaned["log"]["entries"][0]["request"]["postData"]["text"]

    assert "SECRET-TOKEN" not in text
    assert "token=[redacted]" in text


def test_no_secret_survives_anywhere_in_the_cleaned_document():
    cleaned, _ = inspect_network.sanitize_har(_sample_har())
    serialized = _dump(cleaned)

    for secret in SECRETS:
        assert secret not in serialized
    assert "[redacted]" in serialized


def test_sanitize_har_does_not_mutate_its_input():
    har = _sample_har()
    before = _dump(har)

    inspect_network.sanitize_har(har)

    assert _dump(har) == before


def test_sanitize_har_reports_counts_by_location():
    _, stats = inspect_network.sanitize_har(_sample_har())

    assert stats.headers == 4  # request authorization/cookie/x5sec + response set-cookie
    assert stats.cookies == 3
    assert stats.query_params == 2  # request.queryString token + ":path" header token
    assert stats.urls == 2  # request url + response redirectURL
    assert stats.keys == 2  # postData body token + _meta.accessToken
    assert stats.total == 13


def test_sanitize_har_rejects_documents_that_are_not_har():
    for bad in ({}, [], {"log": []}, {"entries": []}, "har"):
        with pytest.raises(ValueError, match="must be an object with a 'log' object"):
            inspect_network.sanitize_har(bad)


def test_summarize_har_dedupes_endpoints_from_cleaned_data():
    cleaned, _ = inspect_network.sanitize_har(_sample_har())

    lines = inspect_network.summarize_har(cleaned)

    assert lines == [
        "POST mtop.damai.cn/h5/mtop.trade.order.create/1.0/ -> 200",
        "GET mtop.damai.cn/h5/mtop.trade.order.create/1.0/ -> 200",
    ]
    assert all("SECRET" not in line for line in lines)


def test_summarize_har_respects_the_limit():
    har = _sample_har()
    har["log"]["entries"] = [
        {
            "request": {"method": "GET", "url": "https://mtop.damai.cn/api/%d" % index},
            "response": {"status": 200},
        }
        for index in range(5)
    ]

    assert len(inspect_network.summarize_har(har, limit=2)) == 2


# --- recording orchestration (fake engine, no browser) ----------------------


class FakeLocator:
    def __init__(self, page):
        self.page = page

    @property
    def first(self):
        return self

    def click(self):
        self.page.script.append(("click",))

    def fill(self, text):
        self.page.script.append(("fill", text))

    def wait_for(self, state=None, timeout=None):
        self.page.script.append(("wait", state, timeout))


class FakePage:
    def __init__(self, *, goto_error=None):
        self.script = []
        self.goto_error = goto_error

    def goto(self, url, wait_until=None):
        if self.goto_error is not None:
            raise self.goto_error
        self.script.append(("goto", url, wait_until))

    def locator(self, selector):
        return FakeLocator(self)

    def screenshot(self, path=None):
        Path(path).write_bytes(b"png")

    def content(self):
        return "<html>damai</html>"


class _FakeHarContext:
    def __init__(self, store, page, kwargs):
        self.store = store
        self.page = page
        self.kwargs = kwargs
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True
        raw_path = Path(self.kwargs["record_har_path"])
        self.store["raw_path"] = raw_path
        raw_path.write_text(json.dumps(self.store["har"]), encoding="utf-8")


class _FakeBrowser:
    def __init__(self, store, page):
        self.store = store
        self.page = page
        self.context = None
        self.closed = False

    def new_context(self, **kwargs):
        self.context = _FakeHarContext(self.store, self.page, kwargs)
        return self.context

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.launch_kwargs = None

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class _FakeDriver:
    def __init__(self, browser):
        self.chromium = _FakeChromium(browser)
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeSyncPlaywright:
    def __init__(self, driver):
        self.driver = driver

    def start(self):
        return self.driver


def _install_fake_engine(monkeypatch, har, *, goto_error=None):
    page = FakePage(goto_error=goto_error)
    store = {"har": har}
    browser = _FakeBrowser(store, page)
    driver = _FakeDriver(browser)
    fake = types.ModuleType("playwright.sync_api")
    fake.sync_playwright = lambda: _FakeSyncPlaywright(driver)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
    return store, browser, driver, page


def test_inspect_url_records_redacts_and_keeps_only_the_cleaned_artifact(
    monkeypatch, tmp_path
):
    store, browser, driver, page = _install_fake_engine(monkeypatch, _sample_har())
    output = tmp_path / "artifacts" / "damai-network.har"

    result = inspect_network.inspect_url(
        "https://detail.damai.cn/item.htm?id=123",
        output=output,
        wait_until="load",
    )

    # Recording options are fixed by the data red line, not by the caller.
    assert browser.context.kwargs["record_har_mode"] == "full"
    assert browser.context.kwargs["record_har_content"] == "omit"
    assert ("goto", "https://detail.damai.cn/item.htm?id=123", "load") in page.script
    assert driver.stopped is True

    # The raw HAR (and its temp directory) is gone; only the cleaned file remains.
    raw_path = store["raw_path"]
    assert not raw_path.exists()
    assert not raw_path.parent.exists()
    assert output.is_file()

    text = output.read_text(encoding="utf-8")
    for secret in SECRETS:
        assert secret not in text
    assert "[redacted]" in text

    assert result.output == output
    assert result.entries == 2
    assert result.redactions.total > 0
    assert result.endpoints == (
        "POST mtop.damai.cn/h5/mtop.trade.order.create/1.0/ -> 200",
        "GET mtop.damai.cn/h5/mtop.trade.order.create/1.0/ -> 200",
    )


def test_inspect_url_defaults_to_headless_domcontentloaded(monkeypatch, tmp_path):
    _, _, driver, page = _install_fake_engine(monkeypatch, _sample_har())

    inspect_network.inspect_url("https://detail.damai.cn/item.htm", output=tmp_path / "a.har")

    assert driver.chromium.launch_kwargs == {"headless": True}
    assert ("goto", "https://detail.damai.cn/item.htm", "domcontentloaded") in page.script


def test_inspect_url_reports_navigation_failure_and_writes_nothing(monkeypatch, tmp_path):
    store, _, driver, _ = _install_fake_engine(
        monkeypatch, _sample_har(), goto_error=RuntimeError("net::ERR_NAME_NOT_RESOLVED")
    )
    output = tmp_path / "a.har"

    with pytest.raises(RuntimeError, match="navigation failed"):
        inspect_network.inspect_url("https://detail.damai.cn/item.htm", output=output)

    assert not output.exists()
    assert driver.stopped is True
    assert not store["raw_path"].exists()


def test_inspect_url_raises_when_no_har_was_written(monkeypatch, tmp_path):
    _install_fake_engine(monkeypatch, _sample_har())

    def no_write(self):
        self.closed = True

    monkeypatch.setattr(_FakeHarContext, "close", no_write, raising=True)

    with pytest.raises(RuntimeError, match="did not write a HAR file"):
        inspect_network.inspect_url("https://detail.damai.cn/item.htm", output=tmp_path / "a.har")


def test_inspect_url_refuses_recordings_that_kept_response_bodies(monkeypatch, tmp_path):
    har = _sample_har()
    har["log"]["entries"][0]["response"]["content"]["text"] = '{"token": "SECRET-BODY"}'
    _install_fake_engine(monkeypatch, har)
    output = tmp_path / "a.har"

    with pytest.raises(RuntimeError, match="recording kept response bodies"):
        inspect_network.inspect_url("https://detail.damai.cn/item.htm", output=output)

    assert not output.exists()


def test_inspect_url_rejects_missing_or_non_http_urls(tmp_path):
    for bad in ("", "   ", None, "file:///etc/passwd", "chrome://settings"):
        with pytest.raises(ValueError):
            inspect_network.inspect_url(bad, output=tmp_path / "a.har")


def test_inspect_url_rejects_unknown_engine(monkeypatch, tmp_path):
    _install_fake_engine(monkeypatch, _sample_har())

    with pytest.raises(ValueError, match="browser_engine must be one of"):
        inspect_network.inspect_url(
            "https://detail.damai.cn/item.htm", output=tmp_path / "a.har", engine="camoufox"
        )


def test_inspect_url_reports_unreadable_har(monkeypatch, tmp_path):
    _install_fake_engine(monkeypatch, _sample_har())

    def write_broken(self):
        self.closed = True
        Path(self.kwargs["record_har_path"]).write_text("{not json", encoding="utf-8")

    monkeypatch.setattr(_FakeHarContext, "close", write_broken, raising=True)

    with pytest.raises(RuntimeError, match="unreadable HAR recording"):
        inspect_network.inspect_url("https://detail.damai.cn/item.htm", output=tmp_path / "a.har")


# --- CLI --------------------------------------------------------------------


def test_cli_prints_counts_and_endpoints(monkeypatch, tmp_path, capsys):
    output = tmp_path / "clean.har"

    def fake_inspect(url, **kwargs):
        return inspect_network.HarInspectionResult(
            url=url,
            output=output,
            entries=2,
            redactions=inspect_network.RedactionStats(headers=4, cookies=3),
            endpoints=("POST mtop.damai.cn/api -> 200",),
        )

    monkeypatch.setattr(inspect_network, "inspect_url", fake_inspect)

    assert inspect_network.main(["--url", "https://detail.damai.cn/x", "--output", str(output)]) == 0

    stdout = capsys.readouterr().out
    assert "entries=2" in stdout
    assert "headers=4" in stdout
    assert "cookies=3" in stdout
    assert "POST mtop.damai.cn/api -> 200" in stdout
    assert str(output) in stdout


def test_cli_reports_tool_errors_with_exit_code_two(monkeypatch, tmp_path, capsys):
    def boom(url, **kwargs):
        raise RuntimeError("navigation failed: timeout")

    monkeypatch.setattr(inspect_network, "inspect_url", boom)

    code = inspect_network.main(
        ["--url", "https://detail.damai.cn/x", "--output", str(tmp_path / "a.har")]
    )

    assert code == 2
    assert "inspect_network: navigation failed" in capsys.readouterr().err


def test_cli_rejects_unknown_engine_before_running():
    with pytest.raises(SystemExit) as excinfo:
        inspect_network.main(
            ["--url", "https://detail.damai.cn/x", "--output", "a.har", "--engine", "camoufox"]
        )

    assert excinfo.value.code == 2


def test_cli_requires_url_and_output():
    with pytest.raises(SystemExit) as excinfo:
        inspect_network.main([])

    assert excinfo.value.code == 2
