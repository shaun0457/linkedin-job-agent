# CLAUDE.md — LinkedIn Job Agent Development Guide

This file contains rules, patterns, and guidelines for developing on the LinkedIn Job Agent project. Follow these instructions to maintain consistency, quality, and alignment with the project vision.

---

## 1. Project Context

**Project**: LinkedIn Job Agent — Semi-automated job search assistant for Cheng Ting
**Current State**: Phase 1 complete (157 tests, 94% coverage), Phase 2 in planning
**Tech Stack**: Python 3.12, pytest, APScheduler, Telegram bot, SQLite, Resume Matcher API, Apify

**Vision**: Reduce job search time by 80% through automated scraping + resume tailoring, while maintaining user control over final decisions.

---

## 2. Core Values

### 2.1 TDD is Mandatory
- **Write tests first**: RED → GREEN → REFACTOR
- **Minimum 80% coverage**: Run `pytest --cov=agent --cov=main --cov-report=term-missing`
- **Test discipline**: Don't commit code without tests passing
- **Current modules at 100%**: config, db, deduper, improver, models, scraper

### 2.2 User Control Always
- User must confirm before any job is applied
- Errors never silently fail (always notify via Telegram `/health` or `/status`)
- Reversibility: Tailored resumes can always be reviewed before confirmation

### 2.3 Data Integrity
- Deduplicate aggressively (no duplicate applications ever)
- Journal all decisions in SQLite (for audit + retry)
- Immutability: Never mutate objects (copy-on-write)

### 2.4 Code Quality over Speed
- Small functions (< 50 lines)
- Small files (200-400 lines typical, 800 max)
- Explicit > implicit (no magic)
- No console.log in production code

---

## 3. Development Workflow

### 3.1 Feature Implementation (TDD)

```bash
# 1. Create a feature branch
git checkout -b feature/P<N>-<name>

# 2. Write tests first (RED)
pytest tests/test_<feature>.py -v

# 3. Implement feature (GREEN)
# Edit agent/<module>.py or main.py

# 4. Run all tests
pytest tests/ -q

# 5. Check coverage
pytest --cov=agent --cov=main --cov-report=term-missing

# 6. Commit (squash on main)
git add <files>
git commit -m "P<N>: <description>

- What changed
- Why it changed
- Test results (X tests, YY% coverage)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

git push -u origin feature/P<N>-<name>
```

### 3.2 Code Review Checklist

Before any PR/commit:
- [ ] All tests pass (`pytest`)
- [ ] Coverage ≥ 80% (`--cov-report=term-missing`)
- [ ] No console.log statements
- [ ] No hardcoded secrets (use `.env`)
- [ ] No mutation (immutable patterns)
- [ ] Function size < 50 lines
- [ ] File size < 800 lines
- [ ] Docstrings for public functions
- [ ] Type hints on function signatures
- [ ] MarkdownV2 escaping in Telegram messages

### 3.3 Branching Strategy

```
main (stable, production-ready)
  ├─ feature/P5-resume-selection (WIP)
  ├─ feature/P8-notifier-coverage ✅ (merged)
  └─ hotfix/utf8-encoding ✅ (merged)
```

Rules:
- Always branch from `main`
- Always merge back to `main` via squash commit
- Feature names: `feature/P<N>-<kebab-case>`
- Hotfix names: `hotfix/<issue>`

---

## 4. Code Standards

### 4.1 Python Style

```python
# ✅ GOOD: Immutable, type-hinted, explicit
def process_jobs(jobs: list[Job], config: SearchConfig) -> list[Job]:
    """Filter and deduplicate jobs."""
    filtered = [j for j in jobs if j.company not in config.blacklist_companies]
    return filter_new(filtered)

# ❌ BAD: Mutation, no type hints, implicit
def process_jobs(jobs, config):
    for j in jobs:
        if j.company in config.blacklist:
            jobs.remove(j)  # MUTATION!
    return jobs
```

