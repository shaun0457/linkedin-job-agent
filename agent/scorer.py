"""AI-powered job quality scoring using Gemini — labels jobs, never filters."""
import json
import logging
from dataclasses import dataclass, field

import httpx

from agent.models import Job

logger = logging.getLogger(__name__)

DEFAULT_SCORE = 5

SCORING_PROMPT_TEMPLATE = """\
You are a job quality evaluator for an AI/ML engineer with dual M.Sc. degrees \
(Computational Engineering + Mechanical Engineering) from TU Darmstadt. \
Experience: LLM-based multi-agent systems, PyTorch, predictive maintenance, sensor fusion.

Score each job 1-10 based on:
- **Company tier** (3pts): global brand, unicorn, or well-funded startup scores high
- **Salary/compensation** (2pts): known high-paying companies or roles score high
- **Role-background fit** (3pts): how well the job matches the candidate's AI/ML + mechanical background
- **Growth potential** (2pts): career advancement, learning opportunities, industry impact

Return ONLY a JSON array, no markdown, no explanation:
[{{"job_id": "...", "score": N, "reason": "one-line reason"}}]

Jobs to score:
{jobs_block}
"""


def match_tier(score: int) -> tuple[str, str]:
    """Return (icon, label) for a numeric score."""
    if score >= 7:
        return ("🟢", "強匹配")
    if score >= 4:
        return ("🟡", "匹配")
    return ("🔴", "弱匹配")


@dataclass
class ScoredJob:
    job: Job
    score: int
    reason: str = ""

    @property
    def tier(self) -> tuple[str, str]:
        return match_tier(self.score)


def _build_scoring_prompt(jobs: list[Job]) -> str:
    """Build the scoring prompt with job details."""
    lines = []
    for job in jobs:
        desc_preview = job.description[:200] if job.description else ""
        lines.append(
            f"- job_id: {job.job_id}\n"
            f"  title: {job.title}\n"
            f"  company: {job.company}\n"
            f"  location: {job.location}\n"
            f"  salary: {job.salary or 'not listed'}\n"
            f"  description: {desc_preview}"
        )
    jobs_block = "\n".join(lines)
    return SCORING_PROMPT_TEMPLATE.format(jobs_block=jobs_block)


async def _call_llm(prompt: str, api_key: str) -> str:
    """Call Gemini API for scoring."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.5-flash:generateContent?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        resp.raise_for_status()
        data = resp.json()
        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )


async def score_jobs(
    jobs: list[Job],
    api_key: str,
) -> list[ScoredJob]:
    """Score jobs using AI. Returns ALL jobs with scores, sorted high→low.

    Never filters — labels only. If LLM fails, all jobs get DEFAULT_SCORE.
    """
    if not jobs:
        return []

    try:
        prompt = _build_scoring_prompt(jobs)
        raw = await _call_llm(prompt, api_key)
        scores = _parse_scores(raw)
    except Exception:
        logger.warning("AI scoring failed, passing all jobs through", exc_info=True)
        return [
            ScoredJob(job=job, score=DEFAULT_SCORE, reason="Scoring failed — included by default")
            for job in jobs
        ]

    # Map scores to jobs
    score_map: dict[str, dict] = {s["job_id"]: s for s in scores}
    result = []
    for job in jobs:
        if job.job_id in score_map:
            entry = score_map[job.job_id]
            scored = ScoredJob(
                job=job,
                score=entry.get("score", DEFAULT_SCORE),
                reason=entry.get("reason", ""),
            )
        else:
            scored = ScoredJob(
                job=job, score=DEFAULT_SCORE,
                reason="Not scored by AI — included by default",
            )
        result.append(scored)

    result.sort(key=lambda s: s.score, reverse=True)

    logger.info(
        "Scored %d jobs: %s",
        len(jobs),
        ", ".join(f"{s.job.company}={s.score}" for s in result),
    )
    return result


def _parse_scores(raw: str) -> list[dict]:
    """Parse JSON array from LLM response, stripping markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    return json.loads(text)
