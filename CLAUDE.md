# CLAUDE.md

Semi-automated job search agent: Apify scrape → Resume Matcher tailor → Telegram notify.
See PRD.md for requirements (What/Why). See BRAINSTORMING.md for design decisions.

## Tech Stack

Python 3.12 / pytest + pytest-asyncio / APScheduler / python-telegram-bot v21 / SQLite / httpx / Apify

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

## Coverage Targets

| Module | Target | Notes |
|--------|--------|-------|
| config, db, deduper, improver, models, scraper | 100% | Currently at 100% |
| notifier | 93%+ | `build_application()` lines excluded |
| main | 76%+ | Startup/shutdown paths hard to unit test |

## Key Decisions

- One combined master resume in RM (dual degree = one identity, not two resumes)
- Local APScheduler at 8:00 + 18:00 Taiwan time (RM on localhost)
- Semi-auto: user always confirms before apply (unless AUTO_CONFIRM=true)
- Config layering: config.yaml defaults → DB overrides (via Telegram commands)
