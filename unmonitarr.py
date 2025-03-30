#!/usr/bin/env python3
"""
Unmonitarr - Universal Unmonitor Script for Radarr/Sonarr

A unified script that unmonitors media from specified release groups in 
both Radarr (movies) and Sonarr (TV series). Optimized for specific naming 
patterns with release groups at the end preceded by a hyphen.
Includes parallel processing, log rotation, and file system monitoring.

Configuration is done via a JSON config file.
"""

import requests
import json
import re
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import argparse
import sys
import concurrent.futures
from functools import partial
import hashlib
import shutil
from dateutil import parser as date_parser

# Configure logging - write to both rotating file in the script directory and console
script_dir = os.path.dirname(os.path.realpath(__file__))
log_file = os.path.join("/logs", "unmonitarr.log")
state_file = os.environ.get("STATE_FILE", os.path.join("/config", "unmonitarr_state.json"))

def setup_logging(debug_mode=False, max_size_mb=10, backup_count=3):
    """Configure logging with rotation and proper levels"""
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Create a custom formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Set up rotating file handler (10MB per file, keep 3 backups by default)
    max_bytes = max_size_mb * 1024 * 1024
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=max_bytes, 
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add our handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

def parse_arguments():
    """Parse command line arguments for config file path and operating mode"""
    parser = argparse.ArgumentParser(description="Unmonitor media from specified release groups in Radarr/Sonarr")
    parser.add_argument('--config', default=os.environ.get('CONFIG_PATH', 'unmonitarr_config.json'),
                        help="Path to the configuration file")
    parser.add_argument('--monitor', action='store_true',
                        help="Run in monitoring mode to track and process only new media files")
    parser.add_argument('--force-full-scan', action='store_true',
                        help="Force a full scan even in monitoring mode")
    return parser.parse_args()

def load_config(config_path):
    """Load configuration from JSON file with enhanced validation and fixing"""
    try:
        with open(config_path, 'r') as config_file:
            config_data = json.load(config_file)
        
        # Check and fix release_groups format if needed
        if 'general' in config_data and 'release_groups' in config_data['general']:
            # If the list contains only one item and it has commas, split it
            release_groups = config_data['general']['release_groups']
            if len(release_groups) == 1 and ',' in release_groups[0]:
                # Split the comma-separated string into a list
                fixed_groups = [group.strip() for group in release_groups[0].split(',')]
                config_data['general']['release_groups'] = fixed_groups
                
                logger.warning("Detected comma-separated release groups in a single string. " +
                               "Automatically splitting into separate items.")
                logger.warning(f"Original: {release_groups}")
                logger.warning(f"Fixed: {fixed_groups}")
                
                # Save the fixed config back to file
                with open(config_path, 'w') as config_file:
                    json.dump(config_data, config_file, indent=2)
                logger.warning(f"Updated config file saved to {config_path}")
            
        # Create the service-specific configs
        configs = {}
        
        # Process Radarr config
        if config_data.get('services', {}).get('radarr', {}).get('enabled', False):
            radarr_config = config_data['services']['radarr'].copy()
            radarr_config['service'] = 'radarr'
            radarr_config['release_groups'] = config_data['general']['release_groups']
            radarr_config['dry_run'] = config_data['general']['dry_run']
            radarr_config['debug'] = config_data['general']['debug']
            radarr_config['concurrent'] = config_data['general']['concurrent']
            radarr_config['log_size'] = config_data['general']['log_size']
            radarr_config['log_backups'] = config_data['general']['log_backups']
            radarr_config['monitoring'] = config_data['general'].get('monitoring', {})
            configs['radarr'] = radarr_config
            logger.info(f"Radarr configuration loaded: {radarr_config['host']}:{radarr_config['port']}")
        
        # Process Sonarr config
        if config_data.get('services', {}).get('sonarr', {}).get('enabled', False):
            sonarr_config = config_data['services']['sonarr'].copy()
            sonarr_config['service'] = 'sonarr'
            sonarr_config['release_groups'] = config_data['general']['release_groups']
            sonarr_config['dry_run'] = config_data['general']['dry_run']
            sonarr_config['debug'] = config_data['general']['debug']
            sonarr_config['concurrent'] = config_data['general']['concurrent']
            sonarr_config['log_size'] = config_data['general']['log_size']
            sonarr_config['log_backups'] = config_data['general']['log_backups']
            sonarr_config['monitoring'] = config_data['general'].get('monitoring', {})
            configs['sonarr'] = sonarr_config
            logger.info(f"Sonarr configuration loaded: {sonarr_config['host']}:{sonarr_config['port']}")
        
        # Log the shared settings with proper formatting
        for service, config in configs.items():
            # Format the release groups for better log readability
            groups_str = ", ".join(f'"{group}"' for group in config['release_groups'])
            logger.info(f"Targeting release groups for {service}: [{groups_str}]")
            logger.info(f"Using {config.get('concurrent', 1)} concurrent workers")
            
        return configs
        
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error parsing config file: {str(e)}")
        raise
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise

