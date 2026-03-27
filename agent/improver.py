"""Resume Matcher API client — aligned with actual RM API schema."""
import asyncio
import logging

import httpx

from agent.models import Job, TailoredResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0


async def tailor_resume(
    base_url: str, master_resume_id: str, job: Job
) -> TailoredResult | None:
    """Upload JD to Resume Matcher, run improve/preview, return TailoredResult or None."""
    async with httpx.AsyncClient(base_url=base_url, timeout=270) as client:
        rm_job_id = await _upload_job(client, job)
        if rm_job_id is None:
            return None

        # improve/preview is synchronous on the RM side (up to 4 min timeout)
        preview_data = await _improve_preview(client, master_resume_id, rm_job_id)
        if preview_data is None:
            return None

        keywords = _extract_keywords(preview_data)
        return TailoredResult(
            job=job,
            preview_data=preview_data,
            rm_job_id=rm_job_id,
            master_resume_id=master_resume_id,
            keywords_added=keywords,
        )


async def confirm_resume(
    base_url: str,
    master_resume_id: str,
    preview_data: dict,
) -> str | None:
    """Confirm a previewed resume. Returns the confirmed resume_id or None."""
    payload = {
        "resume_id": master_resume_id,
        "job_id": preview_data["job_id"],
        "improved_data": preview_data["resume_preview"],
        "improvements": preview_data.get("improvements", []),
    }

    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post("/api/v1/resumes/improve/confirm", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["data"]["resume_id"]
            except httpx.HTTPError as e:
                logger.warning("Confirm attempt %d failed: %s", attempt + 1, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
    return None


async def get_master_resume_id(base_url: str) -> str | None:
    """Fetch master resume ID from Resume Matcher."""
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        try:
            resp = await client.get(
                "/api/v1/resumes/list", params={"include_master": "true"}
            )
            resp.raise_for_status()
            body = resp.json()
            resumes = body.get("data", [])
            masters = [r for r in resumes if r.get("is_master")]
            if masters:
                return masters[0]["resume_id"]
        except httpx.HTTPError as e:
            logger.error("Failed to fetch master resume: %s", e)
    return None


# ── internal helpers ───────────────────────────────────────────────────────


async def _upload_job(client: httpx.AsyncClient, job: Job) -> str | None:
    """Upload JD text. Returns RM job_id string or None."""
    try:
        resp = await client.post(
            "/api/v1/jobs/upload",
            json={"job_descriptions": [job.description]},
        )
        resp.raise_for_status()
        return resp.json()["job_id"][0]
    except (httpx.HTTPError, KeyError, IndexError) as e:
        logger.error("Job upload failed for %s: %s", job.job_id, e)
        return None


async def _improve_preview(
    client: httpx.AsyncClient, master_resume_id: str, rm_job_id: str
) -> dict | None:
    """Run improve/preview. Returns full ImproveResumeData dict or None.

    Note: preview is synchronous on RM side — no polling needed.
    The data.resume_id will be None (preview not yet persisted).
    """
    try:
        resp = await client.post(
            "/api/v1/resumes/improve/preview",
            json={"resume_id": master_resume_id, "job_id": rm_job_id},
        )
        resp.raise_for_status()
        return resp.json()["data"]
    except (httpx.HTTPError, KeyError) as e:
        logger.error("Improve preview failed: %s", e)
        return None


def _extract_keywords(preview_data: dict) -> list[str]:
    """Extract keyword suggestions from improvements list."""
    improvements = preview_data.get("improvements", [])
    return [
        imp.get("suggestion", "")
        for imp in improvements
        if imp.get("suggestion")
    ][:10]  # cap at 10 for Telegram display
