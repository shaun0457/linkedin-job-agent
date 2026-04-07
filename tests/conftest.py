"""Shared pytest fixtures and setup."""
import pytest
from agent import db


@pytest.fixture(autouse=True)
def init_test_db():
    """Ensure DB tables exist before each test."""
    db.init_db()
