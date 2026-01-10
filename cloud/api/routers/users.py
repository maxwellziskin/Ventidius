"""
Ziskin Field Systems - Users Router

User management and camera permission endpoints.
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from sqlalchemy import select, delete
from typing import List
from uuid import UUID
import structlog

from dependencies import DBSession, CurrentUser, AdminUser
from models.user import User, UserCameraAccess
from models.camera import Camera
from schemas.user import UserUpdate, UserResponse, UserInvite, CameraPermission
from services.alerts import send_invite_email
from config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=List[UserResponse])
async def list_users(
    user: AdminUser,
    db: DBSession
):
    """
    List all users. Admin only.
    """
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return [UserResponse(**u.to_dict()) for u in users]


@router.post("/invite")
async def invite_user(
    invite_data: UserInvite,
    user: AdminUser,
    background_tasks: BackgroundTasks,
    db: DBSession
):
    """
    Send an invitation to a new user. Admin only.
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == invite_data.email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Generate invitation link (Clerk handles actual invitation)
    # Here we just prepare the invitation and send email
    invite_url = f"{settings.API_BASE_URL}/invite?email={invite_data.email}"

    # Send invitation email in background
    background_tasks.add_task(
        send_invite_email,
        invite_data.email,
        invite_url,
        user.email
    )

    logger.info("User invitation sent", email=invite_data.email, invited_by=user.email)

    return {
        "status": "ok",
        "message": f"Invitation sent to {invite_data.email}",
        "invite_url": invite_url
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: CurrentUser,
    db: DBSession
):
    """
    Get user details.
    """
    # Users can view their own profile, admins can view any
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(**user.to_dict())


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    admin: AdminUser,
    db: DBSession
):
    """
    Update user details. Admin only.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user_data.role is not None:
        user.role = user_data.role
    if user_data.client_id is not None:
        user.client_id = user_data.client_id
    if user_data.session_limit is not None:
        user.session_limit = user_data.session_limit

    await db.commit()
    await db.refresh(user)

    logger.info("User updated", user_id=str(user_id))

    return UserResponse(**user.to_dict())


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    admin: AdminUser,
    db: DBSession
):
    """
    Delete a user. Admin only.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent self-deletion
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db.delete(user)
    await db.commit()

    logger.info("User deleted", user_id=str(user_id))


@router.get("/{user_id}/cameras", response_model=List[CameraPermission])
async def get_user_cameras(
    user_id: UUID,
    admin: AdminUser,
    db: DBSession
):
    """
    Get camera permissions for a user. Admin only.
    """
    result = await db.execute(
        select(UserCameraAccess).where(UserCameraAccess.user_id == user_id)
    )
    permissions = result.scalars().all()

    return [
        CameraPermission(
            camera_id=p.camera_id,
            can_view=p.can_view,
            can_ptz=p.can_ptz
        )
        for p in permissions
    ]


@router.put("/{user_id}/cameras")
async def update_user_cameras(
    user_id: UUID,
    permissions: List[CameraPermission],
    admin: AdminUser,
    db: DBSession
):
    """
    Update camera permissions for a user. Admin only.
    """
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify all cameras exist
    camera_ids = [p.camera_id for p in permissions]
    result = await db.execute(select(Camera).where(Camera.id.in_(camera_ids)))
    cameras = result.scalars().all()

    if len(cameras) != len(camera_ids):
        raise HTTPException(status_code=400, detail="One or more cameras not found")

    # Remove existing permissions
    await db.execute(
        delete(UserCameraAccess).where(UserCameraAccess.user_id == user_id)
    )

    # Add new permissions
    for perm in permissions:
        access = UserCameraAccess(
            user_id=user_id,
            camera_id=perm.camera_id,
            can_view=perm.can_view,
            can_ptz=perm.can_ptz
        )
        db.add(access)

    await db.commit()

    logger.info(
        "User camera permissions updated",
        user_id=str(user_id),
        camera_count=len(permissions)
    )

    return {"status": "ok", "updated": len(permissions)}
