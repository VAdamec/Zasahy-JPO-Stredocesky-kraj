"""Keep standalone parser tests usable without the HA test dependencies."""

import importlib.util

import pytest

HAS_HA_TESTS = (
    importlib.util.find_spec("pytest_homeassistant_custom_component") is not None
)
pytest_plugins = ["pytest_homeassistant_custom_component"] if HAS_HA_TESTS else []


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(request):
    if HAS_HA_TESTS:
        request.getfixturevalue("enable_custom_integrations")
    yield
