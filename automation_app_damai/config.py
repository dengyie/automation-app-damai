from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DamaiAppConfig:
    channel: str
    url: Optional[str] = None
    app_id: Optional[str] = None

    def validate(self) -> None:
        if self.channel == "web" and not self.url:
            raise ValueError("web channel requires url")
        if self.channel == "android" and not self.app_id:
            raise ValueError("android channel requires app_id")
