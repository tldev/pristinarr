"""INI configuration file reader/writer with validation."""

import configparser
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "pristinarr.conf"

# Environment variable to override config path
CONFIG_PATH_ENV = "PRISTINARR_CONFIG_PATH"

# Validation constants
VALID_MONITORED_VALUES = {"true", "false"}
VALID_UNATTENDED_VALUES = {"true", "false"}
VALID_MOVIE_STATUS = {"tba", "announced", "incinemas", "released", "deleted"}
VALID_SERIES_STATUS = {"continuing", "ended", "upcoming", "deleted"}
VALID_ARTIST_STATUS = {"continuing", "ended"}
VALID_AUTHOR_STATUS = {"continuing", "ended"}

# Regex patterns for validation
URL_PATTERN = re.compile(r"^https?://")
DISCORD_WEBHOOK_PATTERN = re.compile(
    r"https://discord\.com/api/webhooks/\d{17,19}/[A-Za-z0-9_-]{68,}"
)
NOTIFIARR_WEBHOOK_PATTERN = re.compile(
    r"https://notifiarr\.com/api/v1/notification/passthrough/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
DISCORD_CHANNEL_ID_PATTERN = re.compile(r"^\d{17,19}$")


def get_config_path() -> Path:
    """Get the configuration file path.
    
    Returns:
        Path to the configuration file.
    """
    env_path = os.environ.get(CONFIG_PATH_ENV)
    if env_path:
        logger.debug(f"Using config path from environment: {env_path}")
        return Path(env_path)
    logger.debug(f"Using default config path: {DEFAULT_CONFIG_PATH}")
    return DEFAULT_CONFIG_PATH


def load_config() -> configparser.ConfigParser:
    """Load the configuration file.
    
    Returns:
        ConfigParser object with the configuration.
    """
    config_path = get_config_path()
    config = configparser.ConfigParser()
    # Preserve original key case (don't lowercase keys)
    config.optionxform = str
    
    if config_path.exists():
        config.read(config_path)
        logger.debug(f"Loaded configuration from {config_path}")
        logger.debug(f"Configuration sections: {config.sections()}")
    else:
        logger.warning(f"Configuration file not found at {config_path}, using empty config")
    
    return config


def save_config(config: configparser.ConfigParser) -> None:
    """Save the configuration to file.
    
    Args:
        config: ConfigParser object to save.
    """
    config_path = get_config_path()
    
    with open(config_path, "w") as f:
        config.write(f)
    
    logger.info(f"Configuration saved to {config_path}")


def config_to_dict(config: configparser.ConfigParser) -> dict[str, Any]:
    """Convert ConfigParser to a dictionary.
    
    Args:
        config: ConfigParser object to convert.
        
    Returns:
        Dictionary representation of the configuration.
    """
    result = {}
    for section in config.sections():
        result[section] = dict(config[section])
    return result


def validate_quotes(config: configparser.ConfigParser) -> list[str]:
    """Check that no configuration values contain quotes.
    
    Args:
        config: ConfigParser object to validate.
        
    Returns:
        List of error messages, empty if valid.
    """
    errors = []
    
    for section in config.sections():
        for key, value in config[section].items():
            if '"' in value or "'" in value:
                errors.append(
                    f'Configuration value for "{key}" in section [{section}] '
                    "contains quotes which are not allowed."
                )
    
    return errors


def validate_notification_config(config: configparser.ConfigParser) -> list[str]:
    """Validate the notification configuration.
    
    Args:
        config: ConfigParser object to validate.
        
    Returns:
        List of error messages, empty if valid.
    """
    errors = []
    
    # Check both Notifications and General sections (for backward compatibility)
    for section in ["Notifications", "General"]:
        if not config.has_section(section):
            continue
        
        section_config = dict(config[section])
        
        # Validate Discord webhook
        discord_webhook = section_config.get("DiscordWebhook", "").strip()
        if discord_webhook and not DISCORD_WEBHOOK_PATTERN.match(discord_webhook):
            errors.append(
                f"Discord Webhook in [{section}] is not formatted correctly. "
                'It should look like "https://discord.com/api/webhooks/Id123/Token123"'
            )
        
        # Validate Notifiarr Passthrough webhook
        notifiarr_webhook = section_config.get("NotifiarrPassthroughWebhook", "").strip()
        if notifiarr_webhook:
            if not NOTIFIARR_WEBHOOK_PATTERN.match(notifiarr_webhook):
                errors.append(
                    f"Notifiarr Passthrough Webhook in [{section}] is not formatted correctly. "
                    'It should look like "https://notifiarr.com/api/v1/notification/passthrough/uuid-uuid-uuid-uuid-uuid"'
                )
            
            # Check for channel ID if webhook is specified
            channel_id = section_config.get("NotifiarrPassthroughDiscordChannelId", "").strip()
            if not DISCORD_CHANNEL_ID_PATTERN.match(channel_id):
                errors.append(
                    f"Notifiarr Passthrough Discord Channel ID in [{section}] is not formatted correctly. "
                    "It should be a 17-19 digit number."
                )
    
    return errors


def validate_application_config(app_name: str, app_config: dict[str, str]) -> list[str]:
    """Validate an application configuration section.
    
    Args:
        app_name: Name of the application section.
        app_config: Dictionary of configuration values.
        
    Returns:
        List of error messages, empty if valid.
    """
    errors = []
    
    # Determine application type
    app_type = None
    for t in ["radarr", "sonarr", "lidarr", "readarr"]:
        if t in app_name.lower():
            app_type = t
            break
    
    if not app_type:
        errors.append(
            f'Cannot determine application type from "{app_name}". '
            "Name must contain one of: radarr, sonarr, lidarr, readarr"
        )
        return errors
    
    # Validate API Key (32 characters)
    api_key = app_config.get("ApiKey", "").strip()
    if len(api_key) != 32:
        errors.append(f'API Key for "{app_name}" is not 32 characters long')
    
    # Validate URL
    url = app_config.get("Url", "").strip()
    if not URL_PATTERN.match(url):
        errors.append(
            f'URL for "{app_name}" is not formatted correctly. '
            'It should start with "http://" or "https://"'
        )
    
    # Validate Count
    count = app_config.get("Count", "10").strip().lower()
    if count != "max":
        try:
            count_int = int(count)
            if count_int < 1:
                errors.append(
                    f'Count for "{app_name}" must be greater than 0 or "max"'
                )
        except ValueError:
            errors.append(
                f'Count for "{app_name}" must be an integer or "max"'
            )
    
    # Validate Monitored
    monitored = app_config.get("Monitored", "true").strip().lower()
    if monitored not in VALID_MONITORED_VALUES:
        errors.append(
            f'Monitored for "{app_name}" must be "true" or "false"'
        )
    
    # Validate Unattended
    unattended = app_config.get("Unattended", "false").strip().lower()
    if unattended not in VALID_UNATTENDED_VALUES:
        errors.append(
            f'Unattended for "{app_name}" must be "true" or "false"'
        )
    
    # Validate TagName (required)
    tag_name = app_config.get("TagName", "").strip()
    if not tag_name:
        errors.append(f'TagName must be specified for "{app_name}"')
    
    # Validate status based on application type
    if app_type == "radarr":
        movie_status = app_config.get("MovieStatus", "").strip().lower()
        if movie_status and movie_status not in VALID_MOVIE_STATUS:
            errors.append(
                f'MovieStatus for "{app_name}" is not valid. '
                f"Expected one of: {', '.join(VALID_MOVIE_STATUS)}"
            )
    
    elif app_type == "sonarr":
        series_status = app_config.get("SeriesStatus", "").strip().lower()
        if series_status and series_status not in VALID_SERIES_STATUS:
            errors.append(
                f'SeriesStatus for "{app_name}" is not valid. '
                f"Expected one of: {', '.join(VALID_SERIES_STATUS)}"
            )
    
    elif app_type == "lidarr":
        artist_status = app_config.get("ArtistStatus", "").strip().lower()
        if artist_status and artist_status not in VALID_ARTIST_STATUS:
            errors.append(
                f'ArtistStatus for "{app_name}" is not valid. '
                f"Expected one of: {', '.join(VALID_ARTIST_STATUS)}"
            )
    
    elif app_type == "readarr":
        author_status = app_config.get("AuthorStatus", "").strip().lower()
        if author_status and author_status not in VALID_AUTHOR_STATUS:
            errors.append(
                f'AuthorStatus for "{app_name}" is not valid. '
                f"Expected one of: {', '.join(VALID_AUTHOR_STATUS)}"
            )
    
    return errors


def validate_config(config: configparser.ConfigParser) -> list[str]:
    """Validate the entire configuration.
    
    Args:
        config: ConfigParser object to validate.
        
    Returns:
        List of all error messages, empty if valid.
    """
    logger.debug("Starting full configuration validation")
    errors = []
    
    # Check for quotes
    quote_errors = validate_quotes(config)
    if quote_errors:
        logger.debug(f"Quote validation errors: {quote_errors}")
    errors.extend(quote_errors)
    
    # Validate notifications
    notif_errors = validate_notification_config(config)
    if notif_errors:
        logger.debug(f"Notification config errors: {notif_errors}")
    errors.extend(notif_errors)
    
    # Validate each application section
    excluded_sections = {"Notifications", "General", "Scheduler"}
    for section in config.sections():
        if section not in excluded_sections:
            logger.debug(f"Validating application section: {section}")
            app_config = dict(config[section])
            app_errors = validate_application_config(section, app_config)
            if app_errors:
                logger.debug(f"Application '{section}' errors: {app_errors}")
            errors.extend(app_errors)
    
    logger.debug(f"Validation complete: {len(errors)} error(s) found")
    return errors


def get_scheduler_config(config: configparser.ConfigParser) -> dict[str, Any]:
    """Get scheduler configuration.
    
    Args:
        config: ConfigParser object.
        
    Returns:
        Dictionary with scheduler settings.
    """
    if not config.has_section("Scheduler"):
        logger.debug("No Scheduler section found, using defaults")
        return {"enabled": False, "interval_hours": 6}
    
    scheduler_config = dict(config["Scheduler"])
    logger.debug(f"Raw scheduler config: {scheduler_config}")
    
    result = {
        "enabled": scheduler_config.get("Enabled", "false").lower() == "true",
        "interval_hours": int(scheduler_config.get("IntervalHours", "6")),
    }
    logger.debug(f"Parsed scheduler config: {result}")
    return result


def create_default_config() -> configparser.ConfigParser:
    """Create a default configuration.
    
    Returns:
        ConfigParser with default values.
    """
    config = configparser.ConfigParser()
    
    config.add_section("Notifications")
    config.set("Notifications", "DiscordWebhook", "")
    config.set("Notifications", "NotifiarrPassthroughWebhook", "")
    config.set("Notifications", "NotifiarrPassthroughDiscordChannelId", "")
    
    config.add_section("Scheduler")
    config.set("Scheduler", "Enabled", "false")
    config.set("Scheduler", "IntervalHours", "6")
    
    return config

