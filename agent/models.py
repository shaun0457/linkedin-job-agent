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
    preview_data: dict          # full ImproveResumeData from RM API
    rm_job_id: str              # RM's job_id (used for confirm)
    master_resume_id: str       # master resume used for tailoring
    keywords_added: list[str] = field(default_factory=list)


@dataclass
class SearchConfig:
    keywords: list[str]
    location: str
    experience_level: list[str]
    blacklist_companies: list[str]
    max_jobs_per_run: int