**Rules**:
- Use type hints: `def foo(x: int) -> str:`
- Use f-strings: `f"Hello {name}"`
- Use dict unpacking: `{**dict1, **dict2}`
- Avoid mutable defaults: `def foo(x: list = None):`
- Immutable collections: `tuple`, `frozenset`, `dataclass`

### 4.2 Async Code

```python
# ✅ GOOD: Proper async/await
async def run_pipeline(app: Application, settings: Settings) -> None:
    master_id = await improver.get_master_resume_id(...)
    if not master_id:
        await notifier.notify_error(...)
        return

# ❌ BAD: Blocking in async
async def run_pipeline(...):
    result = requests.get(url)  # BLOCKING! Use httpx.AsyncClient instead
```

**Rules**:
- Use `asyncio` / `async def` / `await`
- Use `httpx.AsyncClient` for HTTP (not `requests`)
- Use `@pytest.mark.asyncio` for tests
- Never mix `await` with `.result()` calls

### 4.3 Database

```python
# ✅ GOOD: Parameterized, journaled
db.insert_job(
    job_id=job.job_id,
    title=job.title,
    company=job.company,
    url=job.url,
    preview_data=result.preview_data,  # Full JSON
    rm_job_id=result.rm_job_id,
    master_resume_id=result.master_resume_id,
    notified_at=datetime.now(timezone.utc),
)

# ❌ BAD: SQL injection
con.execute(f"INSERT INTO jobs VALUES ('{job_id}', '{title}')")
```

**Rules**:
- Always use parameterized queries
- Store full response objects as JSON (not truncated)
- Use UTC timestamps: `datetime.now(timezone.utc)`
- Immutable schema: Don't modify existing columns

### 4.4 Telegram Messages

```python
# ✅ GOOD: MarkdownV2 escaping
message = (
    f"Job Found\n"
    f"Title: `{escape_markdown_v2(job.title)}`\n"
    f"Company: `{escape_markdown_v2(job.company)}`\n"
)
await update.message.reply_text(message, parse_mode="MarkdownV2")

# ❌ BAD: Unescaped special chars
message = f"Job: {job.title}"  # If title has '_', it breaks MarkdownV2!
```

**Rules**:
- Always use `parse_mode="MarkdownV2"`
- Escape special chars: `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` `, `\`, `!`, `#`, `+`, `-`, `.`, `>`
- Use inline buttons for user actions (Confirm, Skip, Retry)
- Keep messages < 4096 characters (Telegram limit)

### 4.5 Configuration

```python
# ✅ GOOD: YAML + DB override, environment variables
class Settings(BaseSettings):
    telegram_bot_token: str
    auto_confirm: bool = False  # Default

config = get_search_config()  # YAML + DB merged
schedule = get_schedule_config()  # [8, 18] hours

# ❌ BAD: Hardcoded, hardcoded secrets
TOKEN = "123456789"  # NEVER!
config = {"keywords": ["hardcoded"]}
```

**Rules**:
- Store in `config.yaml` (YAML format)
- Override via database (Telegram commands)
- Secrets in `.env` (gitignored)
- No hardcoded values anywhere

---

## 5. Testing Standards

### 5.1 Test Structure

```python
# ✅ GOOD: Descriptive names, clear assertions
def test_tailor_resume_returns_none_when_upload_job_fails():
    """Test that tailor_resume handles upload failures gracefully."""
    with patch("agent.improver._upload_job", return_value=None):
        result = improver.tailor_resume(...)
    assert result is None

# ❌ BAD: Unclear what's being tested
def test_tailor():
    assert improver.tailor_resume(...) is not None
```

**Rules**:
- Test name: `test_<function>_<scenario>_<expected>`
- One assertion per test (or related assertions)
- Use fixtures for repeated setup
- Mock external services (Apify, Resume Matcher API)

### 5.2 Coverage Targets

