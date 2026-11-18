"""Shared pytest fixtures for s_layer_flint_charts test suite."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# Under CI, a skipped test fails the run (tests/ci_skips.py).
pytest_plugins = ["tests.ci_skips"]
