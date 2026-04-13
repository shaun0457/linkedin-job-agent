"""Shared pytest fixtures for linkedin-job-agent test suite."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from agent.models import SearchConfig

# Default SearchConfig returned when pipeline tests run without a live DB.
_DEFAULT_SEARCH_CONFIG = SearchConfig(
    keywords=["AI Engineer"],
    location="Germany",
    experience_level=["MID_SENIOR_LEVEL"],
    blacklist_companies=[],
    max_jobs_per_run=20,
    time_filter="r86400",
)


@pytest.fixture(autouse=True)
def _patch_main_get_search_config():
    """Patch main.get_search_config for all tests so pipeline tests never hit
    the uninitialised DB.  Tests that exercise agent.config directly are
    unaffected because they use their own import path."""
    with patch("main.get_search_config", return_value=_DEFAULT_SEARCH_CONFIG):
        yield
