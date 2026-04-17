"""Shared pytest fixtures: ensure DB schema exists before any test runs."""
import pytest
import agent.db as db


@pytest.fixture(autouse=True, scope="session")
def init_test_db():
    db.init_db()
