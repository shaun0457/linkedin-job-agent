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

    raw_jobs = [_parse_item(item) for item in items]
    parsed = [j for j in raw_jobs if j is not None]
    jobs = _apply_blacklist(parsed, config.blacklist_companies)

    logger.info("Scrape complete: %d jobs returned", len(jobs))
    return jobs


def scrape_jobs_mock(config: SearchConfig) -> list[Job]:
    """Return hardcoded mock jobs for local testing without Apify."""
    logger.info("Using mock scraper — returning hardcoded jobs")
    return [
        Job(
            job_id="mock-001",
            title="ML Engineer",
            company="DeepMind",
            location="London, UK",
            url="https://www.linkedin.com/jobs/view/mock-001/",
            description=(
                "Join DeepMind's ML team to develop state-of-the-art reinforcement learning "
                "systems. You will work on large-scale training pipelines using PyTorch, "
                "design experiments with Transformers and diffusion models, and collaborate "
                "with researchers on cutting-edge AI safety problems."
            ),
            salary="£90,000 – £130,000",
            posted_at="2024-01-15",
        ),
        Job(
            job_id="mock-002",
            title="Senior AI Research Engineer",
            company="Google DeepMind",
            location="Berlin, Germany",
            url="https://www.linkedin.com/jobs/view/mock-002/",
            description=(
                "We are looking for a Senior AI Research Engineer to join our Berlin office. "
                "Responsibilities include building scalable ML infrastructure, fine-tuning LLMs "
                "with RLHF, and contributing to open-source AI projects. Strong experience with "
                "JAX, TensorFlow, and distributed training required."
            ),
            salary="€95,000 – €140,000",
            posted_at="2024-01-14",
        ),
        Job(
            job_id="mock-003",
            title="Machine Learning Platform Engineer",
            company="Stability AI",
            location="Remote (Europe)",
            url="https://www.linkedin.com/jobs/view/mock-003/",
            description=(
                "Stability AI is seeking a Machine Learning Platform Engineer to build and "
                "maintain our model training and serving infrastructure. You will work with "
                "Kubernetes, Ray, and custom CUDA kernels to accelerate diffusion model training "
                "at scale. Experience with MLOps, model quantization, and inference optimization "
                "is highly valued."
            ),
            salary="€80,000 – €120,000",
            posted_at="2024-01-13",
        ),
    ]


def _apply_blacklist(jobs: list[Job], blacklist: list[str]) -> list[Job]:
    """Return jobs excluding any from blacklisted companies (case-insensitive substring)."""
    if not blacklist:
        return list(jobs)
    result = []
    for job in jobs:
        if any(bl.lower() in job.company.lower() for bl in blacklist):
            logger.debug("Skipping blacklisted company: %s", job.company)
        else:
            result.append(job)
    return result


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
