"""Shared pytest fixtures for s_layer_flint_charts test suite."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
