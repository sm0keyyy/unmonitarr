"""
Unmonitarr State Management Module

Handles state initialization, persistence, and comprehensive tracking.
"""

import os
import json
import copy
import logging
import shutil
from datetime import datetime

logger = logging.getLogger('unmonitarr.state')

STATE_FILE_PATH = '/config/unmonitarr_state.json'
VERSION = '1.2.0'

def calculate_unmonitored_ratio(total, unmonitored):
    """
    Calculate the ratio of unmonitored items to total items.
    
    Args:
        total (int): Total number of items
        unmonitored (int): Number of unmonitored items
        
    Returns:
        float: Ratio of unmonitored items (0-1) or 0 if total is 0
    """
    if total == 0:
        return 0
    return unmonitored / total

def initialize_state():
    """
    Initialize or load existing application state.
    
    Returns:
        dict: Application state with default or loaded values
    """
    try:
        # Check if state file exists
        if os.path.exists(STATE_FILE_PATH):
            with open(STATE_FILE_PATH, 'r') as f:
                existing_state = json.load(f)
                
                # Ensure state has necessary structure
                if not all(key in existing_state for key in ['radarr', 'sonarr']):
                    return _create_default_state()
                
                return existing_state
        
        # Create default state if no existing file
        return _create_default_state()
    
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading state: {e}")
        return _create_default_state()

def _create_default_state():
    """
    Create a default state structure.
    
    Returns:
        dict: Default application state
    """
    return {
        "metadata": {
            "version": VERSION,
            "created_at": datetime.now().isoformat(),
            "last_scan": None
        },
        "radarr": {
            "processed_ids": [],
            "unmonitored_ids": []
        },
        "sonarr": {
            "processed_ids": [],
            "processed_episode_ids": [],
            "unmonitored_ids": [],
            "unmonitored_episode_ids": [],
            "unmonitored_seasons": {}
        }
    }

def save_comprehensive_state(state):
    """
    Save a comprehensive, enriched state with detailed metrics.
    
    Args:
        state (dict): Current application state
    """
    try:
        # Ensure config directory exists
        os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
        
        # Create a deep copy to prevent mutation
        enhanced_state = copy.deepcopy(state)
        
        # Radarr Metrics Calculation
        radarr_processed = len(enhanced_state.get('radarr', {}).get('processed_ids', []))
        radarr_unmonitored = len(enhanced_state.get('radarr', {}).get('unmonitored_ids', []))
        
        # Sonarr Metrics Calculation
        sonarr = enhanced_state.get('sonarr', {})
        sonarr_processed_series = len(sonarr.get('processed_ids', []))
        sonarr_processed_episodes = len(sonarr.get('processed_episode_ids', []))
        sonarr_unmonitored_series = len(sonarr.get('unmonitored_ids', []))
        sonarr_unmonitored_episodes = len(sonarr.get('unmonitored_episode_ids', []))
        
        # Unmonitored Seasons Analysis
        unmonitored_seasons = sonarr.get('unmonitored_seasons', {})
        total_series_with_unmonitored_seasons = len(unmonitored_seasons)
        total_unmonitored_season_entries = sum(
            len(seasons) for seasons in unmonitored_seasons.values()
        )
        
        # Enrich State with Comprehensive Metrics
        enhanced_state['metadata'] = {
            "version": VERSION,
            "last_scan": datetime.now().isoformat(),
            "scanning_mode": "monitoring"  # This could be dynamically set based on mode
        }
        
        # Radarr Summary
        enhanced_state['radarr']['summary'] = {
            "total_processed": radarr_processed,
            "total_unmonitored": radarr_unmonitored,
            "unmonitored_ratio": calculate_unmonitored_ratio(
                radarr_processed, radarr_unmonitored
            )
        }
        
        # Sonarr Summary
        enhanced_state['sonarr']['summary'] = {
            "total_processed_series": sonarr_processed_series,
            "total_processed_episodes": sonarr_processed_episodes,
            "total_unmonitored_series": sonarr_unmonitored_series,
            "total_unmonitored_episodes": sonarr_unmonitored_episodes,
            "total_unmonitored_seasons": total_unmonitored_season_entries,
            "unmonitored_ratio": {
                "series": calculate_unmonitored_ratio(
                    sonarr_processed_series, sonarr_unmonitored_series
                ),
                "episodes": calculate_unmonitored_ratio(
                    sonarr_processed_episodes, sonarr_unmonitored_episodes
                ),
                "seasons": calculate_unmonitored_ratio(
                    sonarr_processed_series, total_series_with_unmonitored_seasons
                )
            }
        }
        
        # Comprehensive Overall Statistics
        enhanced_state['statistics'] = {
            "total_media_processed": radarr_processed + sonarr_processed_series,
            "total_unmonitored_media": radarr_unmonitored + sonarr_unmonitored_series,
            "overall_unmonitored_ratio": calculate_unmonitored_ratio(
                radarr_processed + sonarr_processed_series, 
                radarr_unmonitored + sonarr_unmonitored_series
            ),
            "processing_timestamp": datetime.now().isoformat()
        }
        
        # Create backup of existing state file
        if os.path.exists(STATE_FILE_PATH):
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{STATE_FILE_PATH}.{backup_timestamp}.bak"
            shutil.copy2(STATE_FILE_PATH, backup_file)
            logger.info(f"Created state backup: {backup_file}")
        
        # Write enhanced state with pretty formatting
        with open(STATE_FILE_PATH, 'w') as f:
            json.dump(enhanced_state, f, indent=2)
        
        # Log comprehensive summary
        _log_state_summary(enhanced_state)
    
    except Exception as e:
        logger.error(f"Failed to save comprehensive state: {e}")
        logger.exception("Detailed state saving error")

def _log_state_summary(state):
    """
    Log a human-readable summary of the application state.
    
    Args:
        state (dict): Comprehensive application state
    """
    try:
        logger.info("=== Unmonitarr State Summary ===")
        
        # Radarr Summary
        radarr_summary = state.get('radarr', {}).get('summary', {})
        logger.info(f"Radarr: {radarr_summary.get('total_unmonitored', 0)} movies unmonitored")
        logger.info(f"Radarr Unmonitored Ratio: {radarr_summary.get('unmonitored_ratio', 0)}")
        
        # Sonarr Summary
        sonarr_summary = state.get('sonarr', {}).get('summary', {})
        logger.info(f"Sonarr: {sonarr_summary.get('total_unmonitored_episodes', 0)} episodes unmonitored")
        logger.info(f"Sonarr: {sonarr_summary.get('total_unmonitored_seasons', 0)} seasons unmonitored")
        logger.info(f"Sonarr Series Unmonitored Ratio: {sonarr_summary.get('unmonitored_ratio', {}).get('series', 0)}")
        
        # Overall Statistics
        stats = state.get('statistics', {})
        logger.info(f"Total Media Processed: {stats.get('total_media_processed', 0)}")
        logger.info(f"Total Unmonitored Media: {stats.get('total_unmonitored_media', 0)}")
        logger.info(f"Overall Unmonitored Ratio: {stats.get('overall_unmonitored_ratio', 0)}")
        
        # Metadata
        metadata = state.get('metadata', {})
        logger.info(f"Last Scan: {metadata.get('last_scan', 'N/A')}")
        logger.info(f"Version: {metadata.get('version', 'Unknown')}")
    
    except Exception as e:
        logger.error(f"Failed to log state summary: {e}")

# Optionally export key functions
__all__ = [
    'initialize_state', 
    'save_comprehensive_state', 
    'calculate_unmonitored_ratio'
]