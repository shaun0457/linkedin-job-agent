# LinkedIn Job Agent — Product Requirements Document (PRD)

**Version**: 1.0
**Last Updated**: 2026-03-27
**Status**: Active Development (Phase 1 ✅ Complete, Phase 2 in Planning)

---

## 1. Executive Summary

**LinkedIn Job Agent** is a semi-automated job search assistant that reduces the time spent on job hunting by automating job discovery, resume tailoring, and candidate tracking. The user (Cheng Ting) maintains full control over final job applications via Telegram commands.

**Problem**: Manually searching LinkedIn (8+ hours/week) + manually tailoring resumes per job + missing opportunities across multiple job boards.

**Solution**: Automated 2x daily (8:00 AM, 6:00 PM Taiwan time) job scraping, Resume Matcher tailoring, and Telegram notifications with 1-click confirmation flow.

---

## 2. User Personas & Stories

### User Profile: Cheng Ting
- **Background**: Dual M.Sc. (Computational Engineering + Mechanical Engineering, TU Darmstadt)
- **Job Target**: AI/ML Engineer, Predictive Maintenance roles
- **Location**: Germany / Taiwan
- **Constraint**: Resume Matcher runs locally; must review jobs before applying
- **Goal**: Find best-fit jobs across LinkedIn + major companies (TSMC, Google, Meta) without daily manual search

### User Stories

#### US-1: Auto-discover relevant jobs
```
As Cheng Ting,
I want the system to scrape LinkedIn daily (8:00 AM & 6:00 PM),
So that I don't have to manually browse LinkedIn.
```
**Acceptance Criteria:**
- ✅ Scrape at exactly 8:00 AM and 6:00 PM (Taiwan time)
- ✅ Return jobs matching: keywords, location, experience level
- ✅ Filter out blacklisted companies
- ✅ Deduplicate against previously seen jobs

#### US-2: Auto-tailor resumes
```
As Cheng Ting,
I want the system to automatically tailor my resume per job (using Resume Matcher),
So that I don't manually edit the resume 10+ times per day.
```
**Acceptance Criteria:**
- ✅ Upload job description to Resume Matcher
- ✅ Generate optimized resume with relevant keywords
- ✅ Support dual master's degree positioning (Computational + Mechanical)
- ✅ Cache improved resumes for review before confirmation

#### US-3: Review & confirm in Telegram
```
As Cheng Ting,
I want to see tailored job postings in Telegram and confirm with one click,
So that I can apply within seconds.
```
**Acceptance Criteria:**
- ✅ Receive Telegram notification: job title, company, tailor summary
- ✅ Inline buttons: "Confirm Apply" / "Skip This Job"
- ✅ If confirmed, save tailored resume and provide confirmation message
- ✅ If skipped, log reason (optional) and move to next job

#### US-4: Track application status
```
As Cheng Ting,
I want to see which jobs I've applied to, their status, and stats,
So that I can track my job search progress.
```
**Acceptance Criteria:**
- ✅ `/pending` command: list jobs awaiting confirmation
- ✅ `/status` command: show today's count + weekly rolling stats
- ✅ `/list` command: show all applied jobs with timestamps
- ✅ Database stores: job_id, title, company, URL, tailored resume, confirmation status

#### US-5: Health check Resume Matcher connectivity
```
As Cheng Ting,
I want a `/health` command to check if Resume Matcher is running,
So that I know if something is broken before the daily run.
```
**Acceptance Criteria:**
- ✅ `/health` returns ✅ Normal / ⚠️ Unreachable / ⏱️ Timeout
- ✅ Checks Resume Matcher API endpoint (GET /api/v1/resumes/list)

#### US-6: Optional auto-confirmation for trusted jobs
```
As Cheng Ting,
I want to optionally enable AUTO_CONFIRM mode,
So that highly matching jobs can auto-apply without manual confirmation.
```
**Acceptance Criteria:**
- ✅ AUTO_CONFIRM=true environment variable (default: false)
- ✅ If enabled + match score > threshold: auto-confirm without notification
- ✅ If disabled: traditional flow (notify + wait for user)

---

## 3. Functional Requirements

### 3.1 Core Workflows

#### Workflow A: Daily Scheduled Pipeline
```
Schedule (8:00 AM / 6:00 PM)
    ↓
Scrape LinkedIn + filter by config
    ↓
Deduplicate (check SQLite seen_jobs)
    ↓
For each new job:
  ├─ Upload job description → Resume Matcher
  ├─ Get tailored resume (keywords, suggestions)
  ├─ Insert into DB with status='notified'
  ├─ If AUTO_CONFIRM=false:
  │   └─ Send Telegram: job + tailor summary + buttons
  │       (user: confirm → status='confirmed', skip → status='skipped')
  │
  └─ If AUTO_CONFIRM=true:
      └─ Auto-confirm → status='confirmed'
             (optional: send silent notification)
    ↓
Send summary: "Found X jobs, tailored Y, user confirmed Z"
```

