"""Notification handlers for Discord and Notifiarr."""

from app.notifications.discord import send_discord_message
from app.notifications.notifiarr import send_notifiarr_notification

__all__ = ["send_discord_message", "send_notifiarr_notification"]

