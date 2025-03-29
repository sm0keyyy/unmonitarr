# Unmonitarr

A containerized Python tool that unmonitors media from specified release groups in both Radarr (movies) and Sonarr (TV series).

## Features

- **Unified Processing**: Works with both Radarr (movies) and Sonarr (TV shows)
- **Smart Release Group Detection**: Optimized for specific naming patterns with release groups
- **Parallel Processing**: Uses concurrent workers for faster execution
- **File Monitoring**: Only processes new/changed files since last run 
- **Containerized**: Easy deployment with Docker
- **Logs**: Detailed logging with rotation
- **Dry Run Mode**: Test without making changes

## Installation

### Using Docker (Recommended)

1. Clone the repository:
   ```
   git clone https://github.com/sm0keyyy/unmonitarr.git
   cd unmonitarr
   ```

2. Customize the configuration:
   ```
   cp unmonitarr_config.json config/unmonitarr_config.json
   ```
   Edit `config/unmonitarr_config.json` with your Radarr/Sonarr details.

3. Build and run with Docker Compose:
   ```
   docker-compose up -d
   ```

### Manual Installation

1. Clone the repository:
   ```
   git clone https://github.com/sm0keyyy/unmonitarr.git
   cd unmonitarr
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the script:
   ```
   python unmonitarr.py --config unmonitarr_config.json
   ```

## Configuration

Create a `unmonitarr_config.json` file with the following structure:

```json
{
  "general": {
    "release_groups": [
      "yify",
      "rarbg",
      "axxo",
      "ctrlhd"
    ],
    "dry_run": false,
    "debug": false,
    "concurrent": 4,
    "log_size": 10,
    "log_backups": 3,
    "monitoring": {
      "enabled": true,
      "interval": 3600
    }
  },
  "services": {
    "radarr": {
      "enabled": true,
      "host": "radarr",
      "port": 7878,
      "apikey": "your-radarr-api-key",
      "sample_size": 0
    },
    "sonarr": {
      "enabled": true,
      "host": "sonarr",
      "port": 8989,
      "apikey": "your-sonarr-api-key",
      "sample_size": 0,
      "season_filter": null
    }
  }
}
```

### Configuration Options

#### General Settings

- `release_groups`: List of release groups to target (case insensitive)
- `dry_run`: Set to `true` to test without making changes
- `debug`: Set to `true` for verbose logging
- `concurrent`: Number of concurrent workers (recommend 4-8)
- `log_size`: Maximum log file size in MB
- `log_backups`: Number of log file backups to keep
- `monitoring`: Settings for file monitoring mode
  - `enabled`: Enable file monitoring mode
  - `interval`: Seconds between scans (default: 3600 = 1 hour)

#### Service-Specific Settings

Each service (Radarr, Sonarr) has these options:

- `enabled`: Set to `true` to enable this service
- `host`: Hostname or IP address
- `port`: Port number
- `apikey`: API key for authentication
- `sample_size`: Limit processing to this many items (for testing, 0 = unlimited)
- `season_filter`: (Sonarr only) Only process this season number (null = all seasons)

## Running Modes

### Standard Mode

Processes all media in a one-time scan:

```
python unmonitarr.py --config unmonitarr_config.json
```

### Monitoring Mode

Only processes new/changed files since last run:

```
python unmonitarr.py --config unmonitarr_config.json --monitor
```

To force a full scan but still save state for future incremental scans:

```
python unmonitarr.py --config unmonitarr_config.json --monitor --force-full-scan
```

## Docker Environment Variables

When running in Docker, you can use these environment variables:

- `MONITOR_MODE`: Set to `true` to enable monitoring mode
- `MONITOR_INTERVAL`: Seconds between scans (default: 3600)
- `CONFIG_PATH`: Path to config file (default: `/config/unmonitarr_config.json`)
- `STATE_FILE`: Path to state file (default: `/config/unmonitarr_state.json`)
- `TZ`: Timezone (default: UTC)

## How It Works

		IMPORTANT: use the standard TRaSH guides recommendation for the media naming scheme in Radarr/Sonarr

		Radarr: {Movie CleanTitle} {(Release Year)} {imdb-{ImdbId}} {edition-{Edition Tags}} {[Custom Formats]}{[Quality Full]}{[MediaInfo 3D]}{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[Mediainfo VideoCodec]}{-Release Group}
		Sonarr: Standard: {Movie CleanTitle} {(Release Year)} {imdb-{ImdbId}} {edition-{Edition Tags}} {[Custom Formats]}{[Quality Full]}{[MediaInfo 3D]}{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[Mediainfo VideoCodec]}{-Release Group}
			Daily: {Series TitleYear} - {Air-Date} - {Episode CleanTitle} [{Custom Formats }{Quality Full}]{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[MediaInfo VideoCodec]}{-Release Group}

1. Fetches media items from Radarr/Sonarr APIs
2. In monitoring mode, only processes items added/updated since last run
3. Extracts release group from file paths using pattern matching 
4. If a release group matches your target list, unmonitors the item
5. Saves state of processed files to avoid redundant processing

## License

MIT
