# Unmonitarr

> 🚀 Intelligent Media Library Cleanup for Radarr and Sonarr

## 🚧 Requirements & Warnings

### System Requirements
- Python 3.11+
- Radarr/Sonarr with API access
- Docker (optional)

### ⚠️ Critical Naming Convention Warning

> **IMPORTANT**: This tool requires specific media naming patterns to function correctly!

You **MUST** use the standard [TRaSH guides](https://trash-guides.info/) recommended naming schemes:

**Radarr (Movies):**  
```
{Movie CleanTitle} {(Release Year)} {imdb-{ImdbId}} {edition-{Edition Tags}} {[Custom Formats]}{[Quality Full]}{[MediaInfo 3D]}{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[Mediainfo VideoCodec]}{-Release Group}
```

**Sonarr (TV Series):**  
Standard Episodes:
```
{Series TitleYear} - {Season}x{Episode} - {Episode CleanTitle} [{Custom Formats]}{[Quality Full]}{[MediaInfo VideoDynamicRangeType]}{[Mediainfo AudioCodec}{ Mediainfo AudioChannels]}{[MediaInfo VideoCodec]}{-Release Group}
```

## 📝 Overview

Unmonitarr is a powerful Python tool designed to automatically unmonitor media files from specific release groups across Radarr and Sonarr, with intelligent hierarchical processing.

## ✨ Key Features

- **Hierarchical Unmonitoring**: Systematically unmonitors media at multiple levels
  - Individual episodes
  - Complete seasons
  - Entire series/collections
- **Smart Release Group Detection**: Advanced pattern matching for complex filename formats
- **Parallel Processing**: Efficient concurrent media scanning
- **Flexible Configuration**: Highly customizable via JSON config
- **Monitoring Mode**: Continuous background scanning
- **Preserves Future Monitoring**: Ensures new seasons/releases remain tracked

## 🛠 Installation

### Docker (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/sm0keyyy/unmonitarr.git
   cd unmonitarr
   ```

2. Run the setup script:
   ```bash
   bash setup.sh
   ```

3. Edit the configuration:
   ```bash
   nano config/unmonitarr_config.json
   ```

4. Start the container:
   ```bash
   docker-compose up -d
   ```

### Manual Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure `unmonitarr_config.json`
4. Run the script:
   ```bash
   python unmonitarr.py --config config/unmonitarr_config.json
   ```

## 🔧 Configuration

Customize your `unmonitarr_config.json`:

```json
{
  "general": {
    "release_groups": ["yify", "rarbg", "axxo"],
    "dry_run": false,
    "debug": false,
    "concurrent": 4
  },
  "services": {
    "radarr": {
      "enabled": true,
      "host": "localhost",
      "port": 7878,
      "apikey": "your-radarr-api-key"
    },
    "sonarr": {
      "enabled": true,
      "host": "localhost",
      "port": 8989,
      "apikey": "your-sonarr-api-key"
    }
  }
}
```

## 🚀 Running Modes

### Standard Mode
```bash
python unmonitarr.py --config config/unmonitarr_config.json
```

### Monitoring Mode
```bash
python unmonitarr.py --config config/unmonitarr_config.json --monitor
```

## 🔍 How It Works

Unmonitarr implements a sophisticated hierarchical unmonitoring strategy:

1. **Episode Level**: Unmonitor individual episodes matching target release groups
2. **Season Level**: When ALL episodes in a season are unmonitored, unmonitor the season
3. **Series Level**: When ALL seasons with files are unmonitored, unmonitor the entire series while preserving settings for new seasons

## 📄 License

MIT License

## 🤝 Contributing

Contributions welcome! Please open issues or submit pull requests.
