"""
Ziskin Field Systems - Admin Router

Administrative endpoints for system management.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import structlog

from dependencies import DBSession, AdminUser, EdgeDevice
from models.client import Client
from models.site import Site
from models.camera import Camera
from models.user import User
from models.audit import AuditLog
from schemas.client import ClientCreate, ClientUpdate, ClientResponse
from schemas.audit import AuditLogResponse
from schemas.site import SiteHealth

router = APIRouter()
logger = structlog.get_logger(__name__)


# Client management

@router.get("/clients", response_model=List[ClientResponse])
async def list_clients(
    user: AdminUser,
    db: DBSession
):
    """
    List all clients. Admin only.
    """
    result = await db.execute(select(Client).order_by(Client.name))
    clients = result.scalars().all()

    return [ClientResponse(**c.to_dict()) for c in clients]


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    user: AdminUser,
    db: DBSession
):
    """
    Create a new client. Admin only.
    """
    client = Client(
        name=client_data.name,
        contact_email=client_data.contact_email
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)

    logger.info("Client created", client_id=str(client.id), name=client.name)

    return ClientResponse(**client.to_dict())


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Get client details. Admin only.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return ClientResponse(**client.to_dict())


@router.put("/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    user: AdminUser,
    db: DBSession
):
    """
    Update a client. Admin only.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if client_data.name is not None:
        client.name = client_data.name
    if client_data.contact_email is not None:
        client.contact_email = client_data.contact_email

    await db.commit()
    await db.refresh(client)

    logger.info("Client updated", client_id=str(client_id))

    return ClientResponse(**client.to_dict())


@router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Delete a client. Admin only.
    """
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    await db.delete(client)
    await db.commit()

    logger.info("Client deleted", client_id=str(client_id))


# Site health

@router.get("/sites/{site_id}/health")
async def get_site_health(
    site_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Get edge device health for a site. Admin only.
    """
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Get camera statuses
    result = await db.execute(
        select(Camera).where(Camera.site_id == site_id)
    )
    cameras = result.scalars().all()

    return {
        "site_id": str(site.id),
        "site_name": site.name,
        "status": site.status,
        "last_seen": site.last_seen.isoformat() if site.last_seen else None,
        "cameras": [
            {
                "id": str(c.id),
                "name": c.name,
                "status": c.status,
                "last_seen": c.last_seen.isoformat() if c.last_seen else None
            }
            for c in cameras
        ]
    }


@router.post("/sites/{site_id}/reboot")
async def reboot_site(
    site_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Request remote reboot of edge device. Admin only.
    """
    from routers.ptz import edge_connections

    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    site_id_str = str(site_id)
    if site_id_str not in edge_connections:
        raise HTTPException(status_code=503, detail="Edge device not connected")

    try:
        ws = edge_connections[site_id_str]
        await ws.send_json({"command": "reboot"})
    except Exception as e:
        logger.error("Failed to send reboot command", error=str(e))
        raise HTTPException(status_code=503, detail="Failed to send command")

    logger.info("Reboot command sent", site_id=str(site_id), admin=user.email)

    return {"status": "ok", "message": "Reboot command sent"}


# Edge device health reporting

@router.post("/edge/health")
async def report_health(
    health_data: SiteHealth,
    edge: EdgeDevice,
    db: DBSession
):
    """
    Receive health report from edge device.
    """
    site_id = UUID(edge["site_id"])

    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Update site status
    site.status = "online"
    site.last_seen = datetime.utcnow()

    # Update camera statuses
    app_health = health_data.application
    camera_statuses = app_health.get("cameras", [])

    for cam_status in camera_statuses:
        cam_id = cam_status.get("camera_id")
        if cam_id:
            result = await db.execute(
                select(Camera).where(Camera.id == UUID(cam_id))
            )
            camera = result.scalar_one_or_none()
            if camera:
                camera.update_status(cam_status.get("online", False))

    await db.commit()

    return {"status": "ok"}


@router.post("/edge/alert")
async def receive_alert(
    alert_data: dict,
    edge: EdgeDevice,
    db: DBSession
):
    """
    Receive alert from edge device.
    """
    from services.alerts import send_alert_email

    site_id = edge["site_id"]
    site_name = edge["site_name"]

    alert_type = alert_data.get("type")
    message = alert_data.get("message")
    details = alert_data.get("details", {})

    logger.warning(
        "Alert from edge device",
        site_id=site_id,
        alert_type=alert_type,
        message=message
    )

    # Send alert email
    await send_alert_email(site_name, alert_type, message, details)

    return {"status": "ok"}


# Audit log

@router.get("/audit", response_model=List[AuditLogResponse])
async def list_audit_logs(
    user: AdminUser,
    db: DBSession,
    user_id: Optional[UUID] = None,
    camera_id: Optional[UUID] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get audit logs. Admin only.
    """
    query = select(AuditLog)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if camera_id:
        query = query.where(AuditLog.camera_id == camera_id)
    if action:
        query = query.where(AuditLog.action == action)

    query = query.order_by(AuditLog.timestamp.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [AuditLogResponse(**log.to_dict()) for log in logs]


# Alert history (placeholder - would need an alerts table)

@router.get("/alerts")
async def list_alerts(
    user: AdminUser,
    db: DBSession,
    limit: int = 100
):
    """
    Get alert history. Admin only.
    """
    # This would query an alerts table
    # For now, return empty list
    return {"alerts": []}


# Dashboard statistics

@router.get("/stats")
async def get_stats(
    user: AdminUser,
    db: DBSession
):
    """
    Get system statistics for admin dashboard. Admin only.
    """
    # Count entities
    clients_count = await db.execute(select(func.count(Client.id)))
    sites_count = await db.execute(select(func.count(Site.id)))
    cameras_count = await db.execute(select(func.count(Camera.id)))
    users_count = await db.execute(select(func.count(User.id)))

    # Count online sites/cameras
    online_sites = await db.execute(
        select(func.count(Site.id)).where(Site.status == "online")
    )
    online_cameras = await db.execute(
        select(func.count(Camera.id)).where(Camera.status == "online")
    )

    return {
        "clients": clients_count.scalar(),
        "sites": {
            "total": sites_count.scalar(),
            "online": online_sites.scalar()
        },
        "cameras": {
            "total": cameras_count.scalar(),
            "online": online_cameras.scalar()
        },
        "users": users_count.scalar()
    }
