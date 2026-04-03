import json
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent import db
from agent.models import SearchConfig

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    apify_token: str = ""
    telegram_bot_token: str
    telegram_chat_id: str
    resume_matcher_url: str = "http://localhost:8001"
    auto_confirm: bool = False
    gemini_api_key: str = ""
    min_job_score: int = 5


def load_yaml() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def get_search_config() -> SearchConfig:
    """Load search config from YAML, then apply any DB overrides (set via Telegram)."""
    raw = load_yaml()["search"]
    overrides = db.get_search_overrides()

    keywords = overrides.get("keywords", raw["keywords"])
    location = overrides.get("location", raw["location"])
    experience_level = overrides.get("experience_level", raw["experience_level"])
    blacklist = overrides.get("blacklist_companies", raw.get("blacklist_companies", []))
    max_jobs = overrides.get("max_jobs_per_run", raw.get("max_jobs_per_run", 20))
    time_filter = overrides.get("time_filter", raw.get("time_filter", "r86400"))

    return SearchConfig(
        keywords=keywords,
        location=location,
        experience_level=experience_level,
        blacklist_companies=blacklist,
        max_jobs_per_run=int(max_jobs),
        time_filter=str(time_filter),
    )


def set_keywords(keywords: list[str]) -> None:
    db.set_config_value("keywords", json.dumps(keywords))


def set_location(location: str) -> None:
    db.set_config_value("location", json.dumps(location))


def set_max_jobs(n: int) -> None:
    db.set_config_value("max_jobs_per_run", json.dumps(n))


def set_experience_level(levels: list[str]) -> None:
    db.set_config_value("experience_level", json.dumps(levels))


def set_blacklist_companies(companies: list[str]) -> None:
    db.set_config_value("blacklist_companies", json.dumps(companies))


def set_time_filter(value: str) -> None:
    db.set_config_value("time_filter", json.dumps(value))


def get_schedule_config() -> dict:
    """Load schedule config from YAML. Supports both old (hour) and new (hours) format."""
    raw = load_yaml()
    schedule = raw.get("schedule", {})

    # Backward compatibility: if 'hour' exists, convert to 'hours' list
    if "hour" in schedule:
        hours = [schedule["hour"]]
    else:
        hours = schedule.get("hours", [8])  # Default to 8:00 if neither set

    minute = schedule.get("minute", 0)

    return {
        "hours": hours,  # List of hours to run the pipeline
        "minute": minute,
    }
