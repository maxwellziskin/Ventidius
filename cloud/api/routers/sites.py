"""
Ziskin Field Systems - Sites Router

CRUD operations for surveillance sites.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from typing import List
from uuid import UUID
import structlog

from dependencies import DBSession, CurrentUser, AdminUser
from models.site import Site
from models.camera import Camera
from schemas.site import SiteCreate, SiteUpdate, SiteResponse
from schemas.camera import CameraResponse

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("", response_model=List[SiteResponse])
async def list_sites(
    user: CurrentUser,
    db: DBSession
):
    """
    List sites. Admins see all sites, clients see only their sites.
    """
    if user.is_admin:
        result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    else:
        result = await db.execute(
            select(Site).where(Site.client_id == user.client_id).order_by(Site.created_at.desc())
        )

    sites = result.scalars().all()
    return [SiteResponse(**s.to_dict()) for s in sites]


@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
async def create_site(
    site_data: SiteCreate,
    user: AdminUser,
    db: DBSession
):
    """
    Create a new site. Admin only.
    """
    site = Site(
        client_id=site_data.client_id,
        name=site_data.name,
        address=site_data.address
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)

    logger.info("Site created", site_id=str(site.id), name=site.name)

    return SiteResponse(**site.to_dict(include_api_key=True))


@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: UUID,
    user: CurrentUser,
    db: DBSession
):
    """
    Get site details.
    """
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Check access
    if not user.is_admin and site.client_id != user.client_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return SiteResponse(**site.to_dict(include_api_key=user.is_admin))


@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: UUID,
    site_data: SiteUpdate,
    user: AdminUser,
    db: DBSession
):
    """
    Update a site. Admin only.
    """
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if site_data.name is not None:
        site.name = site_data.name
    if site_data.address is not None:
        site.address = site_data.address
    if site_data.wireguard_pubkey is not None:
        site.wireguard_pubkey = site_data.wireguard_pubkey

    await db.commit()
    await db.refresh(site)

    logger.info("Site updated", site_id=str(site.id))

    return SiteResponse(**site.to_dict(include_api_key=True))


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_site(
    site_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Delete a site. Admin only.
    """
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    db.delete(site)
    await db.commit()

    logger.info("Site deleted", site_id=str(site_id))


@router.get("/{site_id}/cameras", response_model=List[CameraResponse])
async def list_site_cameras(
    site_id: UUID,
    user: CurrentUser,
    db: DBSession
):
    """
    List cameras for a site.
    """
    # Verify site access
    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if not user.is_admin and site.client_id != user.client_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get cameras
    result = await db.execute(
        select(Camera).where(Camera.site_id == site_id).order_by(Camera.name)
    )
    cameras = result.scalars().all()

    return [CameraResponse(**c.to_dict()) for c in cameras]


@router.post("/{site_id}/regenerate-key", response_model=SiteResponse)
async def regenerate_api_key(
    site_id: UUID,
    user: AdminUser,
    db: DBSession
):
    """
    Regenerate API key for a site. Admin only.
    """
    import secrets

    result = await db.execute(select(Site).where(Site.id == site_id))
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    site.api_key = secrets.token_urlsafe(48)
    await db.commit()
    await db.refresh(site)

    logger.info("Site API key regenerated", site_id=str(site_id))

    return SiteResponse(**site.to_dict(include_api_key=True))
