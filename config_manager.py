"""
Unmonitarr Configuration Management Module

Handles loading, validation, and preprocessing of configuration files.
"""

import os
import json
import logging

logger = logging.getLogger('unmonitarr.config')

def load_config(config_path):
    """
    Load and preprocess configuration from JSON file.
    
    Args:
        config_path (str): Path to configuration file
    
    Returns:
        dict: Validated and processed configuration
    
    Raises:
        FileNotFoundError: If configuration file is missing
        json.JSONDecodeError: If configuration is invalid JSON
    """
    try:
        with open(config_path, 'r') as config_file:
            config = json.load(config_file)
        
        # Normalize release groups
        if 'general' in config and 'release_groups' in config['general']:
            release_groups = config['general']['release_groups']
            
            # Handle comma-separated string input
            if isinstance(release_groups, str):
                config['general']['release_groups'] = [
                    group.strip() for group in release_groups.split(',')
                ]
            
            # Normalize to lowercase for consistent matching
            config['general']['release_groups'] = [
                group.lower() for group in config['general']['release_groups']
            ]
        
        logger.info(f"Configuration loaded from {config_path}")
        return config
    
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in configuration file: {config_path}")
        raise

def validate_configuration(config):
    """
    Validate configuration for required elements and sanity checks.
    
    Args:
        config (dict): Configuration dictionary to validate
    
    Raises:
        ValueError: If configuration is invalid
    """
    # Check for required top-level keys
    required_keys = ['general', 'services']
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration section: {key}")
    
    # Validate services
    services = ['radarr', 'sonarr']
    configured_services = []
    
    for service in services:
        if service in config.get('services', {}):
            service_config = config['services'][service]
            
            # Check for minimal required service configuration
            required_service_keys = ['host', 'port', 'apikey']
            for req_key in required_service_keys:
                if req_key not in service_config:
                    raise ValueError(f"Missing {req_key} for {service}")
            
            # Validate host and port
            try:
                port = int(service_config['port'])
                if not (0 < port < 65536):
                    raise ValueError(f"Invalid port for {service}: {port}")
            except ValueError:
                raise ValueError(f"Invalid port configuration for {service}")
            
            configured_services.append(service)
    
    # Ensure at least one service is configured
    if not configured_services:
        raise ValueError("No services (Radarr or Sonarr) configured")
    
    # Validate release groups
    release_groups = config.get('general', {}).get('release_groups', [])
    if not release_groups:
        logger.warning("No release groups configured. No media will be unmonitored.")
    
    logger.info(f"Configuration validated for services: {configured_services}")
