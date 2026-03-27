# LinkedIn Job Agent — Backlog

Work items for scheduled remote sessions.
Pick the top unclaimed item, implement with TDD (write tests first → RED → implement → GREEN), open a PR, merge.

---

## Priority Queue

(All P8-P11 completed on 2026-03-27! Overview of final work below.)
**Why:** Lines 28-45 (`build_application`) require full Telegram app setup — skip.
Lines 288-289, 297-298 are set_location/set_max empty-arg paths already tested elsewhere.
Lines 327-328 (`cmd_search_config` MarkdownV2 parse_mode check) and 353-355 (experience level warning validation path) could be added.
**What to do:**
- `tests/test_notifier_coverage.py`: add `test_cmd_search_config_uses_markdownv2` (check parse_mode="MarkdownV2")
- `tests/test_experience_level_validation.py`: already covers 353-355 — run `--cov-report=term-missing` to verify

---

### [P9] Close remaining improver.py coverage gaps (~94%)
**Why:** Lines 22, 27, 79-80 are error-handling paths in `tailor_resume` (when upload or preview returns None) and `get_master_resume_id` HTTP error.
**What to do:**
- `tests/test_improver.py`: Add tests for:
  - `tailor_resume` returns None when `_upload_job` fails (line 22 path)
  - `tailor_resume` returns None when `_improve_preview` fails (line 27 path)
  - `get_master_resume_id` returns None on empty masters list (line 79-80)
  Note: `test_upload_job_returns_none_on_http_error` already covers part of this.

---

### [P10] Resume Matcher health check command
**Why:** If RM is down, the pipeline fails silently. A `/health` command would let users quickly check if RM is reachable.
**What to do:**
- Add `cmd_health` to `notifier.py` — call `GET {RESUME_MATCHER_URL}/health` or `/api/v1/resumes/list`
- Reply: ✅ Resume Matcher 正常 / ⚠️ Resume Matcher 無法連線
- Register in `build_application`
- 3 tests: reachable, unreachable, timeout

---

### [P11] Auto-confirm mode (optional)
**Why:** User may want to auto-confirm all tailored resumes without manual Telegram confirmation.
**What to do:**
- Add `AUTO_CONFIRM` env var (bool, default False)
- In `run_pipeline`, if AUTO_CONFIRM and tailoring succeeds → call `confirm_resume` immediately
- Skip `notify_job` notification (or notify without confirm/skip buttons)
- 3 tests

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
| #13 | BACKLOG update | 2026-03-27 |
| #14 | P4 VALID_EXPERIENCE_LEVELS + validation warning (TDD) | 2026-03-27 |
| #15 | P6 weekly stats in /status (today + 7-day rolling, TDD) | 2026-03-27 |
| #16 | P7 scrape_jobs with mocked ApifyClient (scraper 74% → 100%) | 2026-03-27 |
| #17 | config.py 100% coverage (save_yaml + get_schedule_config) | 2026-03-27 |
| #18 | P8 notifier.py coverage (88% → 93%) — 4 edge case tests | 2026-03-27 |
| #19 | P9 improver.py coverage (94% → 100%) — 3 error-path tests | 2026-03-27 |
| #20 | P10 /health command (RM connectivity check) — 3 tests | 2026-03-27 |
| #21 | P11 AUTO_CONFIRM mode (auto-confirm resumes) — 3 tests | 2026-03-27 |

**Note:** P5 (Resume type selection) was removed on 2026-03-27.
**Reason:** The two files `master_computational.md` and `master_mechaniacl.md` are German university transcripts (Leistungsspiegel), not two separate resumes.
The user already has one combined main resume (`C:\Users\chengting\projects\resume\resume.md`) that reflects the dual degree.
The Resume Matcher agent architecture is correct — it takes one master resume and tailors it per job opening.
Focus is now on: (1) ensuring the right resume is uploaded to RM as master, (2) enriching it with more details, and (3) continuing with P8-P11 coverage/feature improvements.

**Current state (2026-03-27, after P8-P11):** 157 tests, 94% overall coverage, all green.

Coverage by module:
| Module | Coverage |
|--------|----------|
| config.py | 100% |
| db.py | 100% |
| deduper.py | 100% |
| models.py | 100% |
| scraper.py | 100% |
| improver.py | 100% |
| notifier.py | 93% |
| main.py | 75% |

## Remaining Opportunities (Optional Future Work)

- **notifier.py → 100%**: Lines 28-45 in `build_application()` (integration layer, typically excluded)
- **main.py → 90%+**: Add pipeline integration tests for edge cases (rare startup scenarios)
- **Resume content optimization**: Expand resume.md with more detailed work/project descriptions for better RM tailoring
