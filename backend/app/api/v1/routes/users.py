"""User profile + preferences + recommendations â€” DI-based."""
from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.dependencies import ProvideMemoryService, ProvideUserService, ProvideVideoService
from app.models.user import User
from app.schemas.user import UserPreferenceRead, UserPreferenceUpdate
from app.services.memory_service import MemoryService
from app.services.user_service import UserService
from app.services.video_service import VideoService

router = APIRouter()


@router.get("/preferences", response_model=UserPreferenceRead)
async def get_preferences(
    user: User = Depends(get_current_user),
    svc: UserService = Depends(ProvideUserService),
) -> UserPreferenceRead:
    return UserPreferenceRead.model_validate(await svc.get_preferences(user.id))


@router.patch("/preferences", response_model=UserPreferenceRead)
async def update_preferences(
    payload: UserPreferenceUpdate,
    user: User = Depends(get_current_user),
    svc: UserService = Depends(ProvideUserService),
) -> UserPreferenceRead:
    patch = payload.model_dump(exclude_unset=True)
    pref = await svc.update_preferences(user.id, patch)
    return UserPreferenceRead.model_validate(pref)


@router.get("/memory")
async def get_memory(
    user: User = Depends(get_current_user),
    svc: UserService = Depends(ProvideUserService),
) -> dict:
    pref = await svc.get_preferences(user.id)
    return {
        "facts": pref.memory_facts,
        "notes": pref.notes,
        "language": pref.language,
        "response_style": pref.preferred_response_style,
    }


@router.get("/recommendations")
async def recommendations(
    user: User = Depends(get_current_user),
    videos: VideoService = Depends(ProvideVideoService),
    memory: MemoryService = Depends(ProvideMemoryService),
) -> dict:
    recent = await videos.list_for_user(user.id)
    profile = await memory.get_user_profile(user.id)
    return {
        "recent_videos": [{"id": str(v.id), "title": v.title} for v in recent[:5]],
        "topics_of_interest": list(profile.keys())[:10],
    }
