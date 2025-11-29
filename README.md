# Pristinarr

Pristinarr is a web application that automates the manual searching of media items in your Radarr, Sonarr, Lidarr, or Readarr library. It searches for items that haven't been tagged yet, helping you find upgrades based on your Custom Format scoring.

## Features

- **Web Interface**: Configure and manage your applications through an intuitive web UI
- **Scheduled Runs**: Automatically search for upgrades on a configurable schedule
- **Multiple Applications**: Support for Radarr, Sonarr, Lidarr, and Readarr (including multiple instances)
- **Notifications**: Discord and Notifiarr integration for run notifications
- **Unattended Mode**: Automatically restart the search cycle when complete
- **Dry Run Mode**: Preview what would be searched without making changes
- **Docker Ready**: Easy deployment with Docker and Docker Compose

## Quick Start

### Docker Compose (Recommended)

1. Create a directory for Pristinarr:
   ```bash
   mkdir pristinarr && cd pristinarr
   ```

2. Download the docker-compose.yml:
   ```bash
   curl -O https://raw.githubusercontent.com/tldev/pristinarr/main/docker-compose.yml
   ```

3. Create a config directory:
   ```bash
   mkdir config
   ```

4. Start the container:
   ```bash
   docker-compose up -d
   ```

5. Open http://localhost:8080 in your browser to configure your applications.

### Docker Run

```bash
docker run -d \
  --name pristinarr \
  -p 8080:8080 \
  -v ./config:/config \
  --restart unless-stopped \
  ghcr.io/tldev/pristinarr:latest
```

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/tldev/pristinarr.git
   cd pristinarr
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
   ```

5. Open http://localhost:8080 in your browser.

## Configuration

### Web Interface

The easiest way to configure Pristinarr is through the web interface at http://localhost:8080/config. You can:

- Add and configure Starr applications
- Set up Discord and Notifiarr notifications
- Configure the scheduler for automatic runs
- Test connections to your applications

### Configuration File

Pristinarr uses an INI configuration file located at `/config/pristinarr.conf` (in Docker) or `./pristinarr.conf` (local).

Example configuration:

```ini
[Notifications]
DiscordWebhook=https://discord.com/api/webhooks/123/abc
NotifiarrPassthroughWebhook=
NotifiarrPassthroughDiscordChannelId=

[Scheduler]
Enabled=true
IntervalHours=6

[Radarr]
ApiKey=your-32-character-api-key-here
Url=http://localhost:7878
TagName=pristinarr
Count=10
Monitored=true
Unattended=false
IgnoreTag=
QualityProfileName=
MovieStatus=released

[Sonarr]
ApiKey=your-32-character-api-key-here
Url=http://localhost:8989
TagName=pristinarr
Count=5
Monitored=true
Unattended=false
SeriesStatus=
```

### Configuration Options

#### Scheduler

| Attribute | Description | Default | Values |
|-----------|-------------|---------|--------|
| Enabled | Enable automatic scheduled runs | false | true/false |
| IntervalHours | Hours between each run | 6 | 1-168 |

#### Application Settings

| Attribute | Description | Default | Values |
|-----------|-------------|---------|--------|
| ApiKey | API Key from Settings → General | (required) | 32-character string |
| Url | Application URL with port | (required) | http(s)://host:port |
| TagName | Tag applied to searched media | (required) | any string |
| Count | Number of items to search per run | 10 | integer or "max" |
| Monitored | Only search monitored items | true | true/false |
| Unattended | Auto-restart when all items are tagged | false | true/false |
| IgnoreTag | Skip items with this tag | (empty) | tag name |
| QualityProfileName | Only search items with this profile | (empty) | profile name |

#### Status Filters (Application-specific)

| Application | Attribute | Values |
|-------------|-----------|--------|
| Radarr | MovieStatus | tba, announced, inCinemas, released |
| Sonarr | SeriesStatus | continuing, ended, upcoming |
| Lidarr | ArtistStatus | continuing, ended |
| Readarr | AuthorStatus | continuing, ended |

#### Notifications

| Attribute | Description |
|-----------|-------------|
| DiscordWebhook | Discord webhook URL |
| NotifiarrPassthroughWebhook | Notifiarr passthrough webhook URL |
| NotifiarrPassthroughDiscordChannelId | Discord channel ID for Notifiarr |

## API Endpoints

Pristinarr provides a REST API for programmatic access:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/health | Health check |
| GET | /api/config | Get current configuration |
| GET | /api/history | Get run history |
| GET | /api/scheduler/status | Get scheduler status |
| POST | /api/run | Run all applications |
| POST | /api/run/{app_name} | Run specific application |
| POST | /api/run/{app_name}?dry_run=true | Dry run for specific application |
| GET | /api/test/{app_name} | Test connection to application |
| POST | /api/config/application/{app_name} | Save application config |
| DELETE | /api/config/application/{app_name} | Delete application |
| POST | /api/config/notifications | Save notification config |
| POST | /api/config/scheduler | Save scheduler config |

## Requirements

- Python 3.12+ (for local development)
- Docker (for container deployment)
- Radarr/Sonarr/Lidarr/Readarr with API access

### Starr Application Setup

For best results, configure your Starr applications:

- **Radarr**: Settings → Profiles → Quality Profile → Set "Upgrade Until Custom Format Score" to at least 10000
- **Sonarr v4**: Settings → Profiles → Quality Profile → Set "Upgrade Until Custom Format Score" to at least 10000
- **Lidarr**: Settings → Profiles → Quality Profile → Set "Upgrade Until Custom Format Score" to at least 10000
- **Readarr**: Settings → Profiles → Quality Profile → Set "Upgrade Until Custom Format Score" to at least 10000

> **Tip:** Use [TRaSH Guides](https://trash-guides.info/) for optimal Custom Format configuration.

## Troubleshooting

### Connection Issues

- Verify the URL includes the correct port
- Ensure the API key is correct (32 characters)
- Check that the application is accessible from where Pristinarr is running
- If using Docker, use the container network or host IP, not `localhost`

### Nothing Being Searched

- Check that you have media without the configured tag
- Verify the status filter matches your media
- Ensure "Monitored" setting matches your media's monitored status

### Logs

View logs in Docker:
```bash
docker logs pristinarr
```

Or check the Logs page in the web interface at http://localhost:8080/logs

## License

MIT License - See LICENSE file for details.

## Credits

- Original concept from [Upgradinatorr](https://github.com/angrycuban13/Just-A-Bunch-Of-Starr-Scripts/tree/main/Upgradinatorr) PowerShell script by [angrycuban13](https://github.com/angrycuban13)
