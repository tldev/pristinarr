"""JSON API routes for programmatic access."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)


class ApplicationConfig(BaseModel):
    """Configuration for a Starr application."""
    api_key: str
    url: str
    tag_name: str
    count: str = "10"
    monitored: str = "true"
    unattended: str = "false"
    ignore_tag: Optional[str] = None
    quality_profile_name: Optional[str] = None
    # Status fields (application-specific)
    movie_status: Optional[str] = None
    series_status: Optional[str] = None
    artist_status: Optional[str] = None
    author_status: Optional[str] = None


class NotificationConfig(BaseModel):
    """Notification configuration."""
    discord_webhook: Optional[str] = None
    notifiarr_passthrough_webhook: Optional[str] = None
    notifiarr_passthrough_discord_channel_id: Optional[str] = None


class SchedulerConfig(BaseModel):
    """Scheduler configuration."""
    enabled: bool = False
    interval_hours: int = 6


class RunResponse(BaseModel):
    """Response from a run operation."""
    success: bool
    message: str
    searched_count: int = 0
    dry_run: bool = False
    items: list[str] = []


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/history")
async def get_history():
    """Get run history."""
    from app.runner import get_run_history
    
    return get_run_history()


@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status."""
    from app.scheduler import get_scheduler_status
    
    return get_scheduler_status()


@router.get("/config")
async def get_config():
    """Get the current configuration."""
    from app.config import load_config, config_to_dict
    
    config = load_config()
    return config_to_dict(config)


@router.post("/config/application/{app_name}")
async def save_application_config(app_name: str, config: ApplicationConfig):
    """Save configuration for a specific application."""
    from app.config import load_config, save_config
    
    cfg = load_config()
    
    if not cfg.has_section(app_name):
        cfg.add_section(app_name)
    
    cfg.set(app_name, "ApiKey", config.api_key)
    cfg.set(app_name, "Url", config.url)
    cfg.set(app_name, "TagName", config.tag_name)
    cfg.set(app_name, "Count", config.count)
    cfg.set(app_name, "Monitored", config.monitored)
    cfg.set(app_name, "Unattended", config.unattended)
    
    if config.ignore_tag:
        cfg.set(app_name, "IgnoreTag", config.ignore_tag)
    if config.quality_profile_name:
        cfg.set(app_name, "QualityProfileName", config.quality_profile_name)
    if config.movie_status:
        cfg.set(app_name, "MovieStatus", config.movie_status)
    if config.series_status:
        cfg.set(app_name, "SeriesStatus", config.series_status)
    if config.artist_status:
        cfg.set(app_name, "ArtistStatus", config.artist_status)
    if config.author_status:
        cfg.set(app_name, "AuthorStatus", config.author_status)
    
    save_config(cfg)
    
    return {"success": True, "message": f"Configuration saved for {app_name}"}


@router.delete("/config/application/{app_name}")
async def delete_application_config(app_name: str):
    """Delete configuration for a specific application."""
    from app.config import load_config, save_config
    
    cfg = load_config()
    
    if not cfg.has_section(app_name):
        raise HTTPException(status_code=404, detail=f"Application {app_name} not found")
    
    cfg.remove_section(app_name)
    save_config(cfg)
    
    return {"success": True, "message": f"Configuration deleted for {app_name}"}


@router.post("/config/notifications")
async def save_notification_config(config: NotificationConfig):
    """Save notification configuration."""
    from app.config import load_config, save_config
    
    cfg = load_config()
    
    if not cfg.has_section("Notifications"):
        cfg.add_section("Notifications")
    
    if config.discord_webhook:
        cfg.set("Notifications", "DiscordWebhook", config.discord_webhook)
    if config.notifiarr_passthrough_webhook:
        cfg.set("Notifications", "NotifiarrPassthroughWebhook", config.notifiarr_passthrough_webhook)
    if config.notifiarr_passthrough_discord_channel_id:
        cfg.set("Notifications", "NotifiarrPassthroughDiscordChannelId", config.notifiarr_passthrough_discord_channel_id)
    
    save_config(cfg)
    
    return {"success": True, "message": "Notification configuration saved"}


@router.post("/config/scheduler")
async def save_scheduler_config(config: SchedulerConfig):
    """Save scheduler configuration."""
    from app.config import load_config, save_config
    from app.scheduler import configure_scheduler
    
    cfg = load_config()
    
    if not cfg.has_section("Scheduler"):
        cfg.add_section("Scheduler")
    
    cfg.set("Scheduler", "Enabled", str(config.enabled).lower())
    cfg.set("Scheduler", "IntervalHours", str(config.interval_hours))
    
    save_config(cfg)
    
    # Reconfigure the scheduler
    configure_scheduler(enabled=config.enabled, interval_hours=config.interval_hours)
    
    return {"success": True, "message": "Scheduler configuration saved"}


@router.post("/run/{app_name}")
async def run_application(app_name: str, dry_run: bool = False) -> RunResponse:
    """Manually trigger a run for a specific application."""
    from app.runner import run_application as do_run
    
    try:
        result = await do_run(app_name, dry_run=dry_run)
        if dry_run:
            return RunResponse(
                success=True,
                message=f"Dry run: would search {result['searched_count']} items in {app_name}",
                searched_count=result["searched_count"],
                dry_run=True,
                items=result.get("items", []),
            )
        return RunResponse(
            success=True,
            message=f"Successfully searched {result['searched_count']} items in {app_name}",
            searched_count=result["searched_count"],
            items=result.get("items", []),
        )
    except Exception as e:
        logger.exception(f"Error running {app_name}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_all(dry_run: bool = False) -> RunResponse:
    """Manually trigger a run for all configured applications."""
    from app.runner import run_all_applications
    
    try:
        result = await run_all_applications(dry_run=dry_run)
        if dry_run:
            return RunResponse(
                success=True,
                message=f"Dry run: would search {result['total_searched']} items across all applications",
                searched_count=result["total_searched"],
                dry_run=True,
                items=result.get("items", []),
            )
        return RunResponse(
            success=True,
            message=f"Successfully processed {result['total_searched']} items across all applications",
            searched_count=result["total_searched"],
            items=result.get("items", []),
        )
    except Exception as e:
        logger.exception("Error running all applications")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test/{app_name}")
async def test_connection(app_name: str):
    """Test connection to a Starr application."""
    from app.config import load_config
    from app.starr import StarrClient
    
    cfg = load_config()
    
    if not cfg.has_section(app_name):
        raise HTTPException(status_code=404, detail=f"Application {app_name} not configured")
    
    app_config = dict(cfg[app_name])
    
    try:
        client = StarrClient(
            app_type=app_name.lower(),
            url=app_config.get("Url", "").rstrip("/"),
            api_key=app_config.get("ApiKey", ""),
        )
        api_version = await client.get_api_version()
        return {
            "success": True,
            "message": f"Successfully connected to {app_name}",
            "api_version": api_version,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect: {str(e)}")

