import asyncio
import logging

import httpx

from agent.models import Job, TailoredResult

logger = logging.getLogger(__name__)

POLL_INTERVAL = 3      # seconds between status checks
POLL_TIMEOUT = 60      # total seconds before giving up
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0    # seconds


async def tailor_resume(
    base_url: str, master_resume_id: str, job: Job
) -> TailoredResult | None:
    """Upload JD to Resume Matcher, run improve/preview, return TailoredResult or None."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        rm_job_id = await _upload_job(client, job)
        if rm_job_id is None:
            return None

        preview_id = await _improve_preview(client, master_resume_id, rm_job_id)
        if preview_id is None:
            return None

        keywords = await _poll_until_done(client, preview_id)
        if keywords is None:
            return None

        return TailoredResult(job=job, preview_resume_id=preview_id, keywords_added=keywords)


async def confirm_resume(base_url: str, preview_resume_id: str) -> str | None:
    """Confirm a previewed resume and return the confirmed_resume_id."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(
                    f"/api/v1/resumes/improve/confirm",
                    json={"resume_id": preview_resume_id},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("id") or data.get("resume_id")
            except httpx.HTTPError as e:
                logger.warning("Confirm attempt %d failed: %s", attempt + 1, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
    return None


async def delete_preview(base_url: str, preview_resume_id: str) -> None:
    """Best-effort delete of a preview resume (cleanup on skip)."""
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
            await client.delete(f"/api/v1/resumes/{preview_resume_id}")
    except Exception as e:
        logger.warning("Failed to delete preview %s: %s", preview_resume_id, e)


async def get_master_resume_id(base_url: str) -> str | None:
    """Fetch master resume ID from Resume Matcher."""
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        try:
            resp = await client.get("/api/v1/resumes/list", params={"include_master": "true"})
            resp.raise_for_status()
            resumes = resp.json()
            masters = [r for r in resumes if r.get("is_master")]
            if masters:
                return masters[0]["id"]
        except httpx.HTTPError as e:
            logger.error("Failed to fetch master resume: %s", e)
    return None


# ── internal helpers ───────────────────────────────────────────────────────


async def _upload_job(client: httpx.AsyncClient, job: Job) -> str | None:
    try:
        resp = await client.post(
            "/api/v1/jobs/upload",
            json={"content": job.description, "title": job.title},
        )
        resp.raise_for_status()
        return resp.json()["id"]
    except httpx.HTTPError as e:
        logger.error("Job upload failed for %s: %s", job.job_id, e)
        return None


async def _improve_preview(
    client: httpx.AsyncClient, master_resume_id: str, rm_job_id: str
) -> str | None:
    try:
        resp = await client.post(
            "/api/v1/resumes/improve/preview",
            json={"resume_id": master_resume_id, "job_id": rm_job_id},
        )
        resp.raise_for_status()
        return resp.json()["id"]
    except httpx.HTTPError as e:
        logger.error("Improve preview failed: %s", e)
        return None


async def _poll_until_done(
    client: httpx.AsyncClient, resume_id: str
) -> list[str] | None:
    """Poll processing_status until completed/failed. Returns keywords_added or None."""
    for _ in range(POLL_TIMEOUT // POLL_INTERVAL):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            resp = await client.get(f"/api/v1/resumes/{resume_id}")
            resp.raise_for_status()
            data = resp.json()
            status = data.get("processing_status")

            if status == "completed":
                improvements = data.get("improvements", [])
                keywords = [
                    imp.get("keyword") or imp.get("text", "")
                    for imp in improvements
                    if imp.get("type") == "keyword_added"
                ]
                return keywords

            if status == "failed":
                logger.error("Resume processing failed for %s", resume_id)
                return None

        except httpx.HTTPError as e:
            logger.warning("Poll error for %s: %s", resume_id, e)

    logger.error("Poll timeout for resume %s", resume_id)
    return None
