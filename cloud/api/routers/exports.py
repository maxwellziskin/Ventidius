"""
Ziskin Field Systems - Exports Router

Video clip export request management.
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from sqlalchemy import select
from typing import List
from uuid import UUID
from datetime import datetime
import os
import structlog

from dependencies import DBSession, CurrentUser, AdminUser, EdgeDevice
from models.audit import ExportRequest
from models.camera import Camera
from models.user import UserCameraAccess
from schemas.export import ExportCreate, ExportResponse, ExportStatusUpdate
from config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=List[ExportResponse])
async def list_exports(
    user: CurrentUser,
    db: DBSession,
    status_filter: str = None
):
    """
    List export requests.
    """
    query = select(ExportRequest)

    if not user.is_admin:
        query = query.where(ExportRequest.requested_by == user.id)

    if status_filter:
        query = query.where(ExportRequest.status == status_filter)

    query = query.order_by(ExportRequest.created_at.desc())

    result = await db.execute(query)
    exports = result.scalars().all()

    return [ExportResponse(**e.to_dict()) for e in exports]


@router.post("", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
async def create_export(
    export_data: ExportCreate,
    user: AdminUser,
    db: DBSession
):
    """
    Create a new export request. Admin only.
    """
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == export_data.camera_id))
    camera = result.scalar_one_or_none()

    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Check pending request limit (10 per user)
    result = await db.execute(
        select(ExportRequest)
        .where(ExportRequest.requested_by == user.id)
        .where(ExportRequest.status.in_(["pending", "processing", "uploading"]))
    )
    pending = result.scalars().all()

    if len(pending) >= 10:
        raise HTTPException(
            status_code=429,
            detail="Maximum pending export requests (10) reached"
        )

    export = ExportRequest(
        camera_id=export_data.camera_id,
        requested_by=user.id,
        start_time=export_data.start_time,
        end_time=export_data.end_time,
        status="pending"
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)

    logger.info(
        "Export request created",
        export_id=str(export.id),
        camera_id=str(export_data.camera_id)
    )

    return ExportResponse(**export.to_dict())


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: UUID,
    user: CurrentUser,
    db: DBSession
):
    """
    Get export request details.
    """
    result = await db.execute(select(ExportRequest).where(ExportRequest.id == export_id))
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    # Check access
    if not user.is_admin and export.requested_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return ExportResponse(**export.to_dict())


@router.delete("/{export_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_export(
    export_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Cancel a pending export request. Admin only.
    """
    result = await db.execute(select(ExportRequest).where(ExportRequest.id == export_id))
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if export.status not in ["pending", "processing"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed or failed export")

    db.delete(export)
    await db.commit()

    logger.info("Export request cancelled", export_id=str(export_id))


# Edge device endpoints

@router.get("/edge/pending")
async def get_pending_exports(
    edge: EdgeDevice,
    db: DBSession
):
    """
    Get pending export requests for an edge device's cameras.
    """
    site_id = edge["site_id"]

    # Get cameras for this site
    result = await db.execute(
        select(Camera.id).where(Camera.site_id == UUID(site_id))
    )
    camera_ids = [row[0] for row in result.fetchall()]

    if not camera_ids:
        return {"requests": []}

    # Get pending exports for these cameras
    result = await db.execute(
        select(ExportRequest)
        .where(ExportRequest.camera_id.in_(camera_ids))
        .where(ExportRequest.status == "pending")
        .order_by(ExportRequest.created_at)
    )
    exports = result.scalars().all()

    return {
        "requests": [
            {
                "id": str(e.id),
                "camera_id": str(e.camera_id),
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat()
            }
            for e in exports
        ]
    }


@router.put("/edge/{export_id}/status")
async def update_export_status(
    export_id: UUID,
    status_update: ExportStatusUpdate,
    edge: EdgeDevice,
    db: DBSession
):
    """
    Update export status from edge device.
    """
    result = await db.execute(select(ExportRequest).where(ExportRequest.id == export_id))
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    export.status = status_update.status

    if status_update.file_size:
        export.file_size = status_update.file_size

    if status_update.error_message:
        export.error_message = status_update.error_message

    if status_update.status in ["completed", "failed"]:
        export.completed_at = datetime.utcnow()

    await db.commit()

    logger.info(
        "Export status updated",
        export_id=str(export_id),
        status=status_update.status
    )

    return {"status": "ok"}


@router.post("/edge/{export_id}/upload")
async def upload_export(
    export_id: UUID,
    edge: EdgeDevice,
    file: UploadFile = File(...),
    db: DBSession = None
):
    """
    Upload completed export file from edge device.
    """
    result = await db.execute(select(ExportRequest).where(ExportRequest.id == export_id))
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    # Save file
    upload_dir = os.path.join(settings.UPLOAD_DIR, "exports")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, f"{export_id}.mp4")

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Update export
    export.status = "completed"
    export.file_url = f"/api/exports/{export_id}/download"
    export.file_size = len(content)
    export.completed_at = datetime.utcnow()

    await db.commit()

    logger.info(
        "Export file uploaded",
        export_id=str(export_id),
        file_size=len(content)
    )

    return {"status": "ok", "download_url": export.file_url}


@router.get("/{export_id}/download")
async def download_export(
    export_id: UUID,
    user: CurrentUser,
    db: DBSession
):
    """
    Download completed export file.
    """
    from fastapi.responses import FileResponse

    result = await db.execute(select(ExportRequest).where(ExportRequest.id == export_id))
    export = result.scalar_one_or_none()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    # Check access
    if not user.is_admin and export.requested_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if export.status != "completed":
        raise HTTPException(status_code=400, detail="Export not ready")

    file_path = os.path.join(settings.UPLOAD_DIR, "exports", f"{export_id}.mp4")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=f"export_{export_id}.mp4"
    )
