"""TDD tests for agent/scraper.py."""
from agent.models import Job, SearchConfig
from agent.scraper import _parse_item, scrape_jobs_mock, _apply_blacklist


def _make_config(**kwargs) -> SearchConfig:
    defaults = dict(
        keywords=["ML Engineer"],
        location="Germany",
        experience_level=["MID_SENIOR_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=10,
    )
    defaults.update(kwargs)
    return SearchConfig(**defaults)


# ── _parse_item ───────────────────────────────────────────────────────────────


def test_parse_item_full_fields():
    item = {
        "id": "12345",
        "title": "ML Engineer",
        "companyName": "DeepMind",
        "location": "London, UK",
        "jobUrl": "https://linkedin.com/jobs/view/12345/",
        "description": "Some description",
        "salary": "£80,000 – £120,000",
        "postedAt": "2024-01-15",
    }
    job = _parse_item(item)
    assert job is not None
    assert job.job_id == "12345"
    assert job.title == "ML Engineer"
    assert job.company == "DeepMind"
    assert job.location == "London, UK"
    assert job.url == "https://linkedin.com/jobs/view/12345/"
    assert job.description == "Some description"
    assert job.salary == "£80,000 – £120,000"
    assert job.posted_at == "2024-01-15"


def test_parse_item_alternate_field_names():
    """Scraper should handle alternate field name variants."""
    item = {
        "jobId": "99",
        "jobTitle": "AI Engineer",
        "company": "OpenAI",
        "url": "https://linkedin.com/jobs/view/99/",
        "jobDescription": "Description here",
    }
    job = _parse_item(item)
    assert job is not None
    assert job.job_id == "99"
    assert job.title == "AI Engineer"
    assert job.company == "OpenAI"


def test_parse_item_missing_required_returns_none():
    """Missing required fields (title) → None."""
    item = {
        "id": "123",
        "companyName": "Acme",
        "jobUrl": "https://linkedin.com/jobs/view/123/",
        # no title
    }
    assert _parse_item(item) is None


def test_parse_item_missing_url_returns_none():
    item = {
        "id": "456",
        "title": "Engineer",
        "companyName": "Acme",
        # no url
    }
    assert _parse_item(item) is None


def test_parse_item_empty_description_defaults_to_empty_string():
    item = {
        "id": "789",
        "title": "Engineer",
        "companyName": "Acme",
        "jobUrl": "https://example.com/789",
        # no description
    }
    job = _parse_item(item)
    assert job is not None
    assert job.description == ""


def test_parse_item_location_defaults_to_empty_string():
    item = {
        "id": "000",
        "title": "Engineer",
        "companyName": "Acme",
        "jobUrl": "https://example.com/000",
        # no location
    }
    job = _parse_item(item)
    assert job is not None
    assert job.location == ""


# ── scrape_jobs_mock ──────────────────────────────────────────────────────────


def test_scrape_jobs_mock_returns_list():
    config = _make_config()
    jobs = scrape_jobs_mock(config)
    assert isinstance(jobs, list)
    assert len(jobs) > 0


def test_scrape_jobs_mock_all_jobs_are_valid():
    config = _make_config()
    jobs = scrape_jobs_mock(config)
    for job in jobs:
        assert isinstance(job, Job)
        assert job.job_id
        assert job.title
        assert job.company
        assert job.url.startswith("https://")
        assert job.description


def test_scrape_jobs_mock_blacklist_filtering():
    """scrape_jobs_mock does NOT apply blacklist — that's handled by scrape_jobs.

    The blacklist filter is in scrape_jobs (live). Mock returns fixed jobs.
    The actual blacklist filtering test is in test_scraper_blacklist below.
    """
    config = _make_config(blacklist_companies=["DeepMind"])
    jobs = scrape_jobs_mock(config)
    # Mock ignores blacklist — returns fixed list regardless
    assert len(jobs) > 0


def test_scrape_jobs_mock_job_ids_are_unique():
    config = _make_config()
    jobs = scrape_jobs_mock(config)
    ids = [j.job_id for j in jobs]
    assert len(ids) == len(set(ids))


# ── _apply_blacklist ──────────────────────────────────────────────────────────


def _make_simple_job(job_id: str, company: str) -> Job:
    return Job(
        job_id=job_id,
        title="Engineer",
        company=company,
        location="Anywhere",
        url=f"https://example.com/{job_id}",
        description="desc",
    )


def test_apply_blacklist_removes_blacklisted_company():
    jobs = [
        _make_simple_job("1", "EvilCorp"),
        _make_simple_job("2", "GoodCorp"),
    ]
    result = _apply_blacklist(jobs, ["EvilCorp"])
    assert len(result) == 1
    assert result[0].company == "GoodCorp"


def test_apply_blacklist_case_insensitive():
    jobs = [_make_simple_job("1", "evilcorp")]
    result = _apply_blacklist(jobs, ["EvilCorp"])
    assert result == []


def test_apply_blacklist_partial_name_match():
    """Blacklist entry is a substring of company name."""
    jobs = [_make_simple_job("1", "EvilCorp Inc.")]
    result = _apply_blacklist(jobs, ["evilcorp"])
    assert result == []


def test_apply_blacklist_empty_blacklist_passes_all():
    jobs = [_make_simple_job("1", "AnyCompany"), _make_simple_job("2", "OtherCo")]
    result = _apply_blacklist(jobs, [])
    assert len(result) == 2


def test_apply_blacklist_returns_new_list():
    """Verify the function returns a new list (no mutation)."""
    jobs = [_make_simple_job("1", "EvilCorp")]
    result = _apply_blacklist(jobs, ["EvilCorp"])
    assert result is not jobs
