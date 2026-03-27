"""Tests for agent/models.py dataclasses."""
from agent.models import Job, SearchConfig, TailoredResult


def test_job_minimal_fields():
    job = Job(
        job_id="123",
        title="ML Engineer",
        company="DeepMind",
        location="London, UK",
        url="https://www.linkedin.com/jobs/view/123/",
        description="Build ML models at scale.",
    )
    assert job.job_id == "123"
    assert job.title == "ML Engineer"
    assert job.company == "DeepMind"
    assert job.location == "London, UK"
    assert job.url == "https://www.linkedin.com/jobs/view/123/"
    assert job.description == "Build ML models at scale."
    # Optional fields default to None
    assert job.salary is None
    assert job.posted_at is None


def test_job_optional_fields():
    job = Job(
        job_id="456",
        title="Data Scientist",
        company="Google",
        location="Berlin, Germany",
        url="https://www.linkedin.com/jobs/view/456/",
        description="Data science role.",
        salary="€80,000 – €120,000",
        posted_at="2024-01-15",
    )
    assert job.salary == "€80,000 – €120,000"
    assert job.posted_at == "2024-01-15"


def test_tailored_result_default_keywords():
    job = Job(
        job_id="789",
        title="Research Scientist",
        company="OpenAI",
        location="San Francisco, CA",
        url="https://www.linkedin.com/jobs/view/789/",
        description="Research role.",
    )
    result = TailoredResult(job=job, preview_resume_id="preview-abc")
    assert result.job is job
    assert result.preview_resume_id == "preview-abc"
    assert result.keywords_added == []


def test_tailored_result_with_keywords():
    job = Job(
        job_id="999",
        title="AI Engineer",
        company="Anthropic",
        location="Remote",
        url="https://www.linkedin.com/jobs/view/999/",
        description="AI role.",
    )
    result = TailoredResult(
        job=job,
        preview_resume_id="preview-xyz",
        keywords_added=["PyTorch", "Transformers", "RLHF"],
    )
    assert len(result.keywords_added) == 3
    assert "PyTorch" in result.keywords_added
    assert "RLHF" in result.keywords_added


def test_tailored_result_keywords_are_independent():
    """Verify default keywords_added lists are not shared between instances."""
    job = Job(
        job_id="a",
        title="T",
        company="C",
        location="L",
        url="https://example.com/a",
        description="D",
    )
    r1 = TailoredResult(job=job, preview_resume_id="p1")
    r2 = TailoredResult(job=job, preview_resume_id="p2")
    r1.keywords_added.append("keyword")
    assert r2.keywords_added == []


def test_search_config_fields():
    config = SearchConfig(
        keywords=["ML Engineer", "AI Engineer"],
        location="Germany",
        experience_level=["MID_SENIOR_LEVEL", "ENTRY_LEVEL"],
        blacklist_companies=["SpamCorp"],
        max_jobs_per_run=20,
    )
    assert config.keywords == ["ML Engineer", "AI Engineer"]
    assert config.location == "Germany"
    assert config.experience_level == ["MID_SENIOR_LEVEL", "ENTRY_LEVEL"]
    assert config.blacklist_companies == ["SpamCorp"]
    assert config.max_jobs_per_run == 20


def test_search_config_empty_blacklist():
    config = SearchConfig(
        keywords=["Data Scientist"],
        location="UK",
        experience_level=["SENIOR_LEVEL"],
        blacklist_companies=[],
        max_jobs_per_run=10,
    )
    assert config.blacklist_companies == []
