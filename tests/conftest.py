import pytest

from docpilot.config import Settings
from docpilot.service import DocPilot


@pytest.fixture(scope="session")
def settings():
    s = Settings()
    s.trace_path = ""
    return s


@pytest.fixture(scope="session")
def dp(settings):
    return DocPilot(settings)
