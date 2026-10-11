"""Auth routes â€” DI-based."""
from fastapi import APIRouter, Depends, Request, status

from app.auth.dependencies import get_current_user
from app.dependencies import ProvideUserService
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.schemas.user import (
    TokenPair,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserRead,
)
from app.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: UserCreate,
    svc: UserService = Depends(ProvideUserService),
) -> UserRead:
    return UserRead.model_validate(await svc.register(payload))


@router.post("/login", response_model=TokenPair)
@limiter.limit("20/minute")
async def login(
    request: Request,
    payload: UserLogin,
    svc: UserService = Depends(ProvideUserService),
) -> TokenPair:
    user = await svc.authenticate(payload.email, payload.password)
    return svc.issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    payload: TokenRefresh,
    svc: UserService = Depends(ProvideUserService),
) -> TokenPair:
    return await svc.refresh_tokens(payload.refresh_token)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(user)