| Module | Current | Target |
|--------|---------|--------|
| config.py | 100% | 100% |
| db.py | 100% | 100% |
| deduper.py | 100% | 100% |
| improver.py | 100% | 100% |
| models.py | 100% | 100% |
| scraper.py | 100% | 100% |
| notifier.py | 93% | 100% (lines 28-45 are integration layer, can skip) |
| main.py | 76% | 90% (add edge case tests for startup) |

**Excluded from coverage**:
- `build_application()` (lines 28-45 in notifier.py) — Telegram framework setup
- `if __name__ == "__main__"` blocks — Entry point

### 5.3 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=agent --cov=main --cov-report=term-missing -q

# Run specific test
pytest tests/test_config.py::test_get_search_config_full_override -v

# Run tests matching pattern
pytest tests/ -k "search_config" -v

# Run tests with asyncio debugging
pytest tests/ --asyncio-mode=strict -v
```

---

## 6. Priority Queue (BACKLOG)

**Current Phase**: Phase 1 ✅ (Complete) → Phase 2 (In Planning)

### Phase 1 Completed ✅
- ✅ LinkedIn scraping (Apify)
- ✅ Resume Matcher integration
- ✅ Telegram commands (14 commands)
- ✅ SQLite deduplication
- ✅ APScheduler (8 AM + 6 PM)
- ✅ TDD test suite (157 tests, 94% coverage)
- ✅ Multi-time schedule support

### Phase 2 (Next)
- [ ] **P1**: Big company job sources (TSMC, Google, Meta careers pages)
- [ ] **P2**: Resume content expansion (more details for better RM tailoring)
- [ ] **P3**: Docker deployment + setup guide
- [ ] **P4**: Multi-source deduplication (LinkedIn + company sites)

### Phase 3 (Future)
- [ ] Resume Matcher cloud deployment (true full automation)
- [ ] Job recommendation engine (feedback loop)
- [ ] Interview tracking (follow-ups, offers)
- [ ] Analytics dashboard

**How to claim a task**: Create a feature branch, implement with TDD, open PR, merge via squash.

---

## 7. Known Limitations & Decisions

### 7.1 Why Local APScheduler, Not Remote Agent?
- **Decision**: Keep APScheduler local (user's machine)
- **Reason**: Resume Matcher runs on localhost:8000; remote agent can't reach it
- **Future**: When RM is deployed to cloud, migrate to Claude's remote schedule feature

### 7.2 Why No Automatic Application Filing?
- **Decision**: User must confirm via Telegram before auto-apply
- **Reason**: Applications are irreversible; user must maintain final control
- **Alternative**: `AUTO_CONFIRM=true` allows opt-in auto-confirmation

### 7.3 Why Two Resume Files Initially?
- **Decision**: Removed P5 (resume type selection)
- **Reason**: User has dual degree (Computational + Mechanical); should have ONE combined resume
- **Outcome**: Single master resume in RM, tailored per job automatically

### 7.4 Why SQLite, Not PostgreSQL?
- **Decision**: SQLite for simplicity
- **Reason**: Single-user, local, no server overhead
- **Trade-off**: Can't scale to multiple concurrent users
- **Future**: If needed for team usage, migrate to PostgreSQL

---

## 8. Common Tasks

### Add a New Telegram Command

```python
# 1. Create handler in agent/notifier.py
async def cmd_myfeature(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Short description."""
    await update.message.reply_text("Response", parse_mode="MarkdownV2")

# 2. Register in build_application()
app.add_handler(CommandHandler("myfeature", cmd_myfeature))

# 3. Add help text to cmd_help()
help_text += "\n/myfeature — what it does"

# 4. Write tests in tests/test_notifier_*.py
@pytest.mark.asyncio
async def test_cmd_myfeature_returns_response():
    ...
```

### Add a New Configuration Parameter

```python
# 1. Update config.yaml
my_param: "default_value"

# 2. Update agent/config.py
def get_my_config() -> dict:
    raw = load_yaml()
    return raw.get("my_section", {...})

# 3. Add to Settings class if env var
class Settings(BaseSettings):
    my_param: str = "default"

# 4. Write tests
def test_my_config_loads():
    ...
```

### Add a New Feature

```bash
# 1. Write tests (RED)
git checkout -b feature/P<N>-<feature>
# Create tests/test_<feature>.py
pytest tests/test_<feature>.py -v  # Should fail

# 2. Implement (GREEN)
# Edit agent/<module>.py
pytest tests/ -v  # All should pass

# 3. Check coverage
pytest --cov=agent --cov=main --cov-report=term-missing

# 4. Commit & merge
git add .
git commit -m "P<N>: ..."
git push origin feature/P<N>-<feature>
# Merge to main via squash
```

---

## 9. Troubleshooting

### Test Failures

```bash
# If asyncio test fails
# → Check @pytest.mark.asyncio decorator
# → Check pytest.ini has: asyncio_mode = strict

# If mock fails
# → Verify patch path: "agent.module.function" not "module.function"
# → Check mock.assert_called_once_with() for exact params

# If coverage drops
# → Run --cov-report=term-missing to see lines
# → Check if new code is unreachable (dead code?)
```

### Runtime Issues

```bash
# Resume Matcher timeout
# → Check if RM is running on localhost:8000
# → Use /health command to verify
# → Increase timeout in agent/improver.py if needed

# SQLite locked
# → Multiple processes writing simultaneously
# → Ensure only one main.py instance running

# Telegram message encoding
# → Check special characters are MarkdownV2 escaped
# → Use escape_markdown_v2() helper function
```

---

## 10. Resources

### Code Reading
- **PRD.md**: Product requirements & user stories
- **BRAINSTORMING.md**: Design decisions & trade-offs
- **tests/**: Examples of expected behavior

### External References
- **Apify Docs**: https://docs.apify.com/sdk/python
- **Telegram Bot Docs**: https://python-telegram-bot.readthedocs.io
- **Resume Matcher**: https://github.com/shaun0457/Resume-Matcher
- **Python Async**: https://docs.python.org/3/library/asyncio.html

### Communication
- **Questions about requirements**: Check PRD.md & BRAINSTORMING.md first
- **Questions about code**: Check existing tests & docstrings
- **Bugs/issues**: Log in BACKLOG.md or GitHub issues (if applicable)

---

## 11. Commit Message Format

```
P<N>: <Short description (< 70 chars)>

- What changed
- Why it changed
- How to test it (if not obvious)
- Coverage/test count

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

**Example**:
```
P8: Close notifier.py coverage gaps (88% → 93%)

- Add 4 edge case tests for cmd_set_* functions
- Test comma-only input, no args, -clear option
- Improves reliability for malformed user input
- Tests: 151 → 158 total, notifier.py: 88% → 93%

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 12. Emergency Procedures

### If Resume Matcher is Down
```bash
# 1. Check health
# Telegram: /health

# 2. If down, manually restart
# Your terminal:
cd /path/to/Resume-Matcher
python -m uvicorn app:app --port 8000

# 3. Re-run pipeline
# Telegram: /run
```

### If SQLite is Corrupted
```bash
# 1. Backup current DB
cp linkedin-job-agent/agent/db.sqlite linkedin-job-agent/agent/db.sqlite.bak

# 2. Delete and reinit
rm linkedin-job-agent/agent/db.sqlite

# 3. Restart agent
python main.py
```

### If Tests Fail After Merge
```bash
# 1. Check what changed
git log --oneline -5

# 2. Run tests with verbose output
pytest tests/ -vv 2>&1 | tail -50

# 3. Fix issues (don't blame the tests!)
# Edit agent/ or main.py

# 4. Commit fix
git commit -m "Fix: <reason for failure>"
```

---

## Final Notes

**Last Updated**: 2026-03-27
**Status**: Active development, Phase 2 planning
**Owner**: Cheng Ting Chen + Claude (AI Developer)

**Remember**: Code quality > speed. Tests first, always. User control, always. Questions? Check the docs first, then BRAINSTORMING.md, then PRD.md.

🚀 **Keep shipping!**
