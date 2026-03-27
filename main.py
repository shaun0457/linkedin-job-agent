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
from agent.scraper import scrape_jobs, scrape_jobs_mock

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
    try:
        if not settings.apify_token or settings.apify_token.startswith("mock"):
            logger.info("Mock scraper mode active")
            jobs = scrape_jobs_mock(search_cfg)
        else:
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
    tailored = 0
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
            preview_data=result.preview_data,
            rm_job_id=result.rm_job_id,
            master_resume_id=result.master_resume_id,
            notified_at=now,
        )

        if settings.auto_confirm:
            await improver.confirm_resume(
                settings.resume_matcher_url,
                master_resume_id=result.master_resume_id,
                preview_data=result.preview_data,
            )
        else:
            await notifier.notify_job(app, settings.telegram_chat_id, result)
        tailored += 1

    await notifier.notify_run_summary(
        app,
        settings.telegram_chat_id,
        found=len(new_jobs),
        tailored=tailored,
        failed=failed,
    )

    logger.info("Pipeline complete — found=%d tailored=%d failed=%d", len(new_jobs), tailored, failed)


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

    # Add a job for each configured hour
    for idx, hour in enumerate(schedule["hours"]):
        scheduler.add_job(
            _run_pipeline,
            trigger="cron",
            hour=hour,
            minute=schedule["minute"],
            id=f"daily_pipeline_{idx}",
        )

    async def post_init(application: Application) -> None:
        scheduler.start()
        times_str = ", ".join(f"{h:02d}:{schedule['minute']:02d}" for h in schedule["hours"])
        logger.info("Scheduler started — daily runs at: %s", times_str)

    app.post_init = post_init
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
