"""Discord webhook notification handler."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

AVATAR_URL = "https://gh.notifiarr.com/images/icons/powershell.png"


async def send_discord_message(
    webhook_url: str,
    title: str,
    description: str,
    color: int = 0,
    thumbnail_url: Optional[str] = None,
    avatar_url: Optional[str] = None,
        username: str = "Pristinarr",
) -> bool:
    """Send a message to Discord via webhook.

    Args:
        webhook_url: The Discord webhook URL.
        title: Title of the embedded message.
        description: Main content of the embedded message.
        color: Decimal color code for the embed sidebar.
        thumbnail_url: URL for the embed's thumbnail image.
        avatar_url: URL for the webhook's avatar image.
        username: Username shown for the webhook.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    if not webhook_url:
        logger.warning("Discord webhook URL is empty, skipping notification")
        return False

    payload = {
        "username": username,
        "avatar_url": avatar_url or AVATAR_URL,
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
            }
        ],
    }

    # Add thumbnail if provided
    if thumbnail_url:
        payload["embeds"][0]["thumbnail"] = {"url": thumbnail_url}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=30.0,
            )

            if 200 <= response.status_code < 300:
                logger.debug("Discord message sent successfully")
                return True
            else:
                logger.warning(
                    f"Failed to send Discord message. "
                    f"Status code: {response.status_code}"
                )
                return False

    except httpx.TimeoutException:
        logger.error("Timeout while sending Discord message")
        return False
    except httpx.RequestError as e:
        logger.error(f"Error sending Discord message: {e}")
        return False

