import pytest
from pydantic import ValidationError

from commerce_agent.config.settings import Settings


def test_settings_reject_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"environment": "demo"})


def test_settings_validate_api_port() -> None:
    with pytest.raises(ValidationError):
        Settings(api_port=0)
