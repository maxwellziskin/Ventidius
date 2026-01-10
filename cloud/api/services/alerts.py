"""
Ziskin Field Systems - Alert Service

Handles email alerts and notifications.
"""

import httpx
import structlog
from datetime import datetime

from config import settings

logger = structlog.get_logger(__name__)


async def send_email(
    to: str,
    subject: str,
    html_body: str
) -> bool:
    """Send an email using Resend API."""
    if not settings.RESEND_API_KEY:
        logger.warning("Resend API key not configured, skipping email")
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "from": settings.EMAIL_FROM,
                    "to": to,
                    "subject": subject,
                    "html": html_body
                }
            )

            if response.status_code == 200:
                logger.info("Email sent successfully", to=to, subject=subject)
                return True
            else:
                logger.error(
                    "Failed to send email",
                    status=response.status_code,
                    response=response.text
                )
                return False

    except Exception as e:
        logger.error("Error sending email", error=str(e))
        return False


async def send_alert_email(
    site_name: str,
    alert_type: str,
    message: str,
    details: dict = None
):
    """Send an alert email to administrators."""
    # Get admin email - in production, fetch from database
    admin_email = "admin@zfs.example.com"

    subject = f"[ZFS Alert] {site_name}: {alert_type}"

    details_html = ""
    if details:
        details_html = "<ul>"
        for key, value in details.items():
            details_html += f"<li><strong>{key}:</strong> {value}</li>"
        details_html += "</ul>"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #d32f2f;">🚨 Alert: {alert_type}</h2>

        <p><strong>Site:</strong> {site_name}</p>
        <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

        <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0;">{message}</p>
        </div>

        {details_html if details_html else ''}

        <p style="color: #666; font-size: 12px;">
            This is an automated alert from Ziskin Field Systems.
            <br>
            <a href="{settings.API_BASE_URL}/admin">View Dashboard</a>
        </p>
    </body>
    </html>
    """

    await send_email(admin_email, subject, html_body)


async def send_camera_offline_alert(
    site_name: str,
    camera_name: str,
    last_seen: datetime
):
    """Send alert when camera goes offline."""
    await send_alert_email(
        site_name=site_name,
        alert_type="Camera Offline",
        message=f"Camera '{camera_name}' has been offline for more than 2 minutes.",
        details={
            "Camera": camera_name,
            "Last Seen": last_seen.strftime('%Y-%m-%d %H:%M:%S UTC') if last_seen else "Unknown"
        }
    )


async def send_invite_email(
    to_email: str,
    invite_url: str,
    invited_by: str
):
    """Send invitation email to new user."""
    subject = "You've been invited to Ziskin Field Systems"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Welcome to Ziskin Field Systems</h2>

        <p>You've been invited by {invited_by} to access the Ziskin Field Systems platform.</p>

        <p>Click the button below to set up your account:</p>

        <div style="margin: 30px 0;">
            <a href="{invite_url}"
               style="background-color: #1976d2; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Accept Invitation
            </a>
        </div>

        <p style="color: #666; font-size: 12px;">
            If you didn't expect this invitation, you can ignore this email.
            <br><br>
            This invitation link will expire in 7 days.
        </p>
    </body>
    </html>
    """

    await send_email(to_email, subject, html_body)
    logger.info("Invitation email sent", to=to_email, invited_by=invited_by)


async def send_export_ready_email(
    to_email: str,
    camera_name: str,
    download_url: str
):
    """Send email when export is ready for download."""
    subject = f"Your video export is ready - {camera_name}"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2>Your Video Export is Ready</h2>

        <p>The video export you requested from <strong>{camera_name}</strong> is now ready for download.</p>

        <div style="margin: 30px 0;">
            <a href="{download_url}"
               style="background-color: #4caf50; color: white; padding: 12px 24px;
                      text-decoration: none; border-radius: 5px; display: inline-block;">
                Download Video
            </a>
        </div>

        <p style="color: #666; font-size: 12px;">
            This download link will expire in 24 hours.
            <br><br>
            Ziskin Field Systems
        </p>
    </body>
    </html>
    """

    await send_email(to_email, subject, html_body)
    logger.info("Export ready email sent", to=to_email, camera=camera_name)
