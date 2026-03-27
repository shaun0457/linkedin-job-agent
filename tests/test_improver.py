"""Tests for agent/improver.py — written BEFORE implementation (TDD)."""
import json
import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from agent.models import Job
from agent import improver


# ── fixtures ───────────────────────────────────────────────────────────────

SAMPLE_JOB = Job(
    job_id="test-001",
    title="ML Engineer",
    company="DeepMind",
    location="London",
    url="https://linkedin.com/jobs/test-001",
    description="We need a PyTorch expert.",
)

MASTER_RESUME_ID = "resume-master-abc"
RM_JOB_ID = "rm-job-xyz"
REQUEST_ID = "req-preview-123"

# Realistic API responses based on actual RM schema
JOB_UPLOAD_RESPONSE = {
    "message": "data successfully processed",
    "job_id": [RM_JOB_ID],
    "request": {"job_descriptions": ["We need a PyTorch expert."], "resume_id": None},
}

PREVIEW_RESPONSE = {
    "request_id": REQUEST_ID,
    "data": {
        "request_id": REQUEST_ID,
        "resume_id": None,  # null for preview
        "job_id": RM_JOB_ID,
        "resume_preview": {"personalInfo": {"name": "Cheng Ting"}},
        "improvements": [
            {"suggestion": "Added PyTorch keyword", "lineNumber": 5},
            {"suggestion": "Improved summary", "lineNumber": 1},
        ],
        "markdownOriginal": "# Original",
        "markdownImproved": "# Improved",
        "cover_letter": None,
        "outreach_message": None,
        "diff_summary": None,
        "detailed_changes": None,
        "warnings": [],
        "refinement_attempted": False,
        "refinement_successful": False,
    },
}

CONFIRM_RESPONSE = {
    "request_id": "req-confirm-456",
    "data": {
        "request_id": "req-confirm-456",
        "resume_id": "resume-confirmed-789",  # populated after confirm
        "job_id": RM_JOB_ID,
        "resume_preview": {"personalInfo": {"name": "Cheng Ting"}},
        "improvements": [],
        "warnings": [],
        "refinement_attempted": False,
        "refinement_successful": False,
    },
}

LIST_RESUMES_RESPONSE = {
    "request_id": "req-list-001",
    "data": [
        {
            "resume_id": MASTER_RESUME_ID,
            "filename": "master.pdf",
            "is_master": True,
            "processing_status": "completed",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        },
        {
            "resume_id": "resume-other",
            "filename": "other.pdf",
            "is_master": False,
            "processing_status": "completed",
            "created_at": "2026-01-02T00:00:00",
            "updated_at": "2026-01-02T00:00:00",
        },
    ],
}


# ── _upload_job ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_job_sends_correct_body():
    """_upload_job must POST job_descriptions as a list, not content/title."""
    captured = {}

    async def mock_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = JOB_UPLOAD_RESPONSE
        return resp

    async with httpx.AsyncClient() as client:
        client.post = mock_post
        result = await improver._upload_job(client, SAMPLE_JOB)

    assert result == RM_JOB_ID
    assert captured["json"]["job_descriptions"] == [SAMPLE_JOB.description]
    assert "content" not in captured["json"]
    assert "title" not in captured["json"]


@pytest.mark.asyncio
async def test_upload_job_returns_first_job_id():
    """_upload_job returns the first element of job_id list."""
    async def mock_post(url, json=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"message": "ok", "job_id": ["id-1", "id-2"], "request": {}}
        return resp

    async with httpx.AsyncClient() as client:
        client.post = mock_post
        result = await improver._upload_job(client, SAMPLE_JOB)

    assert result == "id-1"


@pytest.mark.asyncio
async def test_upload_job_returns_none_on_http_error():
    async def mock_post(url, json=None, **kwargs):
        raise httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())

    async with httpx.AsyncClient() as client:
        client.post = mock_post
        result = await improver._upload_job(client, SAMPLE_JOB)

    assert result is None


