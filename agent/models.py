from dataclasses import dataclass, field


@dataclass
class Job:
    job_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    salary: str | None = None
    posted_at: str | None = None


@dataclass
class TailoredResult:
    job: Job
    preview_resume_id: str
    keywords_added: list[str] = field(default_factory=list)
    confirm_payload: dict = field(default_factory=dict)


@dataclass
class SearchConfig:
    keywords: list[str]
    location: str
    experience_level: list[str]
    blacklist_companies: list[str]
    max_jobs_per_run: int