#### Workflow B: User Manual Commands
```
User types in Telegram
    ↓
Match command (/run, /status, /pending, /retry, /config, /help, /health, etc.)
    ↓
Execute handler
    ↓
Return MarkdownV2-formatted response
```

### 3.2 Feature List

| Feature | Status | Priority |
|---------|--------|----------|
| LinkedIn scraping (Apify) | ✅ Phase 1 | P1 |
| Resume Matcher tailoring | ✅ Phase 1 | P1 |
| Telegram notifications | ✅ Phase 1 | P1 |
| SQLite deduplication | ✅ Phase 1 | P1 |
| APScheduler daily runs (8 AM / 6 PM) | ✅ Phase 1 | P1 |
| `/run` — trigger pipeline manually | ✅ Phase 1 | P2 |
| `/status` — today + 7-day rolling stats | ✅ Phase 1 | P2 |
| `/pending` — list jobs awaiting confirmation | ✅ Phase 1 | P2 |
| `/list` — all applied jobs | ✅ Phase 1 | P2 |
| `/retry <job_id>` — re-confirm skipped job | ✅ Phase 1 | P3 |
| `/config` — show current search config | ✅ Phase 1 | P2 |
| `/search_config` — show detailed config (MarkdownV2) | ✅ Phase 1 | P2 |
| `/set_keywords`, `/set_location`, `/set_max_jobs` | ✅ Phase 1 | P3 |
| `/set_experience_level`, `/set_blacklist` | ✅ Phase 1 | P3 |
| `/health` — check RM connectivity | ✅ Phase 1 | P2 |
| `AUTO_CONFIRM` — auto-apply high-match jobs | ✅ Phase 1 | P3 |
| Dual master resume support | ✅ Phase 1 | P0 |
| Big company scraping (TSMC, Google, etc.) | ⏳ Phase 2 | P1 |
| Resume content optimization | 📌 Phase 2 | P2 |
| Deployment guide + Docker | ⏳ Phase 2 | P2 |
| Job match scoring UI | ⏳ Phase 3 | P3 |
| Interview tracking (follow-ups, offers) | ⏳ Phase 3 | P4 |

### 3.3 Configuration (config.yaml)

```yaml
search:
  keywords:
    - "AI/ML Engineer"
    - "Machine Learning Engineer"
  location: "Germany"
  experience_level: ["MID_SENIOR_LEVEL", "ENTRY_LEVEL"]
  blacklist_companies: []
  max_jobs_per_run: 20

schedule:
  hours: [8, 18]   # Taiwan time
  minute: 0

resume_matcher:
  base_url: "http://localhost:8001"
```

### 3.4 Environment Variables

```bash
APIFY_TOKEN=...              # LinkedIn scraper token (or "mock" for testing)
TELEGRAM_BOT_TOKEN=...       # Telegram bot API token
TELEGRAM_CHAT_ID=...         # User's Telegram chat ID
RESUME_MATCHER_URL=...       # Resume Matcher base URL (default: http://localhost:8001)
AUTO_CONFIRM=false           # (default: false, set to "true" for auto-apply)
```

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **Scraping**: < 30 seconds per LinkedIn query (Apify)
- **Tailoring**: < 5 minutes per job (Resume Matcher)
- **Notification**: < 2 seconds (Telegram)
- **Daily pipeline**: < 15 minutes total (10 jobs)

