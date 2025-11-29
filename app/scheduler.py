"""APScheduler setup for periodic background runs."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler()

# Track last run info
_last_run_time: Optional[datetime] = None
_last_run_success: Optional[bool] = None
_next_run_time: Optional[datetime] = None


def _job_listener(event):
    """Listen for job events to track status."""
    global _last_run_time, _last_run_success
    
    _last_run_time = datetime.now()
    
    if event.exception:
        _last_run_success = False
        logger.error(f"Scheduled job failed: {event.exception}")
    else:
        _last_run_success = True
        logger.info("Scheduled job completed successfully")


# Register the listener
scheduler.add_listener(_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


def _run_all_sync():
    """Synchronous wrapper to run the async function."""
    from app.runner import run_all_applications
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_all_applications())
    finally:
        loop.close()


def configure_scheduler(enabled: bool = False, interval_hours: int = 6):
    """Configure the scheduler with the given settings.
    
    Args:
        enabled: Whether the scheduler should run jobs.
        interval_hours: Hours between each run.
    """
    global _next_run_time
    
    # Remove existing jobs
    scheduler.remove_all_jobs()
    _next_run_time = None
    
    if enabled:
        job = scheduler.add_job(
            _run_all_sync,
            trigger=IntervalTrigger(hours=interval_hours),
            id="pristinarr_main",
            name="Pristinarr Main Job",
            replace_existing=True,
        )
        _next_run_time = job.next_run_time
        logger.info(f"Scheduler configured to run every {interval_hours} hours")
        logger.info(f"Next run scheduled for: {_next_run_time}")
    else:
        logger.info("Scheduler is disabled")


def get_scheduler_status() -> dict:
    """Get the current scheduler status.
    
    Returns:
        Dictionary with scheduler status information.
    """
    job = scheduler.get_job("pristinarr_main")
    
    return {
        "running": scheduler.running,
        "enabled": job is not None,
        "next_run_time": job.next_run_time.isoformat() if job and job.next_run_time else None,
        "last_run_time": _last_run_time.isoformat() if _last_run_time else None,
        "last_run_success": _last_run_success,
    }


def init_scheduler_from_config():
    """Initialize the scheduler from the configuration file."""
    from app.config import load_config, get_scheduler_config
    
    config = load_config()
    scheduler_config = get_scheduler_config(config)
    
    configure_scheduler(
        enabled=scheduler_config["enabled"],
        interval_hours=scheduler_config["interval_hours"],
    )
