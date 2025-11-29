"""HTML page routes for the web interface."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Dashboard page showing configured applications and status."""
    from app.config import load_config
    
    config = load_config()
    applications = []
    
    # Get list of configured applications (exclude Notifications, General, Scheduler)
    excluded_sections = {"Notifications", "General", "Scheduler"}
    for section in config.sections():
        if section not in excluded_sections:
            app_config = dict(config[section])
            applications.append({
                "name": section,
                "url": app_config.get("Url", ""),
                "enabled": True,  # All configured apps are considered enabled
            })
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "applications": applications,
        },
    )


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration editor page."""
    from app.config import load_config
    
    config = load_config()
    
    # Parse config into structured data for the template
    notifications = {}
    if config.has_section("Notifications"):
        notifications = dict(config["Notifications"])
    elif config.has_section("General"):
        notifications = dict(config["General"])
    
    scheduler_config = {"Enabled": "false", "IntervalHours": "6"}
    if config.has_section("Scheduler"):
        scheduler_config = dict(config["Scheduler"])
    
    applications = {}
    excluded_sections = {"Notifications", "General", "Scheduler"}
    for section in config.sections():
        if section not in excluded_sections:
            applications[section] = dict(config[section])
    
    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "notifications": notifications,
            "scheduler": scheduler_config,
            "applications": applications,
        },
    )


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Log viewer page for recent runs."""
    from app.runner import get_run_history
    
    history = get_run_history()
    
    return templates.TemplateResponse(
        "logs.html",
        {
            "request": request,
            "history": history,
        },
    )

