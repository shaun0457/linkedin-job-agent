"""Tests for agent/config.py."""
from unittest.mock import patch

import pytest

from agent.config import get_search_config
from agent.models import SearchConfig


def test_get_search_config_returns_search_config():
    with patch("agent.config.db.get_search_overrides", return_value={}):
        config = get_search_config()
    assert isinstance(config, SearchConfig)


def test_get_search_config_yaml_defaults():
    """Values from config.yaml are loaded when there are no DB overrides."""
    with patch("agent.config.db.get_search_overrides", return_value={}):
        config = get_search_config()

    assert config.location == "Germany"
    assert config.max_jobs_per_run == 20
    assert isinstance(config.keywords, list)
    assert len(config.keywords) > 0
    assert isinstance(config.experience_level, list)
    assert isinstance(config.blacklist_companies, list)


def test_get_search_config_location_override():
    with patch(
        "agent.config.db.get_search_overrides",
        return_value={"location": "United Kingdom"},
    ):
        config = get_search_config()
    assert config.location == "United Kingdom"


def test_get_search_config_keywords_override():
    with patch(
        "agent.config.db.get_search_overrides",
        return_value={"keywords": ["Data Scientist", "NLP Engineer"]},
    ):
        config = get_search_config()
    assert config.keywords == ["Data Scientist", "NLP Engineer"]


def test_get_search_config_max_jobs_override():
    with patch(
        "agent.config.db.get_search_overrides",
        return_value={"max_jobs_per_run": 5},
    ):
        config = get_search_config()
    assert config.max_jobs_per_run == 5


def test_get_search_config_partial_override_leaves_defaults():
    """An override of one field should not affect others."""
    with patch(
        "agent.config.db.get_search_overrides",
        return_value={"location": "London"},
    ):
        config = get_search_config()

    assert config.location == "London"
    # Non-overridden fields come from config.yaml
    assert config.max_jobs_per_run == 20


def test_get_search_config_full_override():
    overrides = {
        "location": "Netherlands",
        "keywords": ["LLM Engineer"],
        "experience_level": ["SENIOR_LEVEL"],
        "blacklist_companies": ["Spam Inc"],
        "max_jobs_per_run": 15,
    }
    with patch("agent.config.db.get_search_overrides", return_value=overrides):
        config = get_search_config()

    assert config.location == "Netherlands"
    assert config.keywords == ["LLM Engineer"]
    assert config.experience_level == ["SENIOR_LEVEL"]
    assert config.blacklist_companies == ["Spam Inc"]
    assert config.max_jobs_per_run == 15
