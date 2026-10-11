import uuid

import pytest

from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.exceptions import UnauthorizedError


def test_password_hash_roundtrip():
    pw = "super-secret-1234"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h) is True
    assert verify_password("wrong", h) is False


def test_access_token_roundtrip():
    uid = str(uuid.uuid4())
    token = create_access_token(uid)
    payload = decode_token(token, expected_type="access")
    assert payload["sub"] == uid


def test_refresh_token_rejected_as_access():
    uid = str(uuid.uuid4())
    token = create_refresh_token(uid)
    with pytest.raises(UnauthorizedError):
        decode_token(token, expected_type="access")
