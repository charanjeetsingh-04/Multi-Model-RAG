"""Unit tests for UserService — repository fakes only, no DB."""
from __future__ import annotations

import pytest

from app.core.exceptions import ConflictError, UnauthorizedError
from app.schemas.user import UserCreate
from app.services.user_service import UserService
from tests.fakes import FakeUserPreferenceRepository, FakeUserRepository


@pytest.fixture
def svc():
    return UserService(FakeUserRepository(), FakeUserPreferenceRepository())


@pytest.mark.asyncio
async def test_register_creates_user(svc: UserService):
    user = await svc.register(
        UserCreate(email="a@b.com", username="alice", password="password123", full_name="A")
    )
    assert user.email == "a@b.com"
    assert user.username == "alice"
    assert user.hashed_password != "password123"


@pytest.mark.asyncio
async def test_register_duplicate_email(svc: UserService):
    payload = UserCreate(email="a@b.com", username="alice", password="password123")
    await svc.register(payload)
    with pytest.raises(ConflictError):
        await svc.register(UserCreate(email="a@b.com", username="alice2", password="password123"))


@pytest.mark.asyncio
async def test_authenticate_wrong_password(svc: UserService):
    await svc.register(UserCreate(email="a@b.com", username="alice", password="password123"))
    with pytest.raises(UnauthorizedError):
        await svc.authenticate("a@b.com", "wrong")


@pytest.mark.asyncio
async def test_authenticate_success_issues_tokens(svc: UserService):
    user = await svc.register(UserCreate(email="a@b.com", username="alice", password="password123"))
    pair = svc.issue_tokens(user)
    assert pair.access_token and pair.refresh_token
    assert pair.expires_in > 0
