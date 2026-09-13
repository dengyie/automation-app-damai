from dataclasses import dataclass
from typing import Optional

SUPPORTED_BROWSER_ENGINES = ("playwright", "patchright")


def validate_browser_engine(value: str) -> str:
    """Normalize and validate the live web browser engine selection."""
    if (
        not isinstance(value, str)
        or value.strip().lower() not in SUPPORTED_BROWSER_ENGINES
    ):
        supported = ", ".join(SUPPORTED_BROWSER_ENGINES)
        raise ValueError(f"browser_engine must be one of: {supported}")
    return value.strip().lower()


@dataclass(frozen=True)
class DamaiAppConfig:
    channel: str
    url: Optional[str] = None
    app_id: Optional[str] = None
    browser_engine: str = "playwright"

    def validate(self) -> None:
        if self.channel == "web" and not self.url:
            raise ValueError("web channel requires url")
        if self.channel == "android" and not self.app_id:
            raise ValueError("android channel requires app_id")
        validate_browser_engine(self.browser_engine)
