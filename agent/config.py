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
    resume_matcher_url: str = "http://localhost:8000"


def load_yaml() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_yaml(data: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
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

    return SearchConfig(
        keywords=keywords,
        location=location,
        experience_level=experience_level,
        blacklist_companies=blacklist,
        max_jobs_per_run=int(max_jobs),
    )


def set_keywords(keywords: list[str]) -> None:
    db.set_config_value("keywords", json.dumps(keywords))


def set_location(location: str) -> None:
    db.set_config_value("location", json.dumps(location))


def set_max_jobs(n: int) -> None:
    db.set_config_value("max_jobs_per_run", json.dumps(n))


def get_schedule_config() -> dict:
    raw = load_yaml()
    return raw.get("schedule", {"hour": 8, "minute": 0})
