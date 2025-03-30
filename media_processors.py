"""
Unmonitarr Media Processing Module

Handles intelligent media unmonitoring for Radarr and Sonarr.
"""

import os
import re
import logging
import concurrent.futures
from typing import Dict, List, Optional

logger = logging.getLogger('unmonitarr.processors')

def _extract_release_group(file_path: str) -> Optional[str]:
    """
    🕵️ Extract release group from media file path with surgical precision.
    
    Args:
        file_path (str): Full path to media file
    
    Returns:
        Optional[str]: Detected release group or None
    """
    # Comprehensive release group detection patterns
    patterns = [
        r'-([A-Za-z0-9]+)$',  # Standard release group at end
        r'\[([A-Za-z0-9]+)\]$',  # Bracketed release group
        r'\.([A-Za-z0-9]+)(?:\.|$)',  # Dot-separated release group
        r'(?:^|\.)([A-Za-z0-9]+)-[^-]+$'  # Advanced pattern for complex filenames
    ]
    
    filename = os.path.basename(file_path)
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None

def _should_unmonitor_episode(episode: Dict, target_release_groups: List[str]) -> bool:
    """
    🎯 Precision episode unmonitoring decision engine.
    
    Args:
        episode (dict): Episode metadata
        target_release_groups (list): Configured release groups to unmonitor
    
    Returns:
        bool: Whether episode should be unmonitored
    """
    # Ensure episode has a file
    if not episode.get('hasFile', False):
        return False
    
    # Attempt to extract release group
    file_path = episode.get('episodeFile', {}).get('path', '')
    release_group = _extract_release_group(file_path)
    
    # Check against target release groups
    return (release_group and 
            release_group.lower() in [group.lower() for group in target_release_groups])

def process_radarr_media(
    api_client, 
    current_state: Dict, 
    config: Dict,
    dry_run: bool = False
) -> Dict:
    """
    🎬 Intelligent Radarr Media Unmonitoring Processor
    
    Orchestrates a sophisticated media unmonitoring strategy with:
    - Precise release group detection
    - Parallel processing
    - Comprehensive state tracking
    
    Args:
        api_client (RarrApiClient): Specialized Radarr API client
        current_state (dict): Current application state for Radarr
        config (dict): Application configuration
        dry_run (bool): Simulation mode flag
    
    Returns:
        dict: Comprehensively updated Radarr state
    """
    logger.info("🎥 Initiating Radarr Media Unmonitoring Process")
    
    # Fetch all movies
    movies = api_client.fetch_media()
    
    # Initialize state tracking with defensive defaults
    updated_state = {
        'processed_ids': current_state.get('processed_ids', []),
        'unmonitored_ids': current_state.get('unmonitored_ids', [])
    }
    
    # Parallel processing configuration
    max_workers = config.get('general', {}).get('concurrent', 4)
    unmonitored_movies = []
    
    # Parallel movie processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        def process_movie(movie):
            """
            Individual movie unmonitoring logic
            
            Args:
                movie (dict): Movie metadata
            
            Returns:
                dict or None: Unmonitored movie details or None
            """
            try:
                # Skip already processed or unmonitored movies
                if (movie['id'] in updated_state['processed_ids'] or 
                    movie['id'] in updated_state['unmonitored_ids']):
                    return None
                
                # Skip if not monitored in Radarr
                if not movie.get('monitored', True):
                    updated_state['unmonitored_ids'].append(movie['id'])
                    return None
                
                # Extracting release group from movie file
                release_group = None
                if movie.get('movieFile'):
                    file_path = movie['movieFile'].get('path', '')
                    release_group = _extract_release_group(file_path)
                
                # Release group matching logic
                if release_group and release_group.lower() in config.get('release_groups', []):
                    logger.info(f"🎬 Unmonitoring {movie['title']} (Release Group: {release_group})")
                    
                    if not dry_run:
                        unmonitored = api_client.unmonitor_media(movie)
                        if unmonitored:
                            updated_state['unmonitored_ids'].append(movie['id'])
                            return movie
                
                # Always mark as processed
                updated_state['processed_ids'].append(movie['id'])
                return None
            
            except Exception as e:
                logger.error(f"Error processing movie {movie.get('title', 'Unknown')}: {e}")
                return None
        
        # Execute parallel processing
        movie_futures = [
            executor.submit(process_movie, movie) 
            for movie in movies
        ]
        
        # Collect results, filtering out None values
        for future in concurrent.futures.as_completed(movie_futures):
            result = future.result()
            if result:
                unmonitored_movies.append(result)
    
    # Logging and statistics
    logger.info(f"🏁 Radarr Unmonitoring Summary:")
    logger.info(f"   Total Movies Processed: {len(movies)}")
    logger.info(f"   Movies Unmonitored: {len(unmonitored_movies)}")
    
    # Update state with final processed information
    return updated_state

