"""
Ziskin Field Systems - Cameras Router

CRUD operations for cameras and stream URL generation.
"""

from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import select
from typing import List
from uuid import UUID
from datetime import datetime, timedelta
import secrets
import hashlib
import structlog

from dependencies import DBSession, CurrentUser, AdminUser
from models.camera import Camera
from models.site import Site
from models.user import UserCameraAccess
from models.audit import AuditLog
from schemas.camera import CameraCreate, CameraUpdate, CameraResponse, CameraStreamUrl
from config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)


def generate_stream_token(camera_id: str, expires_at: datetime) -> str:
    """Generate a signed token for stream access."""
    data = f"{camera_id}:{expires_at.timestamp()}:{settings.SECRET_KEY}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


@router.get("", response_model=List[CameraResponse])
async def list_cameras(
    user: CurrentUser,
    db: DBSession
):
    """
    List cameras accessible to the current user.
    """
    if user.is_admin:
        result = await db.execute(select(Camera).order_by(Camera.name))
    else:
        # Get cameras user has access to
        result = await db.execute(
            select(Camera)
            .join(UserCameraAccess, Camera.id == UserCameraAccess.camera_id)
            .where(UserCameraAccess.user_id == user.id)
            .where(UserCameraAccess.can_view == True)
            .order_by(Camera.name)
        )

    cameras = result.scalars().all()
    return [CameraResponse(**c.to_dict()) for c in cameras]


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_data: CameraCreate,
    user: AdminUser,
    db: DBSession
):
    """
    Create a new camera. Admin only.
    """
    # Verify site exists
    result = await db.execute(select(Site).where(Site.id == camera_data.site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    camera = Camera(
        site_id=camera_data.site_id,
        name=camera_data.name,
        local_ip=camera_data.local_ip,
        rtsp_path=camera_data.rtsp_path,
        onvif_port=camera_data.onvif_port,
        onvif_user=camera_data.onvif_user,
        onvif_pass=camera_data.onvif_pass,
        is_ptz=camera_data.is_ptz
    )
    db.add(camera)
    await db.commit()
    await db.refresh(camera)

    logger.info("Camera created", camera_id=str(camera.id), name=camera.name)

    return CameraResponse(**camera.to_dict())


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: UUID,
    user: CurrentUser,
    db: DBSession
):
    """
    Get camera details.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Check access
    if not user.is_admin:
        access_result = await db.execute(
            select(UserCameraAccess)
            .where(UserCameraAccess.user_id == user.id)
            .where(UserCameraAccess.camera_id == camera_id)
            .where(UserCameraAccess.can_view == True)
        )
        if not access_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    return CameraResponse(**camera.to_dict())


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: UUID,
    camera_data: CameraUpdate,
    user: AdminUser,
    db: DBSession
):
    """
    Update a camera. Admin only.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if camera_data.name is not None:
        camera.name = camera_data.name
    if camera_data.local_ip is not None:
        camera.local_ip = camera_data.local_ip
    if camera_data.rtsp_path is not None:
        camera.rtsp_path = camera_data.rtsp_path
    if camera_data.onvif_port is not None:
        camera.onvif_port = camera_data.onvif_port
    if camera_data.onvif_user is not None:
        camera.onvif_user = camera_data.onvif_user
    if camera_data.onvif_pass is not None:
        camera.onvif_pass = camera_data.onvif_pass
    if camera_data.is_ptz is not None:
        camera.is_ptz = camera_data.is_ptz

    await db.commit()
    await db.refresh(camera)

    logger.info("Camera updated", camera_id=str(camera_id))

    return CameraResponse(**camera.to_dict())


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Delete a camera. Admin only.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    await db.delete(camera)
    await db.commit()

    logger.info("Camera deleted", camera_id=str(camera_id))


@router.get("/{camera_id}/stream", response_model=CameraStreamUrl)
async def get_stream_url(
    camera_id: UUID,
    user: CurrentUser,
    request: Request,
    db: DBSession
):
    """
    Get signed HLS stream URL for a camera.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Check access
    if not user.is_admin:
        access_result = await db.execute(
            select(UserCameraAccess)
            .where(UserCameraAccess.user_id == user.id)
            .where(UserCameraAccess.camera_id == camera_id)
            .where(UserCameraAccess.can_view == True)
        )
        if not access_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    # Generate stream URL with token
    expires_at = datetime.utcnow() + timedelta(seconds=settings.STREAM_TOKEN_EXPIRY)
    token = generate_stream_token(str(camera_id), expires_at)

    # Log stream access
    audit = AuditLog(
        user_id=user.id,
        camera_id=camera_id,
        action="stream_view",
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    await db.commit()

    # Build stream URL
    stream_url = f"{settings.API_BASE_URL}/stream/{camera_id}/index.m3u8?token={token}&expires={int(expires_at.timestamp())}"

    return CameraStreamUrl(
        camera_id=camera_id,
        hls_url=stream_url,
        expires_at=expires_at
    )
