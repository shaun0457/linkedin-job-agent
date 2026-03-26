"""Entry point: starts Telegram Bot + APScheduler."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from agent import db
from agent import improver
from agent import notifier
from agent.config import Settings, get_schedule_config, get_search_config
from agent.deduper import filter_new
from agent.scraper import scrape_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_pipeline(app: Application, settings: Settings) -> None:
    """Full pipeline: scrape → deduplicate → tailor → notify."""
    logger.info("Pipeline started")

    search_cfg = get_search_config()

    # ── 1. Check master resume ──────────────────────────────────────────
    master_id = await improver.get_master_resume_id(settings.resume_matcher_url)
    if not master_id:
        logger.error("No master resume found, aborting pipeline")
        await notifier.notify_error(
            app,
            settings.telegram_chat_id,
            "No master resume found in Resume Matcher. Please upload one first.",
        )
        return

    # ── 2. Scrape ───────────────────────────────────────────────────────
    if not settings.apify_token:
        logger.warning("APIFY_TOKEN not set — skipping scrape")
        await notifier.notify_error(
            app,
            settings.telegram_chat_id,
            "APIFY_TOKEN not configured. Set it in .env to enable auto-scraping.\n"
            "You can still use Resume Matcher manually.",
        )
        return

    try:
        jobs = scrape_jobs(settings.apify_token, search_cfg)
    except Exception as e:
        logger.error("Scraper failed: %s", e)
        await notifier.notify_error(
            app, settings.telegram_chat_id, f"Scraper failed: {e}"
        )
        return

    # ── 3. Deduplicate ──────────────────────────────────────────────────
    new_jobs = filter_new(jobs)
    logger.info("%d new jobs after dedup (of %d scraped)", len(new_jobs), len(jobs))

    if not new_jobs:
        logger.info("No new jobs found")
        return

    # ── 4. Tailor + notify each job ─────────────────────────────────────
    failed = 0
    for job in new_jobs:
        result = await improver.tailor_resume(
            settings.resume_matcher_url, master_id, job
        )

        if result is None:
            logger.warning("Tailoring failed for job %s, skipping", job.job_id)
            failed += 1
            continue

        now = datetime.now(timezone.utc).isoformat()
        db.insert_job(
            job_id=job.job_id,
            title=job.title,
            company=job.company,
            url=job.url,
            preview_resume_id=result.preview_resume_id,
            notified_at=now,
        )

        await notifier.notify_job(app, settings.telegram_chat_id, result)

    if failed:
        await notifier.notify_error(
            app,
            settings.telegram_chat_id,
            f"{failed} 個職缺處理失敗，已略過。",
        )

    logger.info("Pipeline complete")


def main() -> None:
    db.init_db()
    settings = Settings()

    app = notifier.build_application(settings)

    # Make pipeline callable from Telegram /run command
    async def _run_pipeline():
        await run_pipeline(app, settings)

    app.bot_data["settings"] = settings
    app.bot_data["run_pipeline"] = _run_pipeline

    # ── Scheduler ───────────────────────────────────────────────────────
    schedule = get_schedule_config()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_pipeline,
        trigger="cron",
        hour=schedule["hour"],
        minute=schedule["minute"],
        id="daily_pipeline",
    )

    async def post_init(application: Application) -> None:
        scheduler.start()
        logger.info(
            "Scheduler started — daily run at %02d:%02d",
            schedule["hour"],
            schedule["minute"],
        )

    app.post_init = post_init
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
