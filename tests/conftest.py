"""Shared pytest fixtures for linkedin-job-agent tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent.models import SearchConfig


@pytest.fixture(autouse=True)
def mock_get_search_config():
    """Prevent any test from hitting the DB via get_search_config.

    run_pipeline() calls get_search_config() which calls db.get_search_overrides(),
    requiring an initialised DB.  This autouse fixture patches it globally so no
    test needs an on-disk database for the config layer.
    """
    default_cfg = SearchConfig(
        keywords=["AI Engineer"],
        location="Remote",
        experience_level=["MID_SENIOR_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=10,
    )
    with patch("main.get_search_config", return_value=default_cfg):
        yield
