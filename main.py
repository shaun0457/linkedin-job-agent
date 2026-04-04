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
from dataclasses import replace

from agent.config import Settings, get_schedule_config, get_search_config, get_scoring_config
from agent.deduper import filter_new
from agent.scorer import score_jobs
from agent.scraper import scrape_jobs, scrape_jobs_mock

# Escalation order for time filter when no new jobs found
_TIME_ESCALATION = ["r86400", "r604800", "r2592000"]

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

    # ── 2. Scrape + Deduplicate (with time escalation) ────────────────
    # Build escalation list: start from current time_filter, then widen
    current = search_cfg.time_filter
    try:
        start_idx = _TIME_ESCALATION.index(current)
    except ValueError:
        start_idx = 0
    time_filters_to_try = _TIME_ESCALATION[start_idx:]

    new_jobs = []
    for time_filter in time_filters_to_try:
        cfg = replace(search_cfg, time_filter=time_filter)
        try:
            if not settings.apify_token or settings.apify_token.startswith("mock"):
                logger.info("Mock scraper mode active")
                jobs = scrape_jobs_mock(cfg)
            else:
                jobs = scrape_jobs(settings.apify_token, cfg)
        except Exception as e:
            logger.error("Scraper failed: %s", e)
            await notifier.notify_error(
                app, settings.telegram_chat_id, f"Scraper failed: {e}"
            )
            return

        new_jobs = filter_new(jobs)
        logger.info(
            "%d new jobs after dedup (of %d scraped, time_filter=%s)",
            len(new_jobs), len(jobs), time_filter,
        )
        if new_jobs:
            break
        logger.info("No new jobs with %s, expanding time range…", time_filter)

    if not new_jobs:
        logger.info("No new jobs found after all time ranges")
        await notifier.notify_run_summary(
            app, settings.telegram_chat_id, found=0, tailored=0, failed=0,
        )
        return

    # ── 4. AI Score (label, not filter) ──────────────────────────────
    scored_jobs: list | None = None
    if settings.gemini_api_key:
        scoring_cfg = get_scoring_config()
        scored_jobs = await score_jobs(
            new_jobs, api_key=settings.gemini_api_key,
            scoring_config=scoring_cfg,
        )
    else:
        logger.info("No GEMINI_API_KEY set, skipping AI scoring")

    # ── 5. Tiered processing ────────────────────────────────────────
    tailored = 0
    failed = 0
    n_strong = 0
    n_medium = 0
    n_weak = 0

    if scored_jobs:
        strong = [s for s in scored_jobs if s.score >= 7]
        medium = [s for s in scored_jobs if 4 <= s.score <= 6]
        weak = [s for s in scored_jobs if s.score <= 3]
        n_strong, n_medium, n_weak = len(strong), len(medium), len(weak)

        # 🟢 Strong: tailor + individual notification
        for s in strong:
            job = s.job
            result = await improver.tailor_resume(
                settings.resume_matcher_url, master_id, job
            )
            if result is None:
                logger.warning("Tailoring failed for job %s", job.job_id)
                failed += 1
                continue

            now = datetime.now(timezone.utc).isoformat()
            db.insert_job(
                job_id=job.job_id, title=job.title, company=job.company,
                url=job.url, preview_data=result.preview_data,
                rm_job_id=result.rm_job_id,
                master_resume_id=result.master_resume_id,
                notified_at=now, score=s.score, score_reason=s.reason,
            )

            if settings.auto_confirm:
                await improver.confirm_resume(
                    settings.resume_matcher_url,
                    master_resume_id=result.master_resume_id,
                    preview_data=result.preview_data,
                )
            else:
                await notifier.notify_job(
                    app, settings.telegram_chat_id, result,
                    score=s.score, reason=s.reason,
                )
            tailored += 1

        # 🟡 Medium: store in DB + batch summary (no tailor)
        for s in medium:
            now = datetime.now(timezone.utc).isoformat()
            db.insert_job(
                job_id=s.job.job_id, title=s.job.title, company=s.job.company,
                url=s.job.url, preview_data={}, rm_job_id="",
                master_resume_id="", notified_at=now,
                score=s.score, score_reason=s.reason, status="medium",
            )
        if medium:
            await notifier.notify_batch_summary(
                app, settings.telegram_chat_id, medium,
            )

        # 🔴 Weak: store silently
        for s in weak:
            now = datetime.now(timezone.utc).isoformat()
            db.insert_job(
                job_id=s.job.job_id, title=s.job.title, company=s.job.company,
                url=s.job.url, preview_data={}, rm_job_id="",
                master_resume_id="", notified_at=now,
                score=s.score, score_reason=s.reason, status="weak",
            )

    else:
        # No scoring — treat all as strong (backward compatible)
        for job in new_jobs:
            result = await improver.tailor_resume(
                settings.resume_matcher_url, master_id, job
            )
            if result is None:
                logger.warning("Tailoring failed for job %s", job.job_id)
                failed += 1
                continue

            now = datetime.now(timezone.utc).isoformat()
            db.insert_job(
                job_id=job.job_id, title=job.title, company=job.company,
                url=job.url, preview_data=result.preview_data,
                rm_job_id=result.rm_job_id,
                master_resume_id=result.master_resume_id, notified_at=now,
            )

            if settings.auto_confirm:
                await improver.confirm_resume(
                    settings.resume_matcher_url,
                    master_resume_id=result.master_resume_id,
                    preview_data=result.preview_data,
                )
            else:
                await notifier.notify_job(
                    app, settings.telegram_chat_id, result,
                )
            tailored += 1

    found = len(scored_jobs) if scored_jobs else len(new_jobs)
    await notifier.notify_run_summary(
        app, settings.telegram_chat_id,
        found=found, tailored=tailored, failed=failed,
        strong=n_strong, medium=n_medium, weak=n_weak,
    )

    logger.info(
        "Pipeline complete — found=%d strong=%d medium=%d weak=%d tailored=%d failed=%d",
        found, n_strong, n_medium, n_weak, tailored, failed,
    )


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
