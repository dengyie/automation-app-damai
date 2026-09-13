"""Live web session factory for damai (stage-5 live E2E infrastructure).

Holds a real browser page for authorized live runs. The engine is
switchable: ``playwright`` is the default, ``patchright`` is the drop-in
stealth fork for authorized environments. Browser SDKs are imported
lazily so default offline tests never require them.

The sync API is used deliberately: ``DriverSession`` actions are
synchronous and ``WorkflowRuntime.run()`` is the documented synchronous
facade (automation-kit development.md §3.3); an async browser instance
would need a loop bridge that violates the sync facade boundary.
"""

from pathlib import Path
from typing import Any, Callable, Optional, Sequence, Tuple

from adapters.errors import AdapterArtifactError, AdapterStartupError
from automation_core.drivers import ActionResult, ArtifactHandle, SessionInfo

from automation_app_damai.config import validate_browser_engine

SessionFactory = Callable[[], "PlaywrightSession"]

CloseHooks = Tuple[Any, ...]


def _close_resource(resource: Any) -> None:
    """Invoke the resource's single close hook (``close`` before ``stop``)."""
    for hook in ("close", "stop"):
        method = getattr(resource, hook, None)
        if callable(method):
            method()
            return


def _import_sync_playwright(engine: str):
    module_name = (
        "playwright.sync_api" if engine == "playwright" else "patchright.sync_api"
    )
    try:
        module = __import__(module_name, fromlist=["sync_playwright"])
    except ImportError as exc:
        raise ImportError(
            "%s is required for browser engine %r; pip install %s"
            % (module_name, engine, engine)
        ) from exc
    return module.sync_playwright


class PlaywrightSession:
    """DriverSession implementation over a Playwright or patchright page."""

    SUPPORTED_ARTIFACT_TYPES = frozenset({"screenshot", "page_source"})

    def __init__(
        self,
        page: Any,
        *,
        identifier: str = "damai-web-live",
        artifact_root: Optional[Path] = None,
        teardown: Optional[Sequence[Any]] = None,
    ):
        self.page = page
        self.info = SessionInfo(
            driver_name="playwright",
            platform="web",
            identifier=identifier,
        )
        self.artifact_root = Path(artifact_root or "artifacts/damai-live")
        self._teardown: CloseHooks = tuple(teardown or ())
        self._started = False

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        # Close every owned resource even if one close fails; the first
        # exception then propagates so the runtime records a cleanup
        # failure (development.md §4.6) instead of the leak being silent.
        errors = []
        for resource in self._teardown:
            try:
                _close_resource(resource)
            except Exception as exc:  # noqa: BLE001 - collected, then raised
                errors.append(exc)
        self._started = False
        if errors:
            raise errors[0]

    def execute_action(self, action_name: str, **kwargs: Any) -> ActionResult:
        if action_name == "open":
            return self._open(**kwargs)
        if action_name == "click":
            return self._click(**kwargs)
        if action_name == "type_text":
            return self._type_text(**kwargs)
        if action_name == "wait_for_element":
            return self._wait_for_element(**kwargs)
        return ActionResult(
            False,
            "unsupported playwright action: %s" % action_name,
        )

    def _locator(self, selector: Any, by: Optional[str] = None):
        if by == "xpath":
            return self.page.locator("xpath=%s" % selector)
        return self.page.locator(selector)

    def _open(self, **kwargs: Any) -> ActionResult:
        url = kwargs.get("url")
        if not url:
            return ActionResult(False, "missing required parameter: url")
        try:
            self.page.goto(url, wait_until=kwargs.get("wait_until", "domcontentloaded"))
        except Exception as exc:
            return ActionResult(False, "open failed: %s" % exc)
        return ActionResult(True, "open", data={"url": url})

    def _click(self, **kwargs: Any) -> ActionResult:
        selector = kwargs.get("selector")
        if not selector:
            return ActionResult(False, "missing required parameter: selector")
        try:
            self._locator(selector, kwargs.get("by")).first.click()
        except Exception as exc:
            return ActionResult(False, "click failed: %s" % exc)
        return ActionResult(True, "click")

    def _type_text(self, **kwargs: Any) -> ActionResult:
        selector = kwargs.get("selector")
        text = kwargs.get("text")
        if not selector:
            return ActionResult(False, "missing required parameter: selector")
        if text is None:
            return ActionResult(False, "missing required parameter: text")
        try:
            locator = self._locator(selector, kwargs.get("by")).first
            if kwargs.get("clear", True):
                locator.fill("")
            locator.fill(str(text))
        except Exception as exc:
            return ActionResult(False, "type_text failed: %s" % exc)
        return ActionResult(True, "type_text")

    def _wait_for_element(self, **kwargs: Any) -> ActionResult:
        selector = kwargs.get("selector")
        if not selector:
            return ActionResult(False, "missing required parameter: selector")
        timeout_ms = float(kwargs.get("timeout", 5.0)) * 1000.0
        try:
            self._locator(selector, kwargs.get("by")).first.wait_for(
                state="visible",
                timeout=timeout_ms,
            )
        except Exception as exc:
            return ActionResult(False, "wait_for_element failed: %s" % exc)
        return ActionResult(True, "wait_for_element")

    def capture_artifact(self, artifact_type: str, name: str) -> ArtifactHandle:
        if artifact_type not in self.SUPPORTED_ARTIFACT_TYPES:
            raise AdapterArtifactError(
                "unsupported playwright artifact type: %s" % artifact_type
            )
        record_path = self.artifact_root / name
        record_path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_type == "screenshot":
            try:
                self.page.screenshot(path=str(record_path))
            except Exception as exc:
                raise AdapterArtifactError("screenshot capture failed") from exc
        else:
            try:
                content = self.page.content()
            except Exception as exc:
                raise AdapterArtifactError("page source capture failed") from exc
            if not isinstance(content, str):
                raise AdapterArtifactError("page content is not a string")
            record_path.write_text(content, encoding="utf-8")
        if not record_path.is_file():
            raise AdapterArtifactError(
                "artifact was not written: %s" % record_path
            )
        return ArtifactHandle(artifact_type=artifact_type, path=record_path)


def create_live_session_factory(
    *,
    engine: str = "playwright",
    headless: bool = True,
    artifact_root: Optional[Path] = None,
) -> SessionFactory:
    """Return a zero-arg factory launching chromium via the requested engine."""
    normalized = validate_browser_engine(engine)

    def factory() -> PlaywrightSession:
        try:
            sync_playwright = _import_sync_playwright(normalized)
        except ImportError:
            # A missing SDK is an actionable operator error, not a
            # generic startup failure - keep the install hint.
            raise
        driver = None
        browser = None
        context = None
        try:
            driver = sync_playwright().start()
            browser = driver.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
        except Exception as exc:
            # Roll back whatever already started; the primary error wins.
            for resource in (context, browser, driver):
                if resource is None:
                    continue
                try:
                    _close_resource(resource)
                except Exception:
                    pass
            raise AdapterStartupError(
                "failed to launch %s browser" % normalized
            ) from exc
        return PlaywrightSession(
            page,
            artifact_root=artifact_root,
            teardown=(context, browser, driver),
        )

    return factory
