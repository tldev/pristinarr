"""Notifiarr Passthrough notification handler."""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


async def send_notifiarr_notification(
    webhook_url: str,
    channel_id: int,
    app_name: str,
    description: str,
    color: str = "FF0000",
    thumbnail_url: Optional[str] = None,
    title: Optional[str] = None,
    icon_url: Optional[str] = None,
    content: Optional[str] = None,
    fields: Optional[list[dict[str, Any]]] = None,
    footer: Optional[str] = None,
    image_url: Optional[str] = None,
    ping_user: Optional[int] = None,
    ping_role: Optional[int] = None,
    update: bool = False,
    event: Optional[str] = None,
) -> bool:
    """Send a notification through Notifiarr's Discord Passthrough Integration.

    Args:
        webhook_url: Notifiarr passthrough webhook URL.
        channel_id: Discord channel ID for the notification.
        app_name: Name of the application sending the notification.
        description: Text between the title and embeds.
        color: 6-digit HTML color code (without #).
        thumbnail_url: URL of thumbnail image.
        title: Title of the notification.
        icon_url: URL of icon to display.
        content: Text above the embed (for toast notifications).
        fields: List of field objects for the embed.
        footer: Footer text.
        image_url: URL to image at bottom of notification.
        ping_user: Discord user ID to ping.
        ping_role: Discord role ID to ping.
        update: Whether to update an existing message with the same ID.
        event: Unique ID for this notification.

    Returns:
        True if the notification was sent successfully, False otherwise.
    """
    if not webhook_url:
        logger.warning("Notifiarr webhook URL is empty, skipping notification")
        return False

    if not channel_id:
        logger.warning("Notifiarr channel ID is empty, skipping notification")
        return False

    # Build the payload structure matching Notifiarr's API
    payload = {
        "notification": {
            "name": app_name,
            "update": update,
        },
        "discord": {
            "color": color,
            "text": {
                "description": description,
            },
            "ids": {
                "channel": channel_id,
            },
        },
    }

    # Add optional notification fields
    if event:
        payload["notification"]["event"] = event

    # Add optional discord fields
    discord = payload["discord"]

    if ping_user or ping_role:
        discord["ping"] = {}
        if ping_user:
            discord["ping"]["pingUser"] = ping_user
        if ping_role:
            discord["ping"]["pingRole"] = ping_role

    if thumbnail_url or image_url:
        discord["images"] = {}
        if thumbnail_url:
            discord["images"]["thumbnail"] = thumbnail_url
        if image_url:
            discord["images"]["image"] = image_url

    text = discord["text"]
    if title:
        text["title"] = title
    if icon_url:
        text["icon"] = icon_url
    if content:
        text["content"] = content
    if fields:
        text["fields"] = fields
    if footer:
        text["footer"] = footer

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers={"Accept": "text/plain"},
                timeout=30.0,
            )

            if response.status_code >= 200 and response.status_code < 300:
                try:
                    result = response.json()
                    if result.get("result") == "success":
                        logger.debug("Notification successfully sent to Notifiarr")
                        return True
                    else:
                        logger.warning(
                            f"Notifiarr returned non-success result: {result}"
                        )
                        return False
                except Exception:
                    # Response might not be JSON
                    logger.debug("Notification sent to Notifiarr (non-JSON response)")
                    return True
            else:
                logger.warning(
                    f"Failed to send Notifiarr notification. "
                    f"Status code: {response.status_code}"
                )
                return False

    except httpx.TimeoutException:
        logger.error("Timeout while sending Notifiarr notification")
        return False
    except httpx.RequestError as e:
        logger.error(f"Error sending Notifiarr notification: {e}")
        return False

