"""TDD tests for agent/scraper.py."""
from unittest.mock import MagicMock, patch

from agent.models import Job, SearchConfig
from agent.scraper import _parse_item, scrape_jobs_mock, _apply_blacklist, scrape_jobs, _build_search_urls


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


def test_parse_item_link_and_description_text_fields():
    """Actor returns 'link' for URL and 'descriptionText' for description."""
    item = {
        "id": "42",
        "title": "ML Engineer",
        "companyName": "Bending Spoons",
        "link": "https://de.linkedin.com/jobs/view/ml-engineer-at-bending-spoons",
        "descriptionText": "Join our team...",
        "location": "Berlin, Germany",
        "postedAt": "2026-03-30T18:06:06.000Z",
    }
    job = _parse_item(item)
    assert job is not None
    assert job.url == "https://de.linkedin.com/jobs/view/ml-engineer-at-bending-spoons"
    assert job.description == "Join our team..."


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


# ── scrape_jobs (ApifyClient mocked) ─────────────────────────────────────────


def _mock_apify(items: list[dict]):
    """Return a mock ApifyClient that yields `items` from a dataset."""
    mock_run = {"defaultDatasetId": "dataset-abc"}
    mock_dataset = MagicMock()
    mock_dataset.iterate_items.return_value = iter(items)
    mock_actor = MagicMock()
    mock_actor.call.return_value = mock_run
    mock_client = MagicMock()
    mock_client.actor.return_value = mock_actor
    mock_client.dataset.return_value = mock_dataset
    return mock_client


_VALID_ITEM = {
    "id": "live-1",
    "title": "AI Engineer",
    "companyName": "TechCorp",
    "location": "Berlin, Germany",
    "link": "https://linkedin.com/jobs/view/live-1/",
    "descriptionText": "Build AI systems",
}


def test_scrape_jobs_returns_parsed_jobs():
    config = _make_config()
    mock_client = _mock_apify([_VALID_ITEM])

    with patch("agent.scraper.ApifyClient", return_value=mock_client):
        jobs = scrape_jobs("fake-token", config)

    assert len(jobs) == 1
    assert jobs[0].job_id == "live-1"
    assert jobs[0].title == "AI Engineer"
    assert jobs[0].company == "TechCorp"


def test_scrape_jobs_sends_correct_run_input():
    config = _make_config(
        keywords=["ML Engineer"], location="Netherlands",
        experience_level=["MID_SENIOR_LEVEL"], max_jobs_per_run=5
    )
    mock_client = _mock_apify([])

    with patch("agent.scraper.ApifyClient", return_value=mock_client):
        scrape_jobs("token", config)

    call_kwargs = mock_client.actor.return_value.call.call_args.kwargs
    run_input = call_kwargs["run_input"]
    assert "urls" in run_input
    assert len(run_input["urls"]) == 1
    assert "keywords=ML%20Engineer" in run_input["urls"][0]
    assert "location=Netherlands" in run_input["urls"][0]
    assert "f_E=4" in run_input["urls"][0]  # MID_SENIOR_LEVEL = 4
    assert run_input["count"] == 5


# ── _build_search_urls ───────────────────────────────────────────────────────


def test_build_search_urls_single_keyword():
    config = _make_config(keywords=["AI Engineer"], location="Germany", experience_level=[])
    urls = _build_search_urls(config)
    assert len(urls) == 1
    assert "keywords=AI%20Engineer" in urls[0]
    assert "location=Germany" in urls[0]
    assert "f_E" not in urls[0]


def test_build_search_urls_multiple_keywords():
    config = _make_config(keywords=["ML Engineer", "Data Scientist"], location="Berlin")
    urls = _build_search_urls(config)
    assert len(urls) == 2
    assert "ML%20Engineer" in urls[0]
    assert "Data%20Scientist" in urls[1]


def test_build_search_urls_experience_levels():
    config = _make_config(experience_level=["ENTRY_LEVEL", "MID_SENIOR_LEVEL"])
    urls = _build_search_urls(config)
    assert "f_E=2%2C4" in urls[0]


def test_build_search_urls_no_location():
    config = _make_config(location="")
    urls = _build_search_urls(config)
    assert "location=" not in urls[0]


def test_build_search_urls_includes_time_filter():
    config = _make_config(time_filter="r86400")
    urls = _build_search_urls(config)
    assert "f_TPR=r86400" in urls[0]
    assert "sortBy=DD" in urls[0]


def test_build_search_urls_default_time_filter():
    config = _make_config()  # default time_filter
    urls = _build_search_urls(config)
    assert "f_TPR=r86400" in urls[0]
    assert "sortBy=DD" in urls[0]


def test_build_search_urls_weekly_time_filter():
    config = _make_config(time_filter="r604800")
    urls = _build_search_urls(config)
    assert "f_TPR=r604800" in urls[0]


def test_build_search_urls_empty_time_filter():
    config = _make_config(time_filter="")
    urls = _build_search_urls(config)
    assert "f_TPR" not in urls[0]
    assert "sortBy" not in urls[0]


def test_scrape_jobs_applies_blacklist():
    config = _make_config(blacklist_companies=["TechCorp"])
    mock_client = _mock_apify([_VALID_ITEM])  # TechCorp item

    with patch("agent.scraper.ApifyClient", return_value=mock_client):
        jobs = scrape_jobs("token", config)

    assert jobs == []


def test_scrape_jobs_skips_invalid_items():
    """Items missing required fields are silently skipped."""
    bad_item = {"id": "bad", "companyName": "Acme"}  # no title, no url
    config = _make_config()
    mock_client = _mock_apify([bad_item, _VALID_ITEM])

    with patch("agent.scraper.ApifyClient", return_value=mock_client):
        jobs = scrape_jobs("token", config)

    assert len(jobs) == 1
    assert jobs[0].job_id == "live-1"