def get_api_url(config):
    """Build base API URL from configuration"""
    return f"http://{config['host']}:{config['port']}/api/v3"

def get_headers(config):
    """Build API request headers"""
    return {
        "X-Api-Key": config['apikey'],
        "Content-Type": "application/json"
    }

def load_state():
    """Load the state from file or initialize a new empty state with enhanced tracking"""
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                state = json.load(f)
                
                # Upgrade old state format if necessary
                if 'radarr' in state and 'unmonitored_ids' not in state['radarr']:
                    state['radarr']['unmonitored_ids'] = []
                if 'sonarr' in state and 'unmonitored_ids' not in state['sonarr']:
                    state['sonarr']['unmonitored_ids'] = []
                if 'sonarr' in state and 'unmonitored_episode_ids' not in state['sonarr']:
                    state['sonarr']['unmonitored_episode_ids'] = []
                    
                logger.info(f"Loaded state file from {state_file}")
                return state
        else:
            logger.info(f"No state file found, initializing new state")
            return {
                'last_scan': None,
                'radarr': {
                    'processed_ids': [],
                    'unmonitored_ids': []  # Track actually unmonitored IDs
                },
                'sonarr': {
                    'processed_ids': [], 
                    'processed_episode_ids': [],
                    'unmonitored_ids': [],  # Track actually unmonitored series IDs
                    'unmonitored_episode_ids': []  # Track actually unmonitored episode IDs
                }
            }
    except Exception as e:
        logger.error(f"Error loading state file: {str(e)}")
        # Return a new, empty state on error
        return {
            'last_scan': None,
            'radarr': {
                'processed_ids': [],
                'unmonitored_ids': []
            },
            'sonarr': {
                'processed_ids': [], 
                'processed_episode_ids': [],
                'unmonitored_ids': [],
                'unmonitored_episode_ids': []
            }
        }

