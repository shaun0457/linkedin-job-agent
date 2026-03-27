"""Tests for agent/config.py."""
import json
from unittest.mock import patch, call

import pytest

from agent.config import (
    get_search_config,
    set_keywords,
    set_location,
    set_max_jobs,
    set_experience_level,
    set_blacklist_companies,
)
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


# ── setter functions ──────────────────────────────────────────────────────────


def test_set_keywords_stores_json():
    with patch("agent.config.db.set_config_value") as mock_set:
        set_keywords(["AI Engineer", "ML Engineer"])
    mock_set.assert_called_once_with("keywords", json.dumps(["AI Engineer", "ML Engineer"]))


def test_set_location_stores_json():
    with patch("agent.config.db.set_config_value") as mock_set:
        set_location("Berlin, Germany")
    mock_set.assert_called_once_with("location", json.dumps("Berlin, Germany"))


def test_set_max_jobs_stores_json():
    with patch("agent.config.db.set_config_value") as mock_set:
        set_max_jobs(15)
    mock_set.assert_called_once_with("max_jobs_per_run", json.dumps(15))


def test_set_experience_level_stores_json():
    with patch("agent.config.db.set_config_value") as mock_set:
        set_experience_level(["MID_SENIOR_LEVEL", "ENTRY_LEVEL"])
    mock_set.assert_called_once_with(
        "experience_level", json.dumps(["MID_SENIOR_LEVEL", "ENTRY_LEVEL"])
    )


def test_set_blacklist_companies_stores_json():
    with patch("agent.config.db.set_config_value") as mock_set:
        set_blacklist_companies(["EvilCorp", "SpamInc"])
    mock_set.assert_called_once_with(
        "blacklist_companies", json.dumps(["EvilCorp", "SpamInc"])
    )


def test_set_blacklist_companies_empty_list():
    with patch("agent.config.db.set_config_value") as mock_set:
        set_blacklist_companies([])
    mock_set.assert_called_once_with("blacklist_companies", json.dumps([]))


# ── save_yaml ────────────────────────────────────────────────────────────────


def test_save_yaml_writes_to_config_path(tmp_path, monkeypatch):
    import yaml
    from agent import config as cfg_module

    tmp_yaml = tmp_path / "config.yaml"
    monkeypatch.setattr(cfg_module, "CONFIG_PATH", tmp_yaml)

    data = {"search": {"keywords": ["test"], "location": "UK"}}
    cfg_module.save_yaml(data)

    assert tmp_yaml.exists()
    loaded = yaml.safe_load(tmp_yaml.read_text())
    assert loaded["search"]["keywords"] == ["test"]


# ── get_schedule_config ──────────────────────────────────────────────────────


def test_get_schedule_config_returns_hours_and_minute():
    from agent.config import get_schedule_config

    # New format with 'hours' list
    with patch("agent.config.load_yaml", return_value={"schedule": {"hours": [9, 18], "minute": 30}}):
        sc = get_schedule_config()

    assert sc["hours"] == [9, 18]
    assert sc["minute"] == 30


def test_get_schedule_config_backward_compat_single_hour():
    from agent.config import get_schedule_config

    # Old format with single 'hour' → convert to 'hours' list
    with patch("agent.config.load_yaml", return_value={"schedule": {"hour": 9, "minute": 30}}):
        sc = get_schedule_config()

    assert sc["hours"] == [9]
    assert sc["minute"] == 30


def test_get_schedule_config_defaults_when_missing():
    from agent.config import get_schedule_config

    with patch("agent.config.load_yaml", return_value={}):
        sc = get_schedule_config()

    assert sc["hours"] == [8]  # Default to 8:00
    assert sc["minute"] == 0
