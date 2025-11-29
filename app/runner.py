"""Main runner logic for processing Starr applications."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# In-memory run history (in production, this could be persisted to a file or database)
_run_history: list[dict[str, Any]] = []


def get_run_history(limit: int = 50) -> list[dict[str, Any]]:
    """Get the run history, most recent first.
    
    Args:
        limit: Maximum number of entries to return.
        
    Returns:
        List of run history entries.
    """
    return list(reversed(_run_history[-limit:]))


def add_run_history(
    application: str,
    success: bool,
    searched_count: int,
    message: str,
):
    """Add an entry to the run history.
    
    Args:
        application: Name of the application that was run.
        success: Whether the run was successful.
        searched_count: Number of items searched.
        message: Status message.
    """
    _run_history.append({
        "timestamp": datetime.now().isoformat(),
        "application": application,
        "success": success,
        "searched_count": searched_count,
        "message": message,
    })
    
    # Keep only the last 100 entries
    if len(_run_history) > 100:
        _run_history.pop(0)


async def run_application(app_name: str, dry_run: bool = False) -> dict[str, Any]:
    """Run the upgrade search for a specific application.
    
    Args:
        app_name: Name of the application to process.
        dry_run: If True, only report what would be searched without actually searching.
        
    Returns:
        Dictionary with run results.
    """
    from app.config import load_config, validate_application_config
    from app.starr import StarrClient
    from app.notifications import send_discord_message, send_notifiarr_notification
    
    logger.info(f"Starting run for {app_name}")
    
    config = load_config()
    
    if not config.has_section(app_name):
        raise ValueError(f"Application {app_name} is not configured")
    
    app_config = dict(config[app_name])
    
    # Validate config
    errors = validate_application_config(app_name, app_config)
    if errors:
        error_msg = f"Configuration errors for {app_name}: {'; '.join(errors)}"
        add_run_history(app_name, False, 0, error_msg)
        raise ValueError(error_msg)
    
    # Determine app type from name
    app_type = None
    for t in ["radarr", "sonarr", "lidarr", "readarr"]:
        if t in app_name.lower():
            app_type = t
            break
    
    if not app_type:
        raise ValueError(f"Cannot determine application type from name: {app_name}")
    
    # Create client
    client = StarrClient(
        app_type=app_type,
        url=app_config.get("Url", "").rstrip("/"),
        api_key=app_config.get("ApiKey", ""),
    )
    
    # Get API version
    api_version = await client.get_api_version()
    client.api_version = api_version
    
    # Get tag ID (create if doesn't exist)
    tag_name = app_config.get("TagName", "")
    tag_id = await client.get_or_create_tag(tag_name)
    
    # Get ignore tag ID if specified
    ignore_tag_id = None
    ignore_tag = app_config.get("IgnoreTag")
    if ignore_tag:
        ignore_tag_id = await client.get_tag_id(ignore_tag)
        if tag_id == ignore_tag_id:
            raise ValueError(f"TagName and IgnoreTag cannot be the same: {tag_name}")
    
    # Get quality profile ID if specified
    quality_profile_id = None
    quality_profile = app_config.get("QualityProfileName")
    if quality_profile:
        quality_profile_id = await client.get_quality_profile_id(quality_profile)
    
    # Get all media
    all_media = await client.get_media()
    logger.info(f"Retrieved {len(all_media)} total media items from {app_name}")
    
    # Build filter criteria
    monitored = app_config.get("Monitored", "true").lower() == "true"
    unattended = app_config.get("Unattended", "false").lower() == "true"
    
    # Get status filter
    status = None
    if app_type == "radarr":
        status = app_config.get("MovieStatus")
    elif app_type == "sonarr":
        status = app_config.get("SeriesStatus")
    elif app_type == "lidarr":
        status = app_config.get("ArtistStatus")
    elif app_type == "readarr":
        status = app_config.get("AuthorStatus")
    
    # Filter media
    filtered_media = client.filter_media(
        media=all_media,
        tag_id=tag_id,
        monitored=monitored,
        status=status,
        quality_profile_id=quality_profile_id,
        ignore_tag_id=ignore_tag_id,
        unattended=False,  # First pass: get media WITHOUT the tag
    )
    
    # Handle empty filtered list
    if not filtered_media:
        if unattended:
            # Remove tags from all media and try again
            logger.info(f"No media to process, removing tags and retrying (unattended mode)")
            
            media_with_tag = client.filter_media(
                media=all_media,
                tag_id=tag_id,
                monitored=monitored,
                status=status,
                quality_profile_id=quality_profile_id,
                ignore_tag_id=ignore_tag_id,
                unattended=True,  # Get media WITH the tag
            )
            
            if media_with_tag:
                await client.remove_media_tag(media_with_tag, tag_id)
                
                # Re-fetch and filter
                all_media = await client.get_media()
                filtered_media = client.filter_media(
                    media=all_media,
                    tag_id=tag_id,
                    monitored=monitored,
                    status=status,
                    quality_profile_id=quality_profile_id,
                    ignore_tag_id=ignore_tag_id,
                    unattended=False,
                )
        
        if not filtered_media:
            msg = f"No media left to process for {app_name}"
            logger.info(msg)
            add_run_history(app_name, True, 0, msg)
            
            # Send notifications
            await _send_notifications(config, app_name, app_type, 0, [])
            
            return {"searched_count": 0, "items": []}
    
    logger.info(f"Found {len(filtered_media)} media items to process for {app_name}")
    
    # Select items to search based on count
    count_str = app_config.get("Count", "10")
    if count_str.lower() == "max":
        media_to_search = filtered_media
    else:
        count = int(count_str)
        import random
        media_to_search = random.sample(filtered_media, min(count, len(filtered_media)))
    
    # Get titles for logging
    titles = []
    for item in media_to_search:
        if app_type == "lidarr":
            titles.append(item.get("artistName", "Unknown"))
        elif app_type == "readarr":
            titles.append(item.get("authorName", "Unknown"))
        else:
            titles.append(item.get("title", "Unknown"))
    
    # In dry run mode, just return what would be searched
    if dry_run:
        msg = f"Dry run: would search {len(media_to_search)} items in {app_name}"
        logger.info(msg)
        add_run_history(app_name, True, len(media_to_search), f"[DRY RUN] {msg}")
        return {"searched_count": len(media_to_search), "items": titles}
    
    # Search media
    await client.search_media(media_to_search)
    
    # Add tags
    await client.add_media_tag(media_to_search, tag_id)
    
    msg = f"Searched {len(media_to_search)} items in {app_name}"
    logger.info(msg)
    add_run_history(app_name, True, len(media_to_search), msg)
    
    # Send notifications
    await _send_notifications(config, app_name, app_type, len(media_to_search), titles)
    
    return {"searched_count": len(media_to_search), "items": titles}


async def _send_notifications(
    config,
    app_name: str,
    app_type: str,
    count: int,
    titles: list[str],
):
    """Send notifications to configured services."""
    from app.notifications import send_discord_message, send_notifiarr_notification
    
    # Get notification config
    discord_webhook = None
    notifiarr_webhook = None
    notifiarr_channel = None
    
    if config.has_section("Notifications"):
        notif_config = dict(config["Notifications"])
        discord_webhook = notif_config.get("DiscordWebhook")
        notifiarr_webhook = notif_config.get("NotifiarrPassthroughWebhook")
        notifiarr_channel = notif_config.get("NotifiarrPassthroughDiscordChannelId")
    elif config.has_section("General"):
        gen_config = dict(config["General"])
        discord_webhook = gen_config.get("DiscordWebhook")
        notifiarr_webhook = gen_config.get("NotifiarrPassthroughWebhook")
        notifiarr_channel = gen_config.get("NotifiarrPassthroughDiscordChannelId")
    
    # Build message
    if count == 0:
        description = f"No media left to search for {app_name}"
    else:
        description = f"Search started for {count} media items in {app_name}:"
        if len(titles) <= 20:
            for title in titles:
                description += f"\n- {title}"
        else:
            description += "\n\n*The list of media items is too long to display here.*"
    
    # Get colors and thumbnails
    colors = {
        "radarr": {"html": "FFC230", "decimal": 16761392},
        "sonarr": {"html": "00CCFF", "decimal": 52479},
        "lidarr": {"html": "009252", "decimal": 37458},
        "readarr": {"html": "8E2222", "decimal": 9314850},
    }
    thumbnails = {
        "radarr": "https://gh.notifiarr.com/images/icons/radarr.png",
        "sonarr": "https://gh.notifiarr.com/images/icons/sonarr.png",
        "lidarr": "https://gh.notifiarr.com/images/icons/lidarr.png",
        "readarr": "https://gh.notifiarr.com/images/icons/readarr.png",
    }
    
    color = colors.get(app_type, {"html": "FF0000", "decimal": 16711680})
    thumbnail = thumbnails.get(app_type, "https://gh.notifiarr.com/images/icons/shell.png")
    
    # Send Discord notification
    if discord_webhook:
        try:
            await send_discord_message(
                webhook_url=discord_webhook,
                title=f"Pristinarr - {app_name}",
                description=description,
                color=color["decimal"],
                thumbnail_url=thumbnail,
            )
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
    
    # Send Notifiarr notification
    if notifiarr_webhook and notifiarr_channel:
        try:
            await send_notifiarr_notification(
                webhook_url=notifiarr_webhook,
                channel_id=int(notifiarr_channel),
                app_name=f"Pristinarr - {app_name}",
                description=description,
                color=color["html"],
                thumbnail_url=thumbnail,
            )
        except Exception as e:
            logger.error(f"Failed to send Notifiarr notification: {e}")


async def run_all_applications(dry_run: bool = False) -> dict[str, Any]:
    """Run the upgrade search for all configured applications.
    
    Args:
        dry_run: If True, only report what would be searched without actually searching.
    
    Returns:
        Dictionary with total results.
    """
    from app.config import load_config
    
    config = load_config()
    excluded_sections = {"Notifications", "General", "Scheduler"}
    
    total_searched = 0
    all_items = []
    results = []
    
    for section in config.sections():
        if section not in excluded_sections:
            try:
                result = await run_application(section, dry_run=dry_run)
                total_searched += result["searched_count"]
                all_items.extend(result.get("items", []))
                results.append({
                    "application": section,
                    "success": True,
                    **result,
                })
            except Exception as e:
                logger.error(f"Error running {section}: {e}")
                results.append({
                    "application": section,
                    "success": False,
                    "error": str(e),
                })
    
    return {"total_searched": total_searched, "results": results, "items": all_items}

