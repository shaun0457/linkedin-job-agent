from agent import db
from agent.models import Job


def filter_new(jobs: list[Job]) -> list[Job]:
    """Return only jobs not yet in seen_jobs (by job_id OR url)."""
    return [j for j in jobs if not db.is_seen(j.job_id, j.url)]