def save_state(state):
    """Save the current state to file"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        # Create a backup of the current state file if it exists
        if os.path.exists(state_file):
            backup_file = f"{state_file}.bak"
            shutil.copy2(state_file, backup_file)
            
        # Update the last scan timestamp
        state['last_scan'] = datetime.now().isoformat()
        
        # Write the new state
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
            logger.info(f"Saved state file to {state_file}")
    except Exception as e:
        logger.error(f"Error saving state file: {str(e)}")

def fetch_all_media(config):
    """Fetch all media items from Radarr or Sonarr"""
    api_url = get_api_url(config)
    headers = get_headers(config)
    
    endpoint = "movie" if config['service'] == 'radarr' else "series"
    url = f"{api_url}/{endpoint}"
    
    logger.info(f"Fetching all media items from {url}")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()  # Raise exception for 4XX/5XX responses
        media_items = response.json()
        
        # Apply sample size limit if configured
        if config.get('sample_size') and config['sample_size'] > 0:
            original_count = len(media_items)
            media_items = media_items[:config['sample_size']]
            logger.info(f"Limiting from {original_count} to {len(media_items)} items for testing")
            
        return media_items
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return []

def fetch_new_media(config, state, last_scan=None):
    """Fetch only new or updated media items since the last scan,
    skipping only items that were actually unmonitored"""
    
    if not last_scan:
        return fetch_all_media(config)
    
    api_url = get_api_url(config)
    headers = get_headers(config)
    
    # Convert ISO timestamp to date object for comparison
    last_scan_date = date_parser.parse(last_scan)
    # Ensure the datetime is timezone-naive for consistent comparison
    if last_scan_date.tzinfo is not None:
        last_scan_date = last_scan_date.replace(tzinfo=None)
    
    if config['service'] == 'radarr':
        # Fetch all movies
        all_media = fetch_all_media(config)
        
        # Filter to only include new or updated items, or items not yet unmonitored
        new_media = []
        for item in all_media:
            # Skip only if previously unmonitored - THIS IS THE KEY CHANGE
            if item['id'] in state['radarr'].get('unmonitored_ids', []):
                continue
                
            # If the file isn't monitored in Radarr already, skip it
            if not item.get('monitored', True):
                # Add to unmonitored list if not already there
                if item['id'] not in state['radarr'].get('unmonitored_ids', []):
                    state['radarr']['unmonitored_ids'].append(item['id'])
                continue
            
            # Include media with changes or new additions since last scan
            include_item = False
            
            # Check if media was added after the last scan
            if 'added' in item:
                added_date = date_parser.parse(item['added'])
                if added_date.tzinfo is not None:
                    added_date = added_date.replace(tzinfo=None)
                if added_date > last_scan_date:
                    include_item = True
            
            # Also include items with recent file changes
            if not include_item and 'movieFile' in item and item['movieFile'] and 'dateAdded' in item['movieFile']:
                file_date = date_parser.parse(item['movieFile']['dateAdded'])
                if file_date.tzinfo is not None:
                    file_date = file_date.replace(tzinfo=None)
                if file_date > last_scan_date:
                    include_item = True
            
            # Include items that haven't been processed before or have changes
            if include_item or item['id'] not in state['radarr'].get('processed_ids', []):
                new_media.append(item)
        
        logger.info(f"Found {len(new_media)} movies to process (new/updated/not unmonitored)")
        return new_media
        
    else:  # sonarr
        # Fetch all series
        all_series = fetch_all_media(config)
        
        # Get episodes added since last scan date or not yet unmonitored
        series_to_process = []
        for series in all_series:
            # Check if series was added recently
            include_series = False
            if 'added' in series:
                added_date = date_parser.parse(series['added'])
                if added_date.tzinfo is not None:
                    added_date = added_date.replace(tzinfo=None)
                if added_date > last_scan_date:
                    include_series = True
            
            # Check for episodes that need processing
            if not include_series:
                episodes = get_episodes(config, series['id'])
                needs_processing = False
                
                for episode in episodes:
                    # Skip episodes already marked as unmonitored
                    if episode['id'] in state['sonarr'].get('unmonitored_episode_ids', []):
                        continue
                        
                    # If already unmonitored in Sonarr, record it but skip
                    if not episode.get('monitored', True):
                        if episode['id'] not in state['sonarr'].get('unmonitored_episode_ids', []):
                            state['sonarr']['unmonitored_episode_ids'].append(episode['id'])
                        continue
                    
                    if not episode.get('hasFile', False) or not episode.get('episodeFileId'):
                        continue
                    
                    # New episode file added
                    if 'episodeFile' in episode and 'dateAdded' in episode['episodeFile']:
                        file_date = date_parser.parse(episode['episodeFile']['dateAdded'])
                        if file_date.tzinfo is not None:
                            file_date = file_date.replace(tzinfo=None)
                        if file_date > last_scan_date:
                            needs_processing = True
                            break
                    
                    # Episode hasn't been processed yet
                    if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
                        needs_processing = True
                        break
                
                if needs_processing:
                    include_series = True
            
            # Include new or unprocessed series
            if include_series or series['id'] not in state['sonarr'].get('processed_ids', []):
                series_to_process.append(series)
        
        logger.info(f"Found {len(series_to_process)} series to process (new/updated/not unmonitored)")
        return series_to_process

def get_file_details(config, media_id, file_id=None):
    """Get file details for a specific movie or series/episode"""
    api_url = get_api_url(config)
    headers = get_headers(config)
    
    if config['service'] == 'radarr':
        url = f"{api_url}/moviefile?movieId={media_id}"
    else:  # sonarr
        if file_id:
            # Get a specific episode file
            url = f"{api_url}/episodefile/{file_id}"
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return [response.json()]  # Return as a list for consistent handling
            except requests.exceptions.RequestException as e:
                if config.get('debug'):
                    logger.debug(f"Failed to get episode file {file_id}: {str(e)}")
                return []
        else:
            # Get all episode files for a series
            url = f"{api_url}/episodefile?seriesId={media_id}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get file details: {str(e)}")
        return []

def get_episodes(config, series_id, season_number=None):
    """Fetch episodes for a series, optionally filtered by season (Sonarr only)"""
    if config['service'] != 'sonarr':
        return []
        
    api_url = get_api_url(config)
    headers = get_headers(config)
    url = f"{api_url}/episode?seriesId={series_id}"
    
    # Add retry logic for more resilience
    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            episodes = response.json()
            
            # Filter by season if specified
            if season_number is not None:
                episodes = [ep for ep in episodes if ep.get('seasonNumber') == season_number]
                
            # Keep only episodes with files
            episodes_with_files = [ep for ep in episodes if ep.get('hasFile', False)]
            
            if config.get('debug'):
                logger.debug(f"Found {len(episodes_with_files)}/{len(episodes)} episodes with files")
                
            return episodes_with_files
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"API request failed, retrying in {retry_delay}s: {str(e)}")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed to get episodes after {max_retries} attempts: {str(e)}")
                return []

def get_release_group(file_path, config):
    """
    Extract release group from file path using enhanced pattern matching.
    
    Works with a wide variety of naming conventions including:
    - Standard: Movie.Title.2023.1080p.WEB-DL.DDP5.1.H.264-RELEASEGROUP
    - Hyphenated: Movie Title (2023) [1080p] [WEB-DL] [DDP5.1] [H.264]-RELEASEGROUP
    - Bracketed: Movie.Title.2023.1080p.BluRay.x264.[RELEASEGROUP]
    - Multiple tags: Movie.Title.2023.1080p.[HDR10].[DV].[DDP5.1]-RELEASEGROUP
    """
    # Get just the filename without the path
    filename = os.path.basename(file_path)
    
    # First, remove the file extension
    basename = os.path.splitext(filename)[0]
    
    if config.get('debug'):
        logger.debug(f"Analyzing filename for release group: {basename}")
    
    # For troubleshooting, extract and log the last portion of the filename
    # This helps identify patterns we might be missing
    last_segment = basename.split('-')[-1] if '-' in basename else ''
    if last_segment and config.get('debug'):
        logger.debug(f"Last segment after hyphen: {last_segment}")
    
    # Common pattern structures for release groups
    patterns = [
        # Primary pattern: Release group at end preceded by hyphen (most common)
        # Examples: "Movie Title-RELEASEGROUP", "Show.S01E01-RELEASEGROUP"
        r'-([A-Za-z0-9._-]+)$',
        
        # Bracket pattern: [RELEASEGROUP] at the end
        # Examples: "Movie Title [RELEASEGROUP]", "Show.S01E01 [RELEASEGROUP]"
        r'\[([A-Za-z0-9._-]+)\]$',
        
        # Dot separated pattern: ending with .RELEASEGROUP
        # Examples: "Movie.Title.2023.1080p.RELEASEGROUP", "Show.S01E01.RELEASEGROUP"
        r'\.([A-Za-z0-9_-]{2,})$',
        
        # Common format with multi brackets: tags then group
        # Examples: "Movie [1080p] [WEB-DL]-RELEASEGROUP"
        r'\][\s]*-[\s]*([A-Za-z0-9._-]+)$',
        
        # Common torrent format with dots
        # Examples: "Movie.Title.2023.1080p.WEB-DL.RELEASEGROUP"
        r'(?:480p|720p|1080p|2160p|4k|bluray|web-dl|webrip|hdtv|xvid|aac|ac3|dts|bd5|bd9|bd25|bd50|bd66|bd100)(?:\.[^.]+)*\.([A-Za-z0-9_-]{2,})$',
        
        # Scene naming convention
        # Examples: "Movie.Title.2023.1080p.WEB-DL.x264-RELEASEGROUP"
        r'(?:x264|x265|h264|h265|hevc|xvid)[\s.]*-[\s.]*([A-Za-z0-9._-]+)(?:\..*)?$',
        
        # Handle brackets in the middle with hyphen after
        # Examples: "Movie.Title.2023.[1080p]-RELEASEGROUP"
        r'\][\s]*-[\s]*([A-Za-z0-9._-]+)(?:\..*)?$',
        
        # Quality patterns with release groups
        # Examples: "Movie.Title.2023.1080p.RELEASEGROUP"
        r'(?:480p|720p|1080p|2160p)\.([A-Za-z0-9._-]{2,})$',
        
        # Very liberal pattern to catch almost anything after the last dot
        r'\.([A-Za-z0-9]{2,})$',
        
        # Fallback pattern for any group-like strings at the end
        # This is less precise but might catch edge cases
        r'(?:[\.\s\[\]\(\)\-]|^)([A-Za-z0-9]{2,})$'
    ]
    
    # Try each pattern in order of specificity
    for pattern in patterns:
        match = re.search(pattern, basename, re.IGNORECASE)
        if match:
            group = match.group(1)
            # Clean up the group name (remove trailing dots, etc)
            group = group.rstrip('.')
            
            if config.get('debug'):
                logger.debug(f"Found release group: {group} using pattern: {pattern}")
            return group
    
    # Special handling for specific scene/p2p naming conventions
    # This handles cases where the release group might be embedded in a complex pattern
    scene_pattern = r'(?:\.|\-|\[|\s)((?:AMIABLE|SPARKS|GECKOS|DRONES|EVO|YIFY|YTS|RARBG)\b.*?)(?:\.|\]|\[|\-|$)'
    match = re.search(scene_pattern, basename, re.IGNORECASE)
    if match:
        group = match.group(1)
        if config.get('debug'):
            logger.debug(f"Found release group using scene pattern: {group}")
        return group
        
    # Check for common abbreviations that might be release groups
    common_groups = ['yts', 'yify', 'rarbg', 'ettv', 'eztv', 'ctrlhd', 'ntb', 'web', 'web-dl']
    for group in common_groups:
        # Look for the group with word boundaries
        pattern = r'(?:^|\W)(' + re.escape(group) + r')(?:$|\W)'
        match = re.search(pattern, basename, re.IGNORECASE)
        if match:
            found_group = match.group(1)
            if config.get('debug'):
                logger.debug(f"Found common release group: {found_group}")
            return found_group
    
    # Handle potential multi-word groups with spaces
    space_pattern = r'-\s*([A-Za-z0-9]+(?: [A-Za-z0-9]+)+)$'
    match = re.search(space_pattern, basename)
    if match:
        group = match.group(1)
        if config.get('debug'):
            logger.debug(f"Found multi-word release group: {group}")
        return group
            
    if config.get('debug'):
        logger.debug(f"No release group found in: {basename}")
    return None

def unmonitor_media(config, media_item):
    """Unmonitor a media item in Radarr/Sonarr"""
    if config['dry_run']:
        logger.info(f"[DRY RUN] Would unmonitor: {media_item['title']}")
        return True
        
    api_url = get_api_url(config)
    headers = get_headers(config)
    
    # Clone the media item and update monitored status
    updated_item = media_item.copy()
    updated_item['monitored'] = False
    
    endpoint = "movie" if config['service'] == 'radarr' else "series"
    url = f"{api_url}/{endpoint}/{media_item['id']}"
    
    logger.info(f"Unmonitoring: {media_item['title']}")
    try:
        response = requests.put(url, headers=headers, json=updated_item, timeout=30)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to unmonitor {media_item['title']}: {str(e)}")
        return False

def process_series(config, series, target_groups, state):
    """Process a single series to check if episodes should be unmonitored (Sonarr only)
    
    IMPORTANT: This function only unmonitors individual episodes that match release groups,
    not the entire series. The series remains monitored.
    """
    series_id = series['id']
    series_title = series['title']
    
    # Get episodes filtered by season if specified
    season_filter = config.get('season_filter')
    episodes = get_episodes(config, series_id, season_filter)
    
    if not episodes:
        if config.get('debug'):
            logger.debug(f"No episodes found for: {series_title}")
            
        # Mark as processed even if no episodes found
        if series_id not in state['sonarr'].get('processed_ids', []):
            state['sonarr']['processed_ids'].append(series_id)
            
        return 0
    
    if config.get('debug'):
        logger.debug(f"Found {len(episodes)} episodes with files for {series_title}")
    
    # Set up parallel processing
    max_workers = config.get('concurrent', 1)
    unmonitored_count = 0
    
    if max_workers > 1:
        logger.info(f"Using {max_workers} concurrent workers to process episodes for {series_title}")
        
        # Create a partial function with the fixed arguments
        process_fn = partial(process_episode, config=config, target_groups=target_groups, state=state)
        
        # Use ThreadPoolExecutor for concurrent processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Map the function to the episodes and collect results
            results = list(executor.map(process_fn, episodes))
            unmonitored_count = results.count(True)
    else:
        # Use traditional sequential processing
        if config.get('debug'):
            logger.debug(f"Processing episodes sequentially for {series_title}")
            
        for episode in episodes:
            if process_episode(episode, config, target_groups, state):
                unmonitored_count += 1
    
    # Mark series as fully processed when done
    if series_id not in state['sonarr'].get('processed_ids', []):
        state['sonarr']['processed_ids'].append(series_id)
    
    # Log the results for this series
    if unmonitored_count > 0:
        action = "Would have unmonitored" if config['dry_run'] else "Unmonitored"
        logger.info(f"{action} {unmonitored_count} episodes in series: {series_title}")
    
    return unmonitored_count

def process_media_sonarr(config, state=None, monitoring_mode=False):
    """Process all series in Sonarr and unmonitor episodes from specified release groups"""
    if monitoring_mode and state and state.get('last_scan'):
        logger.info(f"Running in monitoring mode, only checking series with new/updated episodes since {state['last_scan']}")
        series_list = fetch_new_media(config, state, state['last_scan'])
    else:
        series_list = fetch_all_media(config)
        
    if not series_list:
        logger.info("No series found to process!")
        return 0
    
    logger.info(f"Found {len(series_list)} series to check")
    
    target_groups = [group.lower() for group in config['release_groups']]
    
    # Optional: Display the first few items to verify parsing works correctly
    if config.get('debug') and len(series_list) > 0:
        logger.debug(f"First series: {series_list[0]['title']}")
    
    # Track overall results
    total_unmonitored = 0
    series_affected = 0
    
    # Process each series
    for index, series in enumerate(series_list):
        logger.info(f"Processing {index+1}/{len(series_list)}: {series['title']}")
        
        unmonitored_count = process_series(config, series, target_groups, state if state else {'sonarr': {'processed_ids': [], 'processed_episode_ids': [], 'unmonitored_ids': [], 'unmonitored_episode_ids': []}})
        
        if unmonitored_count > 0:
            total_unmonitored += unmonitored_count
            series_affected += 1
        
        # Add a small delay between series to avoid overwhelming the API
        time.sleep(0.1)
    
    # Summary report
    action = "Would have unmonitored" if config['dry_run'] else "Unmonitored"
    logger.info(f"{action} {total_unmonitored} episodes across {series_affected} series from specified release groups")
    
    return total_unmonitored

def process_media(configs, monitoring_mode=False, force_full_scan=False):
    """Process media across all configured services"""
    # Load state if in monitoring mode
    state = load_state() if monitoring_mode else None
    
    # If force full scan is enabled, clear the processed IDs to reprocess everything
    if force_full_scan and state:
        logger.info("Forced full scan requested - will reprocess all media")
        state['radarr']['processed_ids'] = []
        state['sonarr']['processed_ids'] = []
        state['sonarr']['processed_episode_ids'] = []
    
    total_results = {}
    
    # Process Radarr if configured
    if 'radarr' in configs:
        logger.info("=== Processing Radarr ===")
        radarr_count = process_media_radarr(configs['radarr'], state, monitoring_mode)
        total_results['radarr'] = {
            'unmonitored_count': radarr_count,
            'type': 'movies'
        }
    
    # Process Sonarr if configured
    if 'sonarr' in configs:
        logger.info("=== Processing Sonarr ===")
        sonarr_count = process_media_sonarr(configs['sonarr'], state, monitoring_mode)
        total_results['sonarr'] = {
            'unmonitored_count': sonarr_count,
            'type': 'episodes'
        }
    
    # Print combined results
    logger.info("=== Combined Results ===")
    for service, results in total_results.items():
        action = "Would have unmonitored" if configs[service]['dry_run'] else "Unmonitored"
        logger.info(f"{service.capitalize()}: {action} {results['unmonitored_count']} {results['type']}")
    
    # Save state if in monitoring mode
    if monitoring_mode:
        save_state(state)
        
def run_monitor_loop(configs, interval=3600):
    """Run the script in continuous monitoring mode with the specified interval"""
    logger.info(f"Starting monitoring loop with {interval} second interval")
    
    while True:
        try:
            start_time = time.time()
            logger.info("=== Unmonitarr Monitoring Scan Started ===")
            
            process_media(configs, monitoring_mode=True)
            
            elapsed_time = time.time() - start_time
            logger.info(f"=== Monitoring Scan Completed in {elapsed_time:.2f} seconds ===")
            
            # Sleep until next interval
            next_scan = max(1, interval - elapsed_time)
            logger.info(f"Next scan scheduled in {next_scan:.0f} seconds")
            time.sleep(next_scan)
            
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}", exc_info=True)
            # Sleep for a minute and try again
            logger.info("Retrying in 60 seconds...")
            time.sleep(60)

def main():
    """Main entry point for the script"""
    try:
        args = parse_arguments()
        
        # Initialize basic logging first (will be updated after config is loaded)
        global logger
        logger = setup_logging(debug_mode=False)
        
        # Load configuration from file
        logger.info(f"Loading configuration from file: {args.config}")
        configs = load_config(args.config)
        
        # Update logging based on config settings
        # Use debug mode if any service has debug enabled
        debug_mode = any(config.get('debug', False) for config in configs.values())
        # Use the first service's log settings (they should be the same across services)
        first_config = next(iter(configs.values()))
        log_size = first_config.get('log_size', 10)
        log_backups = first_config.get('log_backups', 3)
        
        logger = setup_logging(
            debug_mode=debug_mode,
            max_size_mb=log_size,
            backup_count=log_backups
        )
        
        # Check if monitoring mode is enabled
        monitoring_mode = args.monitor or os.environ.get('MONITOR_MODE', '').lower() in ('true', 'yes', '1')
        
        # Get monitoring interval
        monitor_interval = int(os.environ.get('MONITOR_INTERVAL', 3600))  # Default: 1 hour
        
        # Run in different modes based on arguments
        if monitoring_mode:
            logger.info("Running in monitoring mode - will only process new/updated media")
            if args.force_full_scan:
                logger.info("Force full scan enabled - will process all media on first run")
            
            # Run once with monitoring mode
            start_time = time.time()
            logger.info("=== Unmonitarr Script Started (Monitoring Mode) ===")
            
            process_media(configs, monitoring_mode=True, force_full_scan=args.force_full_scan)
            
            elapsed_time = time.time() - start_time
            logger.info(f"=== Initial Scan Completed in {elapsed_time:.2f} seconds ===")
            
            # Start monitoring loop
            run_monitor_loop(configs, monitor_interval)
        else:
            # Run once in standard mode
            start_time = time.time()
            logger.info("=== Unmonitarr Script Started (Standard Mode) ===")
            
            process_media(configs)
            
            elapsed_time = time.time() - start_time
            logger.info(f"=== Unmonitarr Script Completed in {elapsed_time:.2f} seconds ===")
        
    except Exception as e:
        if 'logger' in globals():
            logger.error(f"An error occurred: {str(e)}", exc_info=True)
        else:
            print(f"An error occurred before logger was initialized: {str(e)}")
        sys.exit(1)

def process_media_radarr(config, state=None, monitoring_mode=False):
    """Process all movies in Radarr and unmonitor those from specified release groups"""
    if monitoring_mode and state and state.get('last_scan'):
        logger.info(f"Running in monitoring mode, only checking new/updated movies since {state['last_scan']}")
        movies = fetch_new_media(config, state, state['last_scan'])
    else:
        movies = fetch_all_media(config)
        
    if not movies:
        logger.info("No movies found to process!")
        return 0
    
    logger.info(f"Found {len(movies)} movies to check")
    
    target_groups = [group.lower() for group in config['release_groups']]
    
    # Optional: Display the first few items to verify parsing works correctly
    if config.get('debug') and len(movies) > 0:
        logger.debug(f"First movie: {movies[0]['title']}")
    
    # Set up parallel processing
    max_workers = config.get('concurrent', 1)
    unmonitored_count = 0
    
    if max_workers > 1:
        logger.info(f"Using {max_workers} concurrent workers to process movies")
        
        # Create a partial function with the fixed arguments
        process_fn = partial(process_movie, config=config, target_groups=target_groups, state=state if state else {'radarr': {'processed_ids': [], 'unmonitored_ids': []}})
        
        # Use ThreadPoolExecutor for concurrent processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Map the function to the movies and collect results
            results = list(executor.map(process_fn, movies))
            unmonitored_count = results.count(True)
    else:
        # Use traditional sequential processing
        logger.info("Processing movies sequentially")
        for movie in movies:
            if process_movie(movie, config, target_groups, state if state else {'radarr': {'processed_ids': [], 'unmonitored_ids': []}}):
                unmonitored_count += 1
    
    action = "Would have unmonitored" if config['dry_run'] else "Unmonitored"
    logger.info(f"{action} {unmonitored_count} movies from specified release groups")
    
    return unmonitored_count

def unmonitor_episode(config, episode):
    """Unmonitor a specific episode (Sonarr only)"""
    if config['service'] != 'sonarr':
        return False
        
    if config['dry_run']:
        if config.get('debug'):
            logger.debug(f"[DRY RUN] Would unmonitor episode ID {episode['id']}")
        return True
        
    api_url = get_api_url(config)
    headers = get_headers(config)
    
    # Clone the episode and update monitored status
    updated_episode = episode.copy()
    updated_episode['monitored'] = False
    
    url = f"{api_url}/episode/{episode['id']}"
    
    episode_id = f"S{episode.get('seasonNumber', '?')}E{episode.get('episodeNumber', '?')}"
    logger.info(f"Unmonitoring: {episode_id} - {episode.get('title', 'Unknown')}")
    
    try:
        response = requests.put(url, headers=headers, json=updated_episode, timeout=30)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to unmonitor episode {episode['id']}: {str(e)}")
        return False

def process_movie(item, config, target_groups, state):
    """Process a single movie, tracking unmonitored status"""
    try:
        movie_title = item.get('title', 'Unknown')
        
        # Skip if already unmonitored in our tracking
        if item['id'] in state['radarr'].get('unmonitored_ids', []):
            if config.get('debug'):
                logger.debug(f"Skipping already unmonitored movie: {movie_title}")
            return False
            
        # Skip if not monitored in Radarr, but track it
        if not item.get('monitored', True):
            if config.get('debug'):
                logger.debug(f"Movie already unmonitored in Radarr: {movie_title}")
                
            # Add to our unmonitored tracking
            if item['id'] not in state['radarr'].get('unmonitored_ids', []):
                state['radarr']['unmonitored_ids'].append(item['id'])
                
            # Add to processed items for this run
            if item['id'] not in state['radarr'].get('processed_ids', []):
                state['radarr']['processed_ids'].append(item['id'])
                
            return False
            
        # Get file details for the movie
        files = get_file_details(config, item['id'])
        
        if config.get('debug') and not files:
            logger.debug(f"No files found for: {movie_title}")
            
            # Still mark as processed
            if item['id'] not in state['radarr'].get('processed_ids', []):
                state['radarr']['processed_ids'].append(item['id'])
                
            return False
        
        for file in files:
            if 'path' in file:
                if config.get('debug'):
                    logger.debug(f"Checking file: {file['path']}")
                    
                release_group = get_release_group(file['path'], config)
                
                if release_group:
                    # Normalize to lowercase for case-insensitive comparison
                    release_group_lower = release_group.lower()
                    
                    if config.get('debug'):
                        logger.debug(f"Comparing '{release_group_lower}' with targets: {target_groups}")
                    
                    if release_group_lower in target_groups:
                        logger.info(f"Match! Release group '{release_group}' found in {movie_title}")
                        
                        # Add to processed items list
                        if item['id'] not in state['radarr'].get('processed_ids', []):
                            state['radarr']['processed_ids'].append(item['id'])
                        
                        # Unmonitor the movie
                        if unmonitor_media(config, item):
                            # Add to unmonitored list only if successfully unmonitored
                            if item['id'] not in state['radarr'].get('unmonitored_ids', []):
                                state['radarr']['unmonitored_ids'].append(item['id'])
                            return True
        
        # Add to processed items since we've checked it but didn't unmonitor
        if item['id'] not in state['radarr'].get('processed_ids', []):
            state['radarr']['processed_ids'].append(item['id'])
            
        return False
    except Exception as e:
        logger.error(f"Error processing {item.get('title', 'unknown')}: {str(e)}")
        return False

def process_episode(episode, config, target_groups, state):
    """Process a single episode, tracking unmonitored status"""
    try:
        episode_id = f"S{episode.get('seasonNumber', '?')}E{episode.get('episodeNumber', '?')}"
        episode_title = f"{episode_id} - {episode.get('title', 'Unknown')}"
        
        # Skip if already unmonitored in our tracking
        if episode['id'] in state['sonarr'].get('unmonitored_episode_ids', []):
            if config.get('debug'):
                logger.debug(f"Skipping already unmonitored episode: {episode_title}")
            return False
            
        # Skip if not monitored in Sonarr, but track it
        if not episode.get('monitored', True):
            if config.get('debug'):
                logger.debug(f"Episode already unmonitored in Sonarr: {episode_title}")
                
            # Add to our unmonitored tracking
            if episode['id'] not in state['sonarr'].get('unmonitored_episode_ids', []):
                state['sonarr']['unmonitored_episode_ids'].append(episode['id'])
                
            # Add to processed list for this run
            if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
                state['sonarr']['processed_episode_ids'].append(episode['id'])
                
            return False
        
        if not episode.get('hasFile', False) or not episode.get('episodeFileId'):
            if config.get('debug'):
                logger.debug(f"Episode has no file: {episode_title}")
                
            # Add to processed list since we've checked it
            if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
                state['sonarr']['processed_episode_ids'].append(episode['id'])
                
            return False
            
        # Get file details for the episode
        file_details_list = get_file_details(config, None, episode['episodeFileId'])
        
        if not file_details_list:
            # Add to processed list since we've checked it
            if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
                state['sonarr']['processed_episode_ids'].append(episode['id'])
                
            return False
            
        file_details = file_details_list[0]  # We should only have one file
        
        if 'path' not in file_details:
            # Add to processed list since we've checked it
            if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
                state['sonarr']['processed_episode_ids'].append(episode['id'])
                
            return False
        
        if config.get('debug'):
            logger.debug(f"Checking file: {file_details['path']}")
                
        release_group = get_release_group(file_details['path'], config)
            
        if release_group:
            # Normalize to lowercase for case-insensitive comparison
            release_group_lower = release_group.lower()
            
            if config.get('debug'):
                logger.debug(f"Comparing '{release_group_lower}' with targets: {target_groups}")
            
            if release_group_lower in target_groups:
                logger.info(f"Match! Release group '{release_group}' found in {episode_title}")
                
                # Add to processed items list
                if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
                    state['sonarr']['processed_episode_ids'].append(episode['id'])
                
                # Unmonitor the episode - ONLY the individual episode, not the series
                if unmonitor_episode(config, episode):
                    # Add to unmonitored list only if successfully unmonitored
                    if episode['id'] not in state['sonarr'].get('unmonitored_episode_ids', []):
                        state['sonarr']['unmonitored_episode_ids'].append(episode['id'])
                    return True
        
        # Add to processed items since we've checked it but didn't unmonitor
        if episode['id'] not in state['sonarr'].get('processed_episode_ids', []):
            state['sonarr']['processed_episode_ids'].append(episode['id'])
            
        return False
    except Exception as e:
        logger.error(f"Error processing episode {episode.get('id', 'unknown')}: {str(e)}")
        return False

if __name__ == "__main__":
    main()
