import asyncio
import logging

import httpx

from agent.models import Job, TailoredResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2.0    # seconds


async def tailor_resume(
    base_url: str, master_resume_id: str, job: Job
) -> TailoredResult | None:
    """Upload JD to Resume Matcher, run improve/preview, return TailoredResult or None.

    The preview endpoint is synchronous (LLM call returns full result).  The
    confirm_payload stored on the result contains everything needed to call
    POST /api/v1/resumes/improve/confirm later when the user approves.
    """
    async with httpx.AsyncClient(base_url=base_url, timeout=300) as client:
        rm_job_id = await _upload_job(client, job)
        if rm_job_id is None:
            return None

        preview_data = await _improve_preview(client, master_resume_id, rm_job_id)
        if preview_data is None:
            return None

        improved_data = preview_data.get("resume_preview")
        improvements = preview_data.get("improvements", [])
        request_id = preview_data.get("request_id", rm_job_id)

        confirm_payload = {
            "resume_id": master_resume_id,
            "job_id": rm_job_id,
            "improved_data": improved_data,
            "improvements": improvements,
        }

        return TailoredResult(
            job=job,
            preview_resume_id=request_id,
            keywords_added=[],
            confirm_payload=confirm_payload,
        )


async def confirm_resume(base_url: str, confirm_payload: dict) -> str | None:
    """Confirm a previewed resume and return the confirmed resume_id.

    confirm_payload must contain: resume_id, job_id, improved_data, improvements.
    """
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(
                    "/api/v1/resumes/improve/confirm",
                    json=confirm_payload,
                )
                resp.raise_for_status()
                return resp.json()["data"]["resume_id"]
            except httpx.HTTPError as e:
                logger.warning("Confirm attempt %d failed: %s", attempt + 1, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_BACKOFF * (attempt + 1))
    return None


async def delete_preview(base_url: str, preview_resume_id: str) -> None:
    """No-op: previews are not persisted server-side in this API version."""


async def get_master_resume_id(base_url: str) -> str | None:
    """Fetch master resume ID from Resume Matcher."""
    async with httpx.AsyncClient(base_url=base_url, timeout=15) as client:
        try:
            resp = await client.get("/api/v1/resumes/list", params={"include_master": "true"})
            resp.raise_for_status()
            resumes = resp.json().get("data", [])
            masters = [r for r in resumes if r.get("is_master")]
            if masters:
                return masters[0]["resume_id"]
        except httpx.HTTPError as e:
            logger.error("Failed to fetch master resume: %s", e)
    return None


# ── internal helpers ───────────────────────────────────────────────────────


async def _upload_job(client: httpx.AsyncClient, job: Job) -> str | None:
    """Upload a job description; return the job_id string or None on failure."""
    try:
        resp = await client.post(
            "/api/v1/jobs/upload",
            json={"job_descriptions": [job.description]},
        )
        resp.raise_for_status()
        job_ids = resp.json().get("job_id", [])
        return job_ids[0] if job_ids else None
    except httpx.HTTPError as e:
        logger.error("Job upload failed for %s: %s", job.job_id, e)
        return None


async def _improve_preview(
    client: httpx.AsyncClient, master_resume_id: str, rm_job_id: str
) -> dict | None:
    """Call improve/preview (synchronous LLM call) and return the data payload dict."""
    try:
        resp = await client.post(
            "/api/v1/resumes/improve/preview",
            json={"resume_id": master_resume_id, "job_id": rm_job_id},
        )
        resp.raise_for_status()
        return resp.json().get("data")
    except httpx.HTTPError as e:
        logger.error("Improve preview failed: %s", e)
        return None
