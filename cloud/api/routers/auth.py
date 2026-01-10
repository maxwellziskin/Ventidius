"""
Ziskin Field Systems - Authentication Router

Handles Clerk webhook events and user authentication.
"""

from fastapi import APIRouter, HTTPException, Header, Request
from sqlalchemy import select
import hmac
import hashlib
import structlog

from dependencies import DBSession, CurrentUser
from models.user import User
from schemas.user import UserResponse
from config import settings

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/webhook")
async def clerk_webhook(
    request: Request,
    db: DBSession,
    svix_id: str = Header(None),
    svix_timestamp: str = Header(None),
    svix_signature: str = Header(None)
):
    """
    Handle Clerk webhook events for user creation/updates.
    """
    if not all([svix_id, svix_timestamp, svix_signature]):
        raise HTTPException(status_code=400, detail="Missing webhook headers")

    # Verify webhook signature
    body = await request.body()
    payload = body.decode()

    try:
        # Construct the signed content
        signed_content = f"{svix_id}.{svix_timestamp}.{payload}"

        # Get the expected signature
        secret = settings.CLERK_WEBHOOK_SECRET
        if secret.startswith("whsec_"):
            secret = secret[6:]

        import base64
        secret_bytes = base64.b64decode(secret)
        expected_sig = hmac.new(
            secret_bytes,
            signed_content.encode(),
            hashlib.sha256
        ).digest()
        expected_sig_b64 = base64.b64encode(expected_sig).decode()

        # Compare signatures
        signatures = svix_signature.split(" ")
        verified = False
        for sig in signatures:
            if "," in sig:
                version, sig_value = sig.split(",", 1)
                if version == "v1" and hmac.compare_digest(sig_value, expected_sig_b64):
                    verified = True
                    break

        if not verified:
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    except Exception as e:
        logger.error("Webhook signature verification failed", error=str(e))
        raise HTTPException(status_code=401, detail="Signature verification failed")

    # Parse webhook payload
    import json
    data = json.loads(payload)
    event_type = data.get("type")

    logger.info("Received Clerk webhook", event_type=event_type)

    if event_type == "user.created":
        user_data = data.get("data", {})
        clerk_id = user_data.get("id")
        email = user_data.get("email_addresses", [{}])[0].get("email_address")

        if clerk_id and email:
            # Check if user already exists
            result = await db.execute(
                select(User).where(User.clerk_id == clerk_id)
            )
            existing = result.scalar_one_or_none()

            if not existing:
                user = User(
                    clerk_id=clerk_id,
                    email=email,
                    role="client"  # Default role
                )
                db.add(user)
                await db.commit()
                logger.info("Created user from webhook", clerk_id=clerk_id, email=email)

    elif event_type == "user.updated":
        user_data = data.get("data", {})
        clerk_id = user_data.get("id")
        email = user_data.get("email_addresses", [{}])[0].get("email_address")

        if clerk_id:
            result = await db.execute(
                select(User).where(User.clerk_id == clerk_id)
            )
            user = result.scalar_one_or_none()

            if user and email:
                user.email = email
                await db.commit()
                logger.info("Updated user from webhook", clerk_id=clerk_id)

    elif event_type == "user.deleted":
        user_data = data.get("data", {})
        clerk_id = user_data.get("id")

        if clerk_id:
            result = await db.execute(
                select(User).where(User.clerk_id == clerk_id)
            )
            user = result.scalar_one_or_none()

            if user:
                await db.delete(user)
                await db.commit()
                logger.info("Deleted user from webhook", clerk_id=clerk_id)

    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: CurrentUser):
    """
    Get the current authenticated user's information.
    """
    return user