# ── _improve_preview ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_improve_preview_returns_full_data():
    """_improve_preview must return the full data dict, not just an ID."""
    async def mock_post(url, json=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = PREVIEW_RESPONSE
        return resp

    async with httpx.AsyncClient() as client:
        client.post = mock_post
        result = await improver._improve_preview(client, MASTER_RESUME_ID, RM_JOB_ID)

    assert result is not None
    assert result["request_id"] == REQUEST_ID
    assert result["resume_id"] is None  # null for preview
    assert result["job_id"] == RM_JOB_ID
    assert "resume_preview" in result
    assert "improvements" in result


@pytest.mark.asyncio
async def test_improve_preview_sends_correct_body():
    """_improve_preview must send resume_id and job_id."""
    captured = {}

    async def mock_post(url, json=None, **kwargs):
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = PREVIEW_RESPONSE
        return resp

    async with httpx.AsyncClient() as client:
        client.post = mock_post
        await improver._improve_preview(client, MASTER_RESUME_ID, RM_JOB_ID)

    assert captured["json"]["resume_id"] == MASTER_RESUME_ID
    assert captured["json"]["job_id"] == RM_JOB_ID


@pytest.mark.asyncio
async def test_improve_preview_returns_none_on_error():
    async def mock_post(url, json=None, **kwargs):
        raise httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())

    async with httpx.AsyncClient() as client:
        client.post = mock_post
        result = await improver._improve_preview(client, MASTER_RESUME_ID, RM_JOB_ID)

    assert result is None


# ── get_master_resume_id ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_master_resume_id_returns_correct_id():
    """Must extract resume_id from data array, not id field."""
    async def mock_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = LIST_RESUMES_RESPONSE
        return resp

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get
        MockClient.return_value = mock_client

        result = await improver.get_master_resume_id("http://localhost:8000")

    assert result == MASTER_RESUME_ID


@pytest.mark.asyncio
async def test_get_master_resume_id_returns_none_when_no_master():
    """Returns None when no master resume in list."""
    no_master_response = {
        "request_id": "r1",
        "data": [
            {"resume_id": "r1", "is_master": False, "processing_status": "completed",
             "created_at": "", "updated_at": ""}
        ],
    }

    async def mock_get(url, params=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = no_master_response
        return resp

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = mock_get
        MockClient.return_value = mock_client

        result = await improver.get_master_resume_id("http://localhost:8000")

    assert result is None


# ── confirm_resume ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_resume_sends_full_payload():
    """confirm_resume must send resume_id, job_id, improved_data, improvements."""
    captured = {}
    preview_data = PREVIEW_RESPONSE["data"]

    async def mock_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = CONFIRM_RESPONSE
        return resp

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        MockClient.return_value = mock_client

        result = await improver.confirm_resume(
            "http://localhost:8000",
            master_resume_id=MASTER_RESUME_ID,
            preview_data=preview_data,
        )

    assert result == "resume-confirmed-789"
    assert captured["json"]["resume_id"] == MASTER_RESUME_ID
    assert captured["json"]["job_id"] == RM_JOB_ID
    assert "improved_data" in captured["json"]
    assert "improvements" in captured["json"]


@pytest.mark.asyncio
async def test_confirm_resume_returns_none_on_failure():
    preview_data = PREVIEW_RESPONSE["data"]

    async def mock_post(url, json=None, **kwargs):
        raise httpx.HTTPStatusError("400", request=MagicMock(), response=MagicMock())

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        MockClient.return_value = mock_client

        result = await improver.confirm_resume(
            "http://localhost:8000",
            master_resume_id=MASTER_RESUME_ID,
            preview_data=preview_data,
        )

    assert result is None


# ── tailor_resume (integration) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tailor_resume_returns_tailored_result_with_preview_data():
    """tailor_resume must store full preview_data in TailoredResult."""
    async def mock_post(url, json=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "jobs/upload" in url:
            resp.json.return_value = JOB_UPLOAD_RESPONSE
        else:
            resp.json.return_value = PREVIEW_RESPONSE
        return resp

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = mock_post
        MockClient.return_value = mock_client

        result = await improver.tailor_resume(
            "http://localhost:8000", MASTER_RESUME_ID, SAMPLE_JOB
        )

    assert result is not None
    assert result.job == SAMPLE_JOB
    assert result.preview_data is not None
    assert result.preview_data["request_id"] == REQUEST_ID
    assert result.rm_job_id == RM_JOB_ID
    assert result.master_resume_id == MASTER_RESUME_ID
