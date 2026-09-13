"""Live web session factory and browser engine selection tests (offline)."""
import sys
import types

import pytest

from adapters.errors import AdapterArtifactError, AdapterStartupError
from automation_app_damai.config import DamaiAppConfig, validate_browser_engine
from automation_app_damai.live_factory import (
    PlaywrightSession,
    create_live_session_factory,
    validate_engine,
)


class FakeLocator:
    def __init__(self, script, key):
        self.script = script
        self.key = key

    @property
    def first(self):
        return self

    def click(self):
        self.script.append(("click", self.key))

    def fill(self, text):
        self.script.append(("fill", self.key, text))

    def wait_for(self, state=None, timeout=None):
        self.script.append(("wait", self.key, state, timeout))


class FakePage:
    def __init__(self, *, screenshot_ok=True):
        self.script = []
        self.screenshot_ok = screenshot_ok
        self.current_url = None

    def locator(self, selector):
        return FakeLocator(self.script, selector)

    def goto(self, url, wait_until=None):
        self.script.append(("goto", url, wait_until))
        self.current_url = url

    def screenshot(self, path=None):
        if not self.screenshot_ok:
            raise RuntimeError("page closed")
        with open(path, "wb") as handle:
            handle.write(b"png")

    def content(self):
        return "<html>damai</html>"


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.closed = False

    def new_context(self):
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.launch_kwargs = None

    def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class FakeDriver:
    def __init__(self, browser):
        self.chromium = FakeChromium(browser)
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeSyncPlaywright:
    def __init__(self, driver):
        self.driver = driver
        self.started = False

    def start(self):
        self.started = True
        return self.driver


def _install_fake_engine(monkeypatch, name, page):
    driver = FakeDriver(FakeBrowser(FakeContext(page)))
    fake = types.ModuleType(name)
    fake.sync_playwright = lambda: FakeSyncPlaywright(driver)
    monkeypatch.setitem(sys.modules, name, fake)
    return driver


# --- engine selection -------------------------------------------------------


def test_validate_engine_normalizes_and_rejects():
    assert validate_engine(" Patchright ") == "patchright"
    assert validate_engine("playwright") == "playwright"
    with pytest.raises(ValueError, match="browser engine must be one of"):
        validate_engine("camoufox")
    with pytest.raises(ValueError, match="browser engine must be one of"):
        validate_engine(None)


def test_config_browser_engine_default_and_validation():
    config = DamaiAppConfig(channel="web", url="https://example.test/damai")
    config.validate()

    assert config.browser_engine == "playwright"
    assert validate_browser_engine("patchright") == "patchright"

    with pytest.raises(ValueError, match="browser_engine"):
        DamaiAppConfig(
            channel="web",
            url="https://example.test/damai",
            browser_engine="stealth",
        ).validate()


def test_live_factory_dispatches_engines(monkeypatch):
    page = FakePage()
    playwright_driver = _install_fake_engine(monkeypatch, "playwright.sync_api", page)
    factory = create_live_session_factory(engine="playwright", headless=False)
    session = factory()
    session.start()

    assert session.info.driver_name == "playwright"
    assert session.page is page
    assert playwright_driver.chromium.launch_kwargs == {"headless": False}
    session.stop()
    assert playwright_driver.stopped is True

    patchright_page = FakePage()
    patchright_driver = _install_fake_engine(
        monkeypatch, "patchright.sync_api", patchright_page
    )
    patchright_session = create_live_session_factory(engine="patchright")()
    patchright_session.start()
    assert patchright_session.page is patchright_page
    assert patchright_driver.stopped is False
    patchright_session.stop()
    assert patchright_driver.stopped is True


def test_live_factory_rejects_unknown_engine():
    with pytest.raises(ValueError, match="browser engine must be one of"):
        create_live_session_factory(engine="undetected")


def test_live_factory_missing_sdk_raises_actionable_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)

    factory = create_live_session_factory(engine="playwright")

    with pytest.raises(ImportError, match="pip install"):
        factory()


def test_live_factory_launch_failure_raises_startup_error(monkeypatch):
    fake = types.ModuleType("playwright.sync_api")

    def broken():
        raise RuntimeError("no browser binary")

    fake.sync_playwright = broken
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)

    factory = create_live_session_factory(engine="playwright")

    with pytest.raises(AdapterStartupError):
        factory()


# --- PlaywrightSession actions and artifacts --------------------------------


def test_open_click_type_wait_flow_against_fake_page():
    page = FakePage()
    session = PlaywrightSession(page)

    session.start()
    assert session.execute_action("open", url="https://example.test/damai").success
    assert session.execute_action(
        "wait_for_element", selector=".buy", timeout=2
    ).success
    assert session.execute_action("click", selector=".buy").success
    assert session.execute_action(
        "type_text", selector=".qty", text="2"
    ).success

    assert ("goto", "https://example.test/damai", "domcontentloaded") in page.script
    assert ("fill", ".qty", "") in page.script
    assert ("fill", ".qty", "2") in page.script


def test_xpath_by_dispatches_xpath_engine():
    page = FakePage()
    session = PlaywrightSession(page)

    result = session.execute_action("click", selector="//button", by="xpath")

    assert result.success is True
    assert ("click", "xpath=//button") in page.script


def test_actions_validate_required_parameters():
    session = PlaywrightSession(FakePage())

    assert session.execute_action("open").success is False
    assert session.execute_action("click").success is False
    assert session.execute_action("type_text", selector=".x").success is False
    assert session.execute_action("type_text", selector=".x", text=None).success is False
    assert (
        session.execute_action("wait_for_element", selector=".x").success is True
    )  # default timeout 5s is a locator wait, validated above


def test_unknown_action_fails_cleanly():
    session = PlaywrightSession(FakePage())

    result = session.execute_action("hover", selector=".x")

    assert result.success is False
    assert "unsupported playwright action" in result.message


def test_capture_artifact_screenshot_and_page_source(tmp_path):
    page = FakePage()
    session = PlaywrightSession(page, artifact_root=tmp_path)

    shot = session.capture_artifact("screenshot", "home.png")
    source = session.capture_artifact("page_source", "home.html")

    assert shot.path.is_file()
    assert source.path.read_text(encoding="utf-8") == "<html>damai</html>"


def test_capture_artifact_failures(tmp_path):
    page = FakePage(screenshot_ok=False)
    session = PlaywrightSession(page, artifact_root=tmp_path)

    with pytest.raises(AdapterArtifactError):
        session.capture_artifact("screenshot", "home.png")

    with pytest.raises(AdapterArtifactError):
        session.capture_artifact("ui_tree", "tree.xml")


def test_stop_is_idempotent_and_closes_owned_resources():
    page = FakePage()
    driver = FakeDriver(FakeBrowser(FakeContext(page)))
    session = PlaywrightSession(
        page,
        teardown=(driver.chromium.browser, driver),
    )
    session.start()

    session.stop()
    session.stop()

    assert driver.chromium.browser.closed is True
    assert driver.stopped is True
