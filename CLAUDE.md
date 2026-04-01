# CLAUDE.md

Semi-automated job search agent for a dual-degree engineer (Computational + Mechanical, TU Darmstadt).
Scrapes LinkedIn jobs → tailors resume via Resume Matcher → notifies user on Telegram for confirmation.

```
APScheduler (8:00 AM, 6:00 PM Taiwan time)
    ↓
scraper.py (Apify) → deduper.py → improver.py (RM API) → notifier.py (Telegram) → user confirms
                          ↑                                        ↑
                     db.py (SQLite)                      config.py (YAML + .env)
```

**Context:** PRD.md (What/Why) · BRAINSTORMING.md (design decisions) · BACKLOG.md (priorities)

## Tech Stack

Python 3.11+ / pytest + pytest-asyncio / APScheduler / python-telegram-bot v21 / SQLite / httpx / Apify

## Project Status

Phase 1 complete — 157 tests, 94% overall coverage. All core modules at 100%.

## Module Map

| File | Responsibility |
|------|---------------|
| `main.py` | Entry point: init DB, build Telegram app, schedule pipeline, start polling |
| `agent/models.py` | `Job`, `TailoredResult`, `SearchConfig` dataclasses; `VALID_EXPERIENCE_LEVELS` |
| `agent/db.py` | SQLite wrapper — `seen_jobs` + `search_config` tables, migrations |
| `agent/config.py` | `Settings` (Pydantic/env), YAML + DB config layering |
| `agent/scraper.py` | Apify `curious_coder/linkedin-jobs-scraper` client; mock mode |
| `agent/deduper.py` | `filter_new(jobs)` — checks job_id OR url against DB |
| `agent/improver.py` | Resume Matcher API: upload job → preview → confirm; retry logic |
| `agent/notifier.py` | Telegram bot: notifications, inline buttons, 15 slash commands |

## Rules

### TDD (Non-negotiable)

- Write tests FIRST: RED → GREEN → REFACTOR
- Min 80% coverage: `pytest --cov=agent --cov=main --cov-report=term-missing`
- Never commit with failing tests

### Code

- Type hints on all function signatures
- Immutable patterns only — never mutate, always return new objects
- Functions < 50 lines, files < 800 lines
- No print/console.log in production code
- No hardcoded secrets — `.env` only (gitignored)
- `httpx.AsyncClient` for HTTP (never `requests` in async code)
- Parameterized SQL queries only (no f-string SQL)
- UTC timestamps: `datetime.now(timezone.utc)`

### Telegram

- Always `parse_mode="MarkdownV2"` — escape: `_ * [ ] ( ) ~ \` > # + - = | { } . !`
- Use `_esc()` / `_esc_url()` helpers in `notifier.py` — never escape manually inline
- Inline keyboard buttons for user actions (Confirm / Skip / Retry)

### Git

- Branch from main: `feature/P<N>-<kebab-case>` or `hotfix/<issue>`
- Commit format: `P<N>: <description>` with Co-Authored-By trailer
- Squash merge back to main

## Commands

```bash
pytest tests/ -q                                          # run all tests
pytest --cov=agent --cov=main --cov-report=term-missing   # coverage report
python main.py                                            # start agent + scheduler
```

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `APIFY_TOKEN` | Yes | Set to `mock` to use hardcoded test jobs without hitting Apify |
| `TELEGRAM_BOT_TOKEN` | Yes | |
| `TELEGRAM_CHAT_ID` | Yes | |
| `RESUME_MATCHER_URL` | No | Default: `http://localhost:8000` |
| `AUTO_CONFIRM` | No | `true` to skip Telegram confirmation step |

## Coverage Targets

| Module | Target | Notes |
|--------|--------|-------|
| config, db, deduper, improver, models, scraper | 100% | Currently at 100% |
| notifier | 93%+ | `build_application()` integration layer excluded |
| main | 75%+ | Startup/shutdown paths hard to unit test |

## Telegram Commands (15 total)

`/run` · `/status` · `/list` · `/pending` · `/retry <job_id>`
`/config` · `/search_config` · `/set_keywords` · `/set_location` · `/set_max`
`/set_experience_level` · `/set_blacklist` · `/health` · `/help`

## Key Decisions

- One combined master resume in RM (dual degree = one identity, not two resumes)
- Local APScheduler at 8:00 + 18:00 Taiwan time — configurable via `config.yaml` `schedule.hours` list
- Semi-auto: user always confirms before apply (unless `AUTO_CONFIRM=true`)
- Config layering: `config.yaml` defaults → DB overrides (via Telegram commands)
- SQLite at `data/jobs.db` (auto-created by `init_db()`)
