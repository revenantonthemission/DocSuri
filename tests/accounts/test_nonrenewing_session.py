from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from backend.modules.accounts.models import SessionExpiredException, SessionRecord
from backend.modules.accounts.services.session_manager import SessionManager


@pytest.mark.asyncio
async def test_background_inspection_does_not_extend_session():
    now = datetime.now(UTC)
    user_id = "00000000-0000-4000-8000-000000000001"
    session = SessionRecord(
        handle="opaque",
        user_id=user_id,
        created_at=now,
        last_active_at=now - timedelta(minutes=30),
        expires_at=now + timedelta(days=1),
        role="USER",
        mfa_verified=False,
    )
    repository = AsyncMock()
    repository.get.return_value = session
    before = session.last_active_at
    principal = await SessionManager(repository).inspect("opaque")
    assert principal.user_id == user_id
    assert session.last_active_at == before
    repository.save.assert_not_awaited()
    repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_expired_inspection_denies_without_mutation():
    now = datetime.now(UTC)
    repository = AsyncMock()
    repository.get.return_value = SessionRecord(
        handle="opaque",
        user_id="user-1",
        created_at=now - timedelta(days=2),
        last_active_at=now,
        expires_at=now - timedelta(seconds=1),
        role="USER",
        mfa_verified=False,
    )
    with pytest.raises(SessionExpiredException):
        await SessionManager(repository).inspect("opaque")
    repository.save.assert_not_awaited()
    repository.delete.assert_not_awaited()
