#!/usr/bin/env python3
"""
Unmonitarr: Intelligent Media Library Cleanup for Radarr and Sonarr

A sophisticated tool designed to automatically unmonitor media files from 
specified release groups across Radarr and Sonarr, with hierarchical processing.

Features:
- Intelligent hierarchical unmonitoring (episodes → seasons → series)
- Parallel processing for optimal performance
- Comprehensive logging and state tracking
- Flexible configuration via JSON
- Advanced release group detection
- Continuous monitoring mode

Core Unmonitoring Strategy:
1. Identify media from specified release groups
2. Unmonitor individual episodes 
3. Unmonitor entire seasons when all episodes are unmonitored
4. Unmonitor series while preserving future season monitoring
"""

import os
import sys
import json
import copy
import time
import logging
import argparse
import shutil
import concurrent.futures
from functools import partial
from datetime import datetime, timedelta

# Local module imports
from config_manager import load_config, validate_configuration
from state_manager import (
    initialize_state, 
    save_comprehensive_state, 
    calculate_unmonitored_ratio
)
from media_processors import (
    process_radarr_media, 
    process_sonarr_media
)
from api_client import (
    RarrApiClient, 
    SonarrApiClient
)
from notification_manager import send_notifications

# Configure logging
logger = logging.getLogger('unmonitarr')

def setup_logging(debug_mode=False, log_file='/logs/unmonitarr.log', 
                  max_size_mb=10, backup_count=3):
    """
    Configure comprehensive logging with rotation and multiple handlers.
    
    Args:
        debug_mode (bool): Enable verbose logging
        log_file (str): Path to log file
        max_size_mb (int): Maximum log file size in megabytes
        backup_count (int): Number of backup log files to retain
    """
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Create logging directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Configure formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    
    # File Handler with Rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, 
        maxBytes=max_size_mb * 1024 * 1024, 
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    
    # Configure root logger
    logger.setLevel(log_level)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def parse_arguments():
    """
    Parse and validate command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="Unmonitarr: Intelligent Media Library Cleanup"
    )
    parser.add_argument(
        '--config', 
        default='config/unmonitarr_config.json',
        help="Path to configuration file"
    )
    parser.add_argument(
        '--monitor', 
        action='store_true',
        help="Run in continuous monitoring mode"
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help="Simulate unmonitoring without making changes"
    )
    parser.add_argument(
        '--debug', 
        action='store_true',
        help="Enable verbose debugging output"
    )
    
    return parser.parse_args()

def process_media_library(configs, state, args):
    """
    Orchestrate media library processing across Radarr and Sonarr.
    
    Args:
        configs (dict): Service configurations
        state (dict): Current application state
        args (argparse.Namespace): Command-line arguments
    
    Returns:
        dict: Updated state after media processing
    """
    # Deep copy to prevent state mutation
    current_state = copy.deepcopy(state)
    
    logger.info("🚀 Starting Unmonitarr Media Processing")
    start_time = time.time()
    
    # Process Radarr media if configured
    if 'radarr' in configs:
        logger.info("=== Processing Radarr Media ===")
        radarr_client = RarrApiClient(configs['radarr'])
        current_state['radarr'] = process_radarr_media(
            radarr_client, 
            current_state.get('radarr', {}), 
            args.dry_run
        )
    
    # Process Sonarr media if configured
    if 'sonarr' in configs:
        logger.info("=== Processing Sonarr Media ===")
        sonarr_client = SonarrApiClient(configs['sonarr'])
        current_state['sonarr'] = process_sonarr_media(
            sonarr_client, 
            current_state.get('sonarr', {}), 
            args.dry_run
        )
    
    # Send notifications about processed media
    if configs.get('notifications', {}).get('discord', {}).get('enabled', False):
        send_notifications(current_state, configs)
    
    elapsed_time = time.time() - start_time
    logger.info(f"🏁 Media Processing Completed in {elapsed_time:.2f} seconds")
    
    return current_state

def run_monitoring_loop(configs, state, args):
    """
    Continuously monitor and process media library.
    
    Args:
        configs (dict): Service configurations
        state (dict): Initial application state
        args (argparse.Namespace): Command-line arguments
    """
    interval = configs.get('general', {}).get('monitoring_interval', 3600)
    
    while True:
        try:
            # Process media
            updated_state = process_media_library(configs, state, args)
            
            # Save comprehensive state
            save_comprehensive_state(updated_state)
            
            # Log next scan time
            next_scan_time = datetime.now() + timedelta(seconds=interval)
            logger.info(f"Next scan scheduled at: {next_scan_time}")
            
            # Sleep until next interval
            time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            logger.exception("Detailed error traceback")
            time.sleep(60)  # Wait before retrying

def main():
    """
    Main entry point for Unmonitarr application.
    Orchestrates configuration loading, state management, and media processing.
    """
    # Parse command-line arguments
    args = parse_arguments()
    
    # Setup logging based on debug flag
    logger = setup_logging(debug_mode=args.debug)
    
    try:
        # Load and validate configuration
        configs = load_config(args.config)
        validate_configuration(configs)
        
        # Initialize or load application state
        state = initialize_state()
        
        # Determine processing mode
        if args.monitor:
            logger.info("🔄 Starting Continuous Monitoring Mode")
            run_monitoring_loop(configs, state, args)
        else:
            logger.info("🚀 Running Single Media Library Scan")
            updated_state = process_media_library(configs, state, args)
            save_comprehensive_state(updated_state)
    
    except Exception as e:
        logger.error(f"Unmonitarr failed to start: {e}")
        logger.exception("Detailed startup error")
        sys.exit(1)

if __name__ == "__main__":
    main()