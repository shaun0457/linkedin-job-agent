import logging

from apify_client import ApifyClient

from agent.models import Job, SearchConfig

logger = logging.getLogger(__name__)

# Apify actor for LinkedIn Jobs Scraper
ACTOR_ID = "curious_coder/linkedin-jobs-scraper"


def scrape_jobs(token: str, config: SearchConfig) -> list[Job]:
    """Fetch job listings from LinkedIn via Apify actor."""
    client = ApifyClient(token)

    run_input = {
        "searchQueries": config.keywords,
        "location": config.location,
        "experienceLevel": config.experience_level,
        "maxResults": config.max_jobs_per_run,
    }

    logger.info(
        "Starting Apify scrape: keywords=%s location=%s max=%d",
        config.keywords,
        config.location,
        config.max_jobs_per_run,
    )

    run = client.actor(ACTOR_ID).call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    jobs: list[Job] = []
    for item in items:
        job = _parse_item(item)
        if job is None:
            continue
        if any(bl.lower() in job.company.lower() for bl in config.blacklist_companies):
            logger.debug("Skipping blacklisted company: %s", job.company)
            continue
        jobs.append(job)

    logger.info("Scrape complete: %d jobs returned", len(jobs))
    return jobs


def _parse_item(item: dict) -> Job | None:
    job_id = item.get("id") or item.get("jobId") or item.get("trackingId")
    title = item.get("title") or item.get("jobTitle")
    company = item.get("companyName") or item.get("company")
    url = item.get("jobUrl") or item.get("url")
    description = item.get("description") or item.get("jobDescription") or ""

    if not all([job_id, title, company, url]):
        logger.warning("Skipping incomplete item: %s", item.get("id"))
        return None

    return Job(
        job_id=str(job_id),
        title=str(title),
        company=str(company),
        location=item.get("location", ""),
        url=str(url),
        description=str(description),
        salary=item.get("salary"),
        posted_at=item.get("postedAt") or item.get("publishedAt"),
    )
