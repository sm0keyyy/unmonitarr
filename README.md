# Unmonitarr

> ⚠️ **IMPORTANT**: This tool requires specific naming patterns to work correctly!
> 
> You **MUST** use the standard [TRaSH guides](https://trash-guides.info/) recommended naming scheme:
> 
> **Radarr (Movies):**  
> ```
> {Movie CleanTitle} {(Release Year)} {imdb-{ImdbId}} {edition-{Edition Tags}} {[Custom Formats]}{[Quality Full]}{[MediaInfo 3D]}{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[Mediainfo VideoCodec]}{-Release Group}
> ```
> 
> **Sonarr (TV Series):**  
> Standard Episodes:
> ```
> {Movie CleanTitle} {(Release Year)} {imdb-{ImdbId}} {edition-{Edition Tags}} {[Custom Formats]}{[Quality Full]}{[MediaInfo 3D]}{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[Mediainfo VideoCodec]}{-Release Group}
> ```
> 
> Daily Episodes:
> ```
> {Series TitleYear} - {Air-Date} - {Episode CleanTitle} [{Custom Formats }{Quality Full}]{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[MediaInfo VideoCodec]}{-Release Group}
> ```

A containerized Python tool that unmonitors media from specified release groups in both Radarr (movies) and Sonarr (TV series), with advanced hierarchical unmonitoring capabilities.

## Features

- **Hierarchical Unmonitoring**: Intelligently cascades unmonitoring from episodes → seasons → series
- **New Season Protection**: Preserves monitoring for future seasons even when unmonitoring a series
- **Unified Processing**: Works with both Radarr (movies) and Sonarr (TV shows)
- **Smart Release Group Detection**: Advanced pattern matching for virtually any naming convention
- **Parallel Processing**: Uses concurrent workers for faster execution
- **Intelligent Monitoring**: Only processes files that haven't been unmonitored yet
- **Self-Healing Config**: Automatically detects and fixes common configuration issues
- **Containerized**: Easy deployment with Docker
- **Comprehensive Logging**: Detailed, actionable logs with hierarchical tracking
- **Dry Run Mode**: Test pattern matching without making changes

## Smart Hierarchical Unmonitoring

Unmonitarr now features an intelligent hierarchical unmonitoring system that respects the natural structure of your media library:

1. **Episode Level**: Individual episodes matching target release groups are unmonitored
2. **Season Level**: When ALL episodes in a season are unmonitored, the season itself is unmonitored
3. **Series Level**: When ALL seasons with files are unmonitored, the series is unmonitored

This creates a clean, organized library while preserving your ability to automatically monitor new seasons as they're announced.

## Real-World Example

Below is a sample output of Unmonitarr with hierarchical unmonitoring in action:

```
2025-03-30 09:23:16,426 - INFO - Match! Release group 'SbR' found in 12 Years a Slave
2025-03-30 09:23:16,427 - INFO - Match! Release group 'DON' found in 12 Angry Men
2025-03-30 09:23:16,434 - INFO - Unmonitoring: 12 Years a Slave
2025-03-30 09:23:16,442 - INFO - Unmonitoring: 12 Angry Men

... [processing continues] ...

2025-03-30 09:23:50,492 - INFO - Using 6 concurrent workers to process episodes for Band of Brothers
2025-03-30 09:23:50,507 - INFO - Match! Release group 'D-Z0N3' found in S1E2 - Day of Days
2025-03-30 09:23:50,515 - INFO - Unmonitoring: S1E2 - Day of Days
2025-03-30 09:23:50,520 - INFO - Match! Release group 'D-Z0N3' found in S1E3 - Carentan
2025-03-30 09:23:50,528 - INFO - Unmonitoring: S1E3 - Carentan
2025-03-30 09:23:51,142 - INFO - All 10 episodes in season 1 are unmonitored. Unmonitoring season.
2025-03-30 09:23:51,356 - INFO - Successfully unmonitored season 1 of Band of Brothers
2025-03-30 09:23:51,420 - INFO - All 1 seasons with files in Band of Brothers have been unmonitored. Unmonitoring entire series.
2025-03-30 09:23:51,620 - INFO - Successfully unmonitored series: Band of Brothers (new seasons will still be monitored)

... [processing continues] ...

2025-03-30 09:24:42,750 - INFO - === Hierarchical Unmonitoring Summary ===
2025-03-30 09:24:42,751 - INFO - Unmonitored 553 episodes across 87 series
2025-03-30 09:24:42,752 - INFO - Unmonitored 43 complete seasons
2025-03-30 09:24:42,753 - INFO - Unmonitored 12 entire series (preserving new season monitoring)
2025-03-30 09:24:42,757 - INFO - === Combined Results ===
2025-03-30 09:24:42,758 - INFO - Radarr: Unmonitored 553 movies
2025-03-30 09:24:42,759 - INFO - Sonarr: Unmonitored 553 episodes
2025-03-30 09:24:42,759 - INFO - Sonarr: Unmonitored 43 complete seasons
2025-03-30 09:24:42,759 - INFO - Sonarr: Unmonitored 12 entire series (preserving new season monitoring)
2025-03-30 09:24:42,772 - INFO - === Initial Scan Completed in 87.83 seconds ===
```

In this example, Unmonitarr:
- Identified and unmonitored movies from target release groups
- Unmonitored individual episodes from matching release groups
- Detected when all episodes in a season were unmonitored and unmonitored the entire season
- Detected when all seasons in a series were unmonitored and unmonitored the entire series
- Preserved the ability to monitor new seasons automatically
- Provided detailed hierarchical reporting at each level
- Completed processing in under 90 seconds

## Installation

### Using the Setup Script (Recommended)

The easiest way to get started is to use the provided setup script:

1. Clone the repository into your app data directory (where you keep your Docker configurations):
   ```bash
   # Navigate to your app data directory, for example:
   cd /path/to/your/docker/appdata
   
   # Clone the repository into a new unmonitarr directory
   git clone https://github.com/sm0keyyy/unmonitarr.git
   cd unmonitarr
   ```

2. Run the setup script:
   ```bash
   bash setup.sh
   ```

   This script automatically:
   - Creates the necessary directory structure (config, logs)
   - Generates a default configuration file
   - Creates required Docker files (docker-compose.yml, Dockerfile)
   - Sets up the Python requirements
   - Prepares the application for deployment

3. Edit the configuration:
   ```bash
   nano config/unmonitarr_config.json
   ```
   **Important**: You must add your Radarr/Sonarr API keys before running the container.

4. Build and start the container:
   ```bash
   docker-compose up -d
   ```

### Using Docker Manually

1. Clone the repository into your app data directory:
   ```bash
   # Navigate to your app data directory
   cd /path/to/your/docker/appdata
   
   # Clone the repository
   git clone https://github.com/sm0keyyy/unmonitarr.git
   cd unmonitarr
   ```

2. Create and customize the configuration:
   ```bash
   # Create config directory if it doesn't exist
   mkdir -p config
   
   # Create a default config
   cp unmonitarr_config.json config/unmonitarr_config.json
   
   # Edit the config file
   nano config/unmonitarr_config.json
   ```

3. Build and run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

### Manual Installation

1. Clone the repository:
   ```bash
   # Choose an appropriate location for the application
   cd /path/to/install/directory
   
   # Clone the repository
   git clone https://github.com/sm0keyyy/unmonitarr.git
   cd unmonitarr
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a configuration file:
   ```bash
   # Copy the example configuration
   cp unmonitarr_config.json config/unmonitarr_config.json
   
   # Edit as needed
   nano config/unmonitarr_config.json
   ```

4. Run the script:
   ```bash
   python unmonitarr.py --config config/unmonitarr_config.json
   ```

## Configuration

Create a `unmonitarr_config.json` file with the following structure (Edit as needed):

```json
{
  "general": {
    "release_groups": [
      "yify",
      "rarbg",
      "axxo",
      "ctrlhd",
      "iFT",
      "NTb",
      "FLUX",
      "D-Z0N3",
      "DON",
      "c0kE",
      "TayTO",
      "EbP",
      "SbR",
      "NCmt"
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
      "host": "localhost-or-ip",
      "port": 7878,
      "apikey": "your-radarr-api-key",
      "sample_size": 0
    },
    "sonarr": {
      "enabled": true,
      "host": "localhost-or-ip",
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
  - **Important**: Each group must be a separate list item, NOT a comma-separated string
  - Example: `["yify", "rarbg"]` is correct, `["yify,rarbg"]` is incorrect
  - Case-insensitive matching lets you list them as shown above
- `dry_run`: Set to `true` to test without making changes
- `debug`: Set to `true` for verbose logging (helpful for troubleshooting release group detection)
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

```bash
python unmonitarr.py --config config/unmonitarr_config.json
```

### Monitoring Mode

Only processes new/changed files or files that haven't been unmonitored yet:

```bash
python unmonitarr.py --config config/unmonitarr_config.json --monitor
```

To force a full scan but still save state for future incremental scans:

```bash
python unmonitarr.py --config config/unmonitarr_config.json --monitor --force-full-scan
```

## Docker Environment Variables

When running in Docker, you can use these environment variables:

- `MONITOR_MODE`: Set to `true` to enable monitoring mode
- `MONITOR_INTERVAL`: Seconds between scans (default: 3600)
- `CONFIG_PATH`: Path to config file (default: `/config/unmonitarr_config.json`)
- `STATE_FILE`: Path to state file (default: `/config/unmonitarr_state.json`)
- `TZ`: Timezone (default: UTC)

## How It Works

### Hierarchical Unmonitoring Logic

The hierarchical unmonitoring system follows a bottom-up approach:

1. **Episode Level**: 
   - Unmonitarr identifies episodes that match your target release groups
   - These individual episodes are unmonitored first

2. **Season Level**:
   - After processing episodes, Unmonitarr checks each season
   - If ALL episodes with files in a season are unmonitored, the season itself is unmonitored
   - This keeps your Sonarr interface cleaner by hiding completed seasons

3. **Series Level**:
   - After processing seasons, Unmonitarr evaluates the entire series
   - If ALL seasons with files are unmonitored, the series itself is unmonitored
   - Crucially, the script preserves settings to ensure new seasons are still monitored
   - This gives you the best of both worlds: a clean current library, with automatic handling of future content

### Core Features

1. **Smart Configuration**: Detects and fixes common configuration issues automatically
2. **API Integration**: Fetches media items from Radarr/Sonarr APIs
3. **Pattern Recognition**: Uses multiple specialized regex patterns to identify release groups
4. **Intelligent Monitoring**: In monitoring mode, only processes:
   - New items added since last scan
   - Updated items with changes
   - Items that haven't been unmonitored yet
5. **Hierarchical Unmonitoring**: Cascades unmonitoring actions from episodes → seasons → series
6. **Future-Proof**: Preserves the ability to monitor new seasons automatically
7. **State Tracking**: Maintains separate tracking for processed vs. unmonitored items at all levels
8. **Timezone-Safe**: Handles datetime comparison issues between timezone-aware and naive timestamps

### Enhanced State Tracking

Unmonitarr maintains sophisticated state tracking at all hierarchical levels:

```json
{
  "sonarr": {
    "unmonitored_episode_ids": [123, 456, ...],  // Episode level
    "unmonitored_seasons": {                     // Season level
      "10": [1, 2],     // Series 10, seasons 1 and 2 unmonitored
      "20": [1, 3, 4]   // Series 20, seasons 1, 3, 4 unmonitored 
    },
    "unmonitored_ids": [10, 30, ...]            // Series level
  }
}
```

## Advanced Features

### Enhanced Release Group Detection

Unmonitarr can detect release groups in numerous formats:

- Standard hyphenated: `Movie-RELEASEGROUP`
- Bracketed: `Movie [RELEASEGROUP]`
- Dot-separated: `Movie.2023.1080p.RELEASEGROUP`
- Scene-style: `Movie.2023.1080p.BluRay.x264-RELEASEGROUP`
- With quality tags: `Movie [1080p] [BluRay] [x264]-RELEASEGROUP`

The advanced pattern matching even works with release groups that contain hyphens or special characters, as seen with 'D-Z0N3' in the logs.

### Performance

The tool is optimized for speed and efficiency. As shown in the example output, it can process thousands of media items in under 90 seconds, handling all levels of the hierarchy simultaneously.

### State Management

Subsequent scans are even faster due to intelligent state tracking:

```
2025-03-30 09:24:46,265 - INFO - Radarr: Unmonitored 0 movies
2025-03-30 09:24:46,265 - INFO - Sonarr: Unmonitored 0 episodes
2025-03-30 09:24:46,265 - INFO - Sonarr: Unmonitored 0 seasons
2025-03-30 09:24:46,265 - INFO - Sonarr: Unmonitored 0 series
2025-03-30 09:24:46,276 - INFO - === Monitoring Scan Completed in 3.50 seconds ===
```

## Troubleshooting

### Release Groups Not Being Detected

1. Enable debug mode in your config file:
   ```json
   "debug": true
   ```

2. Look for log entries showing filename analysis:
   ```
   DEBUG - Analyzing filename for release group: Movie.Title.2023.1080p.WEB-DL.x264-RELEASEGROUP
   ```

3. Confirm your release groups are configured correctly (as separate list items):
   ```json
   "release_groups": [
     "releasegroup",
     "another-group"
   ]
   ```

### Hierarchical Unmonitoring Not Working

1. Ensure you have set up monitoring with full state tracking:
   ```bash
   python unmonitarr.py --config config/unmonitarr_config.json --monitor
   ```

2. Check debug logs to see if all episodes in a season have been unmonitored:
   ```
   DEBUG - Found 10/10 episodes with files for season 1
   DEBUG - Calculating unmonitored episodes in season 1
   ```

3. Series will only be unmonitored when ALL seasons with files are unmonitored

### Datetime Comparison Errors

If you see errors like:
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

The latest version (2.0+) of Unmonitarr should automatically handle this issue by normalizing timezone information.

## License

MIT
