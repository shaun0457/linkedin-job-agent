# LinkedIn Job Agent

Semi-automatic job hunting pipeline:
**Apify LinkedIn scraper → Resume Matcher API → Telegram Bot**

Finds new jobs daily, auto-tailors your resume for each one, and pings you on Telegram to confirm or skip.

---

## How It Works

```
[APScheduler 08:00]
        │
        ▼
  Apify scraper ──► Dedup (SQLite) ──► Resume Matcher improve/preview
                                               │
                                               ▼
                                        Telegram notification
                                        [✅ Confirm] [❌ Skip]
                                               │
                            ┌──────────────────┴───────────────────┐
                         confirm                                  skip
                            │                                      │
                   improve/confirm API                      delete preview
                   send PDF link                            mark skipped
```

---

## Setup

### 1. Prerequisites

- Python 3.11+
- [Resume Matcher](https://github.com/shaun0457/Resume-Matcher) running locally (default: `http://localhost:8001`)
- Upload your master resume in Resume Matcher first

### 2. Install dependencies

```bash
# With uv (recommended)
pip install uv
uv sync

# Or with pip
pip install -e .
```

### 3. Create a Telegram Bot

1. Open Telegram, message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, follow prompts → get your **BOT_TOKEN**
3. Message your new bot, then visit:
   `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
4. Send any message to the bot and note your **chat_id** from the response

### 4. Create an Apify account

1. Sign up at [apify.com](https://apify.com) (free tier: 5 USD/month compute units)
2. Go to Settings → Integrations → API token → copy your **APIFY_TOKEN**

### 5. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```
APIFY_TOKEN=apify_api_xxxxxxxxxxxx
TELEGRAM_BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=your_numeric_chat_id
RESUME_MATCHER_URL=http://localhost:8001
```

Edit `config.yaml` to set initial search preferences (can also change via Telegram):
```yaml
search:
  keywords:
    - "AI/ML Engineer"
    - "Machine Learning Engineer"
  location: "Germany"
  max_jobs_per_run: 20
```

### 6. Run

```bash
python main.py
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/run` | Trigger pipeline immediately |
| `/status` | Today's stats (found / confirmed / skipped) |
| `/list` | Last 10 confirmed jobs with PDF links |
| `/retry <job_id>` | Retry confirm for a stuck job |
| `/config` | Show current search settings |
| `/set_keywords AI Engineer, ML Engineer` | Update search keywords |
| `/set_location Berlin, Germany` | Update location |
| `/set_max 15` | Update max jobs per run |

---

## Project Structure

```
linkedin-job-agent/
├── main.py              # Entry point: Bot + Scheduler
├── config.yaml          # Default search config
├── .env                 # Secrets (not committed)
├── agent/
│   ├── models.py        # Job, TailoredResult, SearchConfig dataclasses
│   ├── db.py            # SQLite wrapper (seen_jobs, search_config)
│   ├── config.py        # Config loader (YAML + DB overrides)
│   ├── scraper.py       # Apify LinkedIn Jobs Scraper client
│   ├── deduper.py       # Deduplication logic
│   ├── improver.py      # Resume Matcher API client
│   └── notifier.py      # Telegram Bot (messages + callbacks + commands)
└── data/
    └── jobs.db          # SQLite database (auto-created)
```

---

## Notes

- Config changes via Telegram (`/set_keywords` etc.) are stored in SQLite and override `config.yaml` values
- Auto-submitting applications is intentionally out of scope — the pipeline stops at tailored resume + PDF link
- The Apify actor used is `curious_coder/linkedin-jobs-scraper` — check [Apify Store](https://apify.com/store) for latest actor ID if scraping breaks
