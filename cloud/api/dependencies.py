"""
Ziskin Field Systems - Cloud API Dependencies

FastAPI dependency injection for authentication, database sessions, etc.
"""

from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
import httpx
import structlog

from config import settings
from db.database import get_db
from models.user import User

logger = structlog.get_logger(__name__)


async def verify_clerk_token(authorization: str = Header(None)) -> dict:
    """Verify Clerk JWT token and return user claims."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        # Fetch Clerk JWKS
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.clerk.dev/v1/jwks",
                headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"}
            )
            jwks = response.json()

        # Decode and verify token
        # In production, cache the JWKS and use proper key selection
        header = jwt.get_unverified_header(token)
        key = None

        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == header.get("kid"):
                key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
                break

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token key"
            )

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_user(
    claims: dict = Depends(verify_clerk_token),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get the current authenticated user from database."""
    from sqlalchemy import select

    clerk_id = claims.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims"
        )

    result = await db.execute(
        select(User).where(User.clerk_id == clerk_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


async def require_admin(
    user: User = Depends(get_current_user)
) -> User:
    """Require that the current user is an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


async def verify_edge_device(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Verify edge device API key and return site information."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

    api_key = authorization[7:]

    from sqlalchemy import select
    from models.site import Site

    result = await db.execute(
        select(Site).where(Site.api_key == api_key)
    )
    site = result.scalar_one_or_none()

    if not site:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )

    return {
        "site_id": str(site.id),
        "site_name": site.name,
        "client_id": str(site.client_id)
    }


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
EdgeDevice = Annotated[dict, Depends(verify_edge_device)]
