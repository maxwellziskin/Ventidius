"""
Ziskin Field Systems - PTZ Control Router

PTZ (Pan-Tilt-Zoom) camera control endpoints.
"""

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from typing import List, Dict
from uuid import UUID
import asyncio
import json
import structlog

from dependencies import DBSession, CurrentUser, AdminUser
from models.camera import Camera, PTZPreset
from models.site import Site
from models.user import UserCameraAccess
from models.audit import AuditLog
from schemas.ptz import PTZCommand, PTZPresetCreate, PTZPresetResponse

router = APIRouter()
logger = structlog.get_logger(__name__)

# Store for active WebSocket connections to edge devices
edge_connections: Dict[str, WebSocket] = {}


@router.post("/cameras/{camera_id}/ptz")
async def send_ptz_command(
    camera_id: UUID,
    command: PTZCommand,
    user: CurrentUser,
    request: Request,
    db: DBSession
):
    """
    Send a PTZ command to a camera.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if not camera.is_ptz:
        raise HTTPException(status_code=400, detail="Camera does not support PTZ")

    # Check PTZ permission
    if not user.is_admin:
        access_result = await db.execute(
            select(UserCameraAccess)
            .where(UserCameraAccess.user_id == user.id)
            .where(UserCameraAccess.camera_id == camera_id)
            .where(UserCameraAccess.can_ptz == True)
        )
        if not access_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="PTZ access denied")

    # Get site to find edge device
    result = await db.execute(select(Site).where(Site.id == camera.site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Send command to edge device
    site_id = str(site.id)
    if site_id not in edge_connections:
        raise HTTPException(status_code=503, detail="Edge device not connected")

    try:
        ws = edge_connections[site_id]
        await ws.send_json({
            "camera_id": str(camera_id),
            "action": command.action,
            "pan": command.pan,
            "tilt": command.tilt,
            "zoom": command.zoom,
            "preset_id": command.preset_id
        })
    except Exception as e:
        logger.error("Failed to send PTZ command", error=str(e))
        raise HTTPException(status_code=503, detail="Failed to send command to edge device")

    # Log PTZ action
    audit = AuditLog(
        user_id=user.id,
        camera_id=camera_id,
        action=f"ptz_{command.action}",
        details={
            "pan": command.pan,
            "tilt": command.tilt,
            "zoom": command.zoom,
            "preset_id": command.preset_id
        },
        ip_address=request.client.host if request.client else None
    )
    db.add(audit)
    await db.commit()

    return {"status": "ok", "command": command.action}


@router.get("/cameras/{camera_id}/presets", response_model=List[PTZPresetResponse])
async def list_presets(
    camera_id: UUID,
    user: CurrentUser,
    db: DBSession
):
    """
    List PTZ presets for a camera.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if not camera.is_ptz:
        raise HTTPException(status_code=400, detail="Camera does not support PTZ")

    # Check access
    if not user.is_admin:
        access_result = await db.execute(
            select(UserCameraAccess)
            .where(UserCameraAccess.user_id == user.id)
            .where(UserCameraAccess.camera_id == camera_id)
        )
        if not access_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    result = await db.execute(
        select(PTZPreset).where(PTZPreset.camera_id == camera_id).order_by(PTZPreset.name)
    )
    presets = result.scalars().all()

    return [PTZPresetResponse(**p.to_dict()) for p in presets]


@router.post("/cameras/{camera_id}/presets", response_model=PTZPresetResponse)
async def create_preset(
    camera_id: UUID,
    preset_data: PTZPresetCreate,
    user: AdminUser,
    db: DBSession
):
    """
    Save current camera position as a preset. Admin only.
    """
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    if not camera.is_ptz:
        raise HTTPException(status_code=400, detail="Camera does not support PTZ")

    # Get site to find edge device
    result = await db.execute(select(Site).where(Site.id == camera.site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Request current position from edge device and save preset
    # For now, create preset with null position (edge device will handle actual preset)
    preset = PTZPreset(
        camera_id=camera_id,
        name=preset_data.name
    )
    db.add(preset)
    await db.commit()
    await db.refresh(preset)

    logger.info("PTZ preset created", camera_id=str(camera_id), preset_name=preset_data.name)

    return PTZPresetResponse(**preset.to_dict())


@router.delete("/cameras/{camera_id}/presets/{preset_id}")
async def delete_preset(
    camera_id: UUID,
    preset_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Delete a PTZ preset. Admin only.
    """
    result = await db.execute(
        select(PTZPreset)
        .where(PTZPreset.id == preset_id)
        .where(PTZPreset.camera_id == camera_id)
    )
    preset = result.scalar_one_or_none()

    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    db.delete(preset)
    await db.commit()

    logger.info("PTZ preset deleted", preset_id=str(preset_id))

    return {"status": "ok"}


@router.websocket("/ws/edge/{site_id}")
async def edge_websocket(
    websocket: WebSocket,
    site_id: str,
    db: DBSession
):
    """
    WebSocket endpoint for edge device PTZ command reception.
    """
    await websocket.accept()

    # Verify site exists and get API key from query params
    api_key = websocket.query_params.get("api_key")

    result = await db.execute(
        select(Site).where(Site.id == site_id).where(Site.api_key == api_key)
    )
    site = result.scalar_one_or_none()

    if not site:
        await websocket.close(code=4001, reason="Invalid site or API key")
        return

    # Register connection
    edge_connections[site_id] = websocket
    logger.info("Edge device connected", site_id=site_id)

    try:
        while True:
            # Keep connection alive, receive heartbeats
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        logger.info("Edge device disconnected", site_id=site_id)
    finally:
        if site_id in edge_connections:
            del edge_connections[site_id]