def process_sonarr_media(
    api_client, 
    current_state: Dict, 
    config: Dict,
    dry_run: bool = False
) -> Dict:
    """
    📺 Intelligent Sonarr Media Unmonitoring Processor
    
    Implements a multi-tiered unmonitoring strategy:
    - Episode-level processing
    - Season-level aggregation
    - Series-level management
    
    Args:
        api_client (SonarrApiClient): Specialized Sonarr API client
        current_state (dict): Current application state for Sonarr
        config (dict): Application configuration
        dry_run (bool): Simulation mode flag
    
    Returns:
        dict: Comprehensively updated Sonarr state
    """
    logger.info("📺 Initiating Sonarr Media Unmonitoring Process")
    
    # Fetch all series
    series_list = api_client.fetch_media()
    
    # Initialize state tracking
    updated_state = {
        'processed_ids': current_state.get('processed_ids', []),
        'processed_episode_ids': current_state.get('processed_episode_ids', []),
        'unmonitored_ids': current_state.get('unmonitored_ids', []),
        'unmonitored_episode_ids': current_state.get('unmonitored_episode_ids', []),
        'unmonitored_seasons': current_state.get('unmonitored_seasons', {})
    }
    
    # Parallel processing configuration
    max_workers = config.get('general', {}).get('concurrent', 4)
    unmonitored_series_details = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        def process_series(series):
            """
            Comprehensive series unmonitoring processor
            
            Args:
                series (dict): Series metadata
            
            Returns:
                dict or None: Series unmonitoring details
            """
            try:
                # Skip already processed series
                if series['id'] in updated_state['processed_ids']:
                    return None
                
                # Skip if not monitored in Sonarr
                if not series.get('monitored', True):
                    updated_state['unmonitored_ids'].append(series['id'])
                    return None
                
                # Fetch episodes for this series
                episodes = api_client.fetch_episodes(series['id'])
                
                # Track series-level processing details
                series_details = {
                    'title': series['title'],
                    'unmonitored_episodes': [],
                    'unmonitored_seasons': set()
                }
                
                # Process individual episodes
                for episode in episodes:
                    if _should_unmonitor_episode(episode, config.get('release_groups', [])):
                        if not dry_run:
                            unmonitored = api_client.unmonitor_episode(episode)
                            if unmonitored:
                                updated_state['unmonitored_episode_ids'].append(episode['id'])
                                series_details['unmonitored_episodes'].append(episode['id'])
                                series_details['unmonitored_seasons'].add(episode.get('seasonNumber', 0))
                
                # Mark series as processed
                updated_state['processed_ids'].append(series['id'])
                
                # Optionally unmonitor entire series if all episodes are unmonitored
                if series_details['unmonitored_episodes']:
                    # Track unmonitored seasons
                    if series['id'] not in updated_state['unmonitored_seasons']:
                        updated_state['unmonitored_seasons'][series['id']] = list(series_details['unmonitored_seasons'])
                    
                    # Unmonitor series if all episodes unmonitored
                    if len(series_details['unmonitored_episodes']) == len(episodes):
                        if not dry_run:
                            api_client.unmonitor_media(series)
                            updated_state['unmonitored_ids'].append(series['id'])
                    
                    return series_details
                
                return None
            
            except Exception as e:
                logger.error(f"Error processing series {series.get('title', 'Unknown')}: {e}")
                return None
        
        # Execute parallel series processing
        series_futures = [
            executor.submit(process_series, series) 
            for series in series_list
        ]
        
        # Collect results, filtering out None values
        for future in concurrent.futures.as_completed(series_futures):
            result = future.result()
            if result:
                unmonitored_series_details.append(result)
    
    # Logging and statistics
    logger.info(f"🏁 Sonarr Unmonitoring Summary:")
    logger.info(f"   Total Series Processed: {len(series_list)}")
    logger.info(f"   Series with Unmonitored Episodes: {len(unmonitored_series_details)}")
    
    return updated_state

# Expose key processing functions
__all__ = [
    'process_radarr_media', 
    'process_sonarr_media'
]