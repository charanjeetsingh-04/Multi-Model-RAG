"""Verify the RFC 7807 error envelope shape from AppError."""
from __future__ import annotations

from app.core.errors import ErrorCode, spec_for
from app.core.exceptions import AppError, ConflictError, NotFoundError


def test_app_error_defaults_from_registry():
    e = AppError(ErrorCode.NOT_FOUND)
    spec = spec_for(ErrorCode.NOT_FOUND)
    assert e.status_code == spec.status
    assert e.title == spec.title
    assert e.message == spec.default_message


def test_app_error_custom_message():
    e = NotFoundError(message="Video missing")
    assert e.message == "Video missing"
    assert e.code is ErrorCode.NOT_FOUND


def test_conflict_status():
    e = ConflictError(message="dup")
    assert e.status_code == 409
