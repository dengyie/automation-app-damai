import pytest

from automation_app_damai.config import DamaiAppConfig


def test_damai_app_config_requires_channel_specific_target():
    config = DamaiAppConfig(channel="web", url="https://example.test/damai")

    assert config.channel == "web"
    assert config.url == "https://example.test/damai"


def test_damai_app_config_rejects_missing_web_url():
    config = DamaiAppConfig(channel="web")

    with pytest.raises(ValueError, match="web channel requires url"):
        config.validate()


def test_damai_app_config_rejects_missing_android_app_id():
    config = DamaiAppConfig(channel="android")

    with pytest.raises(ValueError, match="android channel requires app_id"):
        config.validate()
