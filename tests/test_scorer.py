"""TDD tests for agent/scorer.py — AI job quality scoring with tier labels."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.models import Job
from agent.scorer import (
    score_jobs, _build_scoring_prompt, ScoredJob, match_tier, DEFAULT_SCORE,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_job(job_id: str = "j1", title: str = "ML Engineer",
              company: str = "NVIDIA", description: str = "Build ML pipelines") -> Job:
    return Job(
        job_id=job_id, title=title, company=company,
        location="Germany", url=f"https://linkedin.com/jobs/{job_id}",
        description=description,
    )


# ── match_tier ─────────────────────────────────────────────────────────────


def test_match_tier_strong():
    assert match_tier(7) == ("🟢", "強匹配")
    assert match_tier(10) == ("🟢", "強匹配")


def test_match_tier_medium():
    assert match_tier(4) == ("🟡", "匹配")
    assert match_tier(6) == ("🟡", "匹配")


def test_match_tier_weak():
    assert match_tier(1) == ("🔴", "弱匹配")
    assert match_tier(3) == ("🔴", "弱匹配")


# ── ScoredJob dataclass ─────────────────────────────────────────────────────


def test_scored_job_has_required_fields():
    job = _make_job()
    scored = ScoredJob(job=job, score=8, reason="Top AI company")
    assert scored.score == 8
    assert scored.reason == "Top AI company"
    assert scored.job is job


def test_scored_job_default_reason():
    scored = ScoredJob(job=_make_job(), score=5)
    assert scored.reason == ""


def test_scored_job_tier_property():
    scored = ScoredJob(job=_make_job(), score=9)
    icon, label = scored.tier
    assert icon == "🟢"
    assert label == "強匹配"


# ── _build_scoring_prompt ────────────────────────────────────────────────────


def test_build_scoring_prompt_contains_job_info():
    jobs = [_make_job(title="AI Engineer", company="Google")]
    prompt = _build_scoring_prompt(jobs)
    assert "AI Engineer" in prompt
    assert "Google" in prompt


def test_build_scoring_prompt_multiple_jobs():
    jobs = [_make_job(job_id="1", company="Google"), _make_job(job_id="2", company="TSMC")]
    prompt = _build_scoring_prompt(jobs)
    assert "Google" in prompt
    assert "TSMC" in prompt


def test_build_scoring_prompt_includes_scoring_criteria():
    prompt = _build_scoring_prompt([_make_job()])
    assert "company" in prompt.lower()
    assert "salary" in prompt.lower() or "compensation" in prompt.lower()


# ── score_jobs — returns ALL jobs (no filtering) ─────────────────────────────


@pytest.mark.asyncio
async def test_score_jobs_returns_all_jobs_scored():
    """score_jobs returns ALL jobs with scores, never filters."""
    jobs = [_make_job(job_id="1"), _make_job(job_id="2")]
    mock_response = json.dumps([
        {"job_id": "1", "score": 9, "reason": "Top GPU company"},
        {"job_id": "2", "score": 2, "reason": "Weak match"},
    ])

    with patch("agent.scorer._call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await score_jobs(jobs, api_key="fake-key")

    assert len(result) == 2  # both returned, none filtered


@pytest.mark.asyncio
async def test_score_jobs_sorted_by_score_descending():
    """Results are sorted high→low so strong matches come first."""
    jobs = [_make_job(job_id="1"), _make_job(job_id="2"), _make_job(job_id="3")]
    mock_response = json.dumps([
        {"job_id": "1", "score": 3, "reason": "Weak"},
        {"job_id": "2", "score": 9, "reason": "Great"},
        {"job_id": "3", "score": 6, "reason": "OK"},
    ])

    with patch("agent.scorer._call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await score_jobs(jobs, api_key="fake-key")

    assert [s.score for s in result] == [9, 6, 3]


@pytest.mark.asyncio
async def test_score_jobs_empty_input():
    result = await score_jobs([], api_key="fake-key")
    assert result == []


@pytest.mark.asyncio
async def test_score_jobs_llm_failure_returns_all_with_default_score():
    """If LLM fails, all jobs pass through with default score."""
    jobs = [_make_job(job_id="1"), _make_job(job_id="2")]

    with patch("agent.scorer._call_llm", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await score_jobs(jobs, api_key="fake-key")

    assert len(result) == 2
    for scored in result:
        assert scored.score == DEFAULT_SCORE
        assert "scoring failed" in scored.reason.lower()


@pytest.mark.asyncio
async def test_score_jobs_partial_response_handles_missing_jobs():
    """If LLM only scores some jobs, unscored jobs get default score."""
    jobs = [_make_job(job_id="1"), _make_job(job_id="2")]
    mock_response = json.dumps([
        {"job_id": "1", "score": 9, "reason": "Great"},
    ])

    with patch("agent.scorer._call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await score_jobs(jobs, api_key="fake-key")

    assert len(result) == 2
    scores_by_id = {s.job.job_id: s for s in result}
    assert scores_by_id["1"].score == 9
    assert scores_by_id["2"].score == DEFAULT_SCORE


@pytest.mark.asyncio
async def test_score_jobs_invalid_json_returns_all():
    """If LLM returns invalid JSON, all jobs pass through."""
    jobs = [_make_job()]

    with patch("agent.scorer._call_llm", new_callable=AsyncMock, return_value="not json"):
        result = await score_jobs(jobs, api_key="fake-key")

    assert len(result) == 1
    assert result[0].score == DEFAULT_SCORE


# ── _call_llm ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_llm_sends_request_and_returns_text():
    """_call_llm posts to Gemini API and extracts text from response."""
    from agent.scorer import _call_llm

    fake_response = {
        "candidates": [
            {"content": {"parts": [{"text": '[{"job_id":"1","score":8}]'}]}}
        ]
    }
    mock_response = MagicMock()
    mock_response.json.return_value = fake_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("agent.scorer.httpx.AsyncClient", return_value=mock_client):
        result = await _call_llm("test prompt", "fake-key")

    assert result == '[{"job_id":"1","score":8}]'
    mock_client.post.assert_called_once()
    call_url = mock_client.post.call_args[0][0]
    assert "gemini-2.5-flash" in call_url
    assert "fake-key" in call_url


# ── _parse_scores ───────────────────────────────────────────────────────────


def test_parse_scores_strips_markdown_fences():
    """_parse_scores removes ```json fences from LLM response."""
    from agent.scorer import _parse_scores

    raw = '```json\n[{"job_id": "1", "score": 7, "reason": "ok"}]\n```'
    result = _parse_scores(raw)
    assert len(result) == 1
    assert result[0]["score"] == 7


def test_parse_scores_plain_json():
    """_parse_scores handles plain JSON without fences."""
    from agent.scorer import _parse_scores

    raw = '[{"job_id": "1", "score": 9}]'
    result = _parse_scores(raw)
    assert result[0]["score"] == 9
