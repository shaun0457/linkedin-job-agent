# LinkedIn Job Agent — Backlog

Work items for scheduled remote sessions.
Pick the top unclaimed item, implement with TDD (write tests first → RED → implement → GREEN), open a PR, merge.

---

## Priority Queue

### [P4] `/set_experience_level` and `/set_blacklist` accept level validation
**Why:** Any string is accepted as an experience level. LinkedIn only accepts:
`INTERNSHIP`, `ENTRY_LEVEL`, `ASSOCIATE`, `MID_SENIOR_LEVEL`, `DIRECTOR`, `EXECUTIVE`.
**What to do:**
- Add `VALID_EXPERIENCE_LEVELS` constant to `models.py`
- In `cmd_set_experience_level`: warn if unknown level passed (but still save it)
- Write 2 tests: valid levels → no warning, unknown level → warning in reply

---

### [P5] Resume type selection (computational vs mechanical)
**Why:** User has two master resumes (`master_computational.md` and `master_mechanical.md`).
The pipeline currently picks the first master resume found. It should pick the right one.
**What to do:**
- Add `RESUME_TYPE` env var (values: `computational` | `mechanical` | `auto`)
- Add to `Settings` in `config.py`
- In `run_pipeline`, pass `RESUME_TYPE` to `get_master_resume_id` filter
- `get_master_resume_id` already fetches list — filter by `name` containing the type
- Write tests for type selection logic

---

### [P6] Weekly stats in `/status`
**Why:** Daily stats reset at midnight. Users want to see the week's activity.
**What to do:**
- Add weekly summary line to `cmd_status`:
  ```
  📊 今日統計 / 本週統計
  • 今日職缺：N  / 本週職缺：M
  ```
- Call `db.get_stats(since=7_days_ago)` for weekly counts
- 2 additional tests in `test_notifier_coverage.py`

---

### [P7] Apify live scraper mock test
**Why:** `scrape_jobs()` itself (lines 15-45) can be tested by mocking `ApifyClient`.
**What to do:**
- In `tests/test_scraper.py`, add:
  - Mock `ApifyClient` so `client.actor(...).call()` returns a fake run
  - Mock `client.dataset(...).iterate_items()` to return fake items
  - Test: `scrape_jobs` returns parsed jobs
  - Test: `scrape_jobs` applies blacklist (skips matching company)
  - Test: `scrape_jobs` skips items with missing required fields

---

### [P8] Error recovery: notify_error uses MarkdownV2-safe text
**Why:** `notify_error` sends plain text. If the error message contains `(`, `)`,
or `.` it could break Telegram rendering if we ever switch to MarkdownV2 there.
Currently low risk (plain text mode). Defer unless needed.

---

## Completed

| PR | Description | Date |
|----|-------------|------|
| #1 | MarkdownV2 fix, /help, requirements.txt, mock scraper, pytest suite | 2026-03-27 |
| #3 | API alignment (improver/db/models), run summary, /search_config (TDD) | 2026-03-27 |
| #5 | /set_experience_level, /set_blacklist, /pending + scraper tests (TDD) | 2026-03-27 |
| #6 | Pipeline integration tests (6 paths), /pending formatting fix | 2026-03-27 |
| #7 | Config setter coverage (set_experience_level, set_blacklist) | 2026-03-27 |
| #8 | Notifier coverage — notify_job, callbacks, commands (34% → 69%) | 2026-03-27 |
| #9 | cmd_retry + handle_callback coverage (69% → 84%) | 2026-03-27 |
| #10 | BACKLOG.md created | 2026-03-27 |
| #11 | P1 cmd_run/cmd_help tests + P2 get_pending_jobs integration (84% → 88%) | 2026-03-27 |
| #12 | P3 extract _apply_blacklist + 5 blacklist tests (scraper 54% → 74%) | 2026-03-27 |

**Current state (2026-03-27):** 128 tests, 88% coverage, all green.