### 4.2 Reliability
- **Uptime**: Best effort (depends on user's machine + RM availability)
- **Retries**: Failed jobs logged; can retry via `/retry` command
- **Deduplication**: 100% accuracy (no duplicate applications)
- **Data persistence**: SQLite, backed up locally

### 4.3 Scalability
- **Job limit per run**: Configurable (default 20)
- **Time period**: Can extend to 3x daily or less
- **Resume count**: Supports 1+ master resumes
- **Telegram rate limit**: Built-in backoff

### 4.4 Code Quality
- **Test coverage**: ≥ 80% (currently 94%)
- **Testing methodology**: TDD (tests first, then code)
- **Code style**: PEP 8, type hints, immutability
- **Documentation**: Docstrings, inline comments for non-obvious logic

---

## 5. Data Model

### Table: `seen_jobs`
```sql
CREATE TABLE seen_jobs (
  job_id TEXT PRIMARY KEY,
  title TEXT,
  company TEXT,
  url TEXT,
  description TEXT,
  preview_data JSON,      -- RM improved resume data
  rm_job_id TEXT,         -- Resume Matcher job ID
  master_resume_id TEXT,  -- RM master resume used
  status TEXT,            -- 'notified' | 'confirmed' | 'skipped'
  notified_at TIMESTAMP,
  confirmed_at TIMESTAMP
);

CREATE TABLE search_config (
  key TEXT PRIMARY KEY,
  value TEXT              -- JSON-encoded
);
```

---

## 6. Telegram Commands

### Admin Commands
| Command | Example | Purpose |
|---------|---------|---------|
| `/run` | `/run` | Trigger pipeline immediately |
| `/status` | `/status` | Show today + weekly stats |
| `/pending` | `/pending` | List jobs awaiting confirmation |
| `/list` | `/list` | Show last 20 applied jobs |
| `/retry <id>` | `/retry job-123` | Re-confirm a skipped job |
| `/health` | `/health` | Check RM connectivity |

### Configuration Commands
| Command | Example | Purpose |
|---------|---------|---------|
| `/config` | `/config` | Show current config (brief) |
| `/search_config` | `/search_config` | Show detailed config (MarkdownV2) |
| `/set_keywords` | `/set_keywords AI Engineer, ML Engineer` | Update keywords |
| `/set_location` | `/set_location Berlin, Germany` | Update location |
| `/set_max` | `/set_max 15` | Update max jobs per run |
| `/set_experience_level` | `/set_experience_level MID_SENIOR_LEVEL, ENTRY_LEVEL` | Update experience filter |
| `/set_blacklist` | `/set_blacklist EvilCorp, BadInc` | Update company blacklist |
| `/set_blacklist -clear` | `/set_blacklist -clear` | Clear blacklist |
| `/help` | `/help` | Show all commands |

### Response Format
- **Text**: UTF-8 Chinese/English
- **Formatting**: MarkdownV2 (escape special chars)
- **Buttons**: Inline keyboards (Confirm, Skip, Retry)
- **Images**: None (text-only for now)

---

## 7. Success Metrics

### Quantitative
- **Jobs discovered/week**: Currently 20-40 (LinkedIn only), target 50+ (with big company sources)
- **Time saved/week**: ~6 hours (manual LinkedIn browsing + resume editing)
- **Application quality**: 100% deduplicated, tailored resumes
- **Match rate**: Should exceed 70% (RM-optimized)

### Qualitative
- **User satisfaction**: "System is more helpful than burden"
- **Reliability**: "I never miss a good job opportunity"
- **Ease of use**: "Telegram commands are intuitive"

---

## 8. Out of Scope (Phase 2+)

- [ ] Interview scheduling integration (Calendly, Google Calendar)
- [ ] Salary negotiation assistance
- [ ] Company review scraping (Glassdoor, Blind)
- [ ] Automatic application form filling
- [ ] Email notification (Telegram only)
- [ ] Browser extension (CLI + Telegram only)

---

## 9. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Resume Matcher down | Medium | High | `/health` check; queue jobs; user notification |
| LinkedIn scraper blocked | Low | High | Use Apify's managed service (officially endorsed) |
| Duplicate applications | Low | Critical | SQLite deduplication with job_id uniqueness |
| Missed good opportunities | Medium | Medium | Lower resume match threshold; `/list` for review |
| Database corruption | Very Low | Critical | Daily SQLite backups; JSON snapshots |
| Telegram token leak | Low | High | Use `.env` with gitignore; rotate token if leaked |

---

## 10. Roadmap

### Phase 1 ✅ (Completed)
- LinkedIn scraper via Apify
- Resume Matcher integration
- Telegram bot with core commands
- SQLite deduplication
- APScheduler (8 AM + 6 PM)
- TDD test suite (157 tests, 94% coverage)

### Phase 2 (Q2 2026)
- [ ] Big company job sources (Google Careers, Meta Jobs, TSMC Careers, etc.)
- [ ] Resume content expansion (more work/project details)
- [ ] Docker deployment + setup guide
- [ ] Multi-source deduplication

### Phase 3 (Q3 2026)
- [ ] Resume Matcher cloud deployment
- [ ] Job recommendation engine (feedback loop)
- [ ] Interview tracking (follow-ups, offers)
- [ ] Analytics dashboard (application stats)

---

## 11. Dependencies

### External Services
- **Apify**: LinkedIn Jobs Scraper actor (requires token)
- **Resume Matcher API**: Local or cloud (requires setup)
- **Telegram Bot API**: Telegram Bot token
- **Python 3.12+**: Runtime

### Internal Components
- `agent/scraper.py` — Apify integration
- `agent/improver.py` — Resume Matcher client
- `agent/notifier.py` — Telegram bot
- `agent/db.py` — SQLite operations
- `agent/config.py` — Configuration management
- `main.py` — Orchestration + APScheduler

---

## 12. Approval & Sign-off

| Role | Name | Date | Sign-off |
|------|------|------|----------|
| Product Owner | Cheng Ting Chen | 2026-03-27 | ✅ Approved |
| Developer | Claude (AI) | 2026-03-27 | ✅ Acknowledged |

---

**Document Version History**
- v1.0 (2026-03-27): Initial PRD created after Phase 1 completion
