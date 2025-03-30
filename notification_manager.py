"""
Unmonitarr Notification Management Module

Handles sending notifications about media library cleanup activities.
"""

import os
import json
import logging
import requests # type: ignore
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger('unmonitarr.notifications')

class DiscordNotifier:
    """
    🤖 Intelligent Discord Notification Engine
    
    Crafts rich, contextual notifications about media library cleanup
    with sophisticated formatting and intelligent throttling.
    """
    
    def __init__(self, config_path: str = '/config/unmonitarr_config.json'):
        """
        Initialize the Discord notification system with smart configuration.
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.webhook_url = os.environ.get('DISCORD_WEBHOOK_URL') or \
            self.config.get('notifications', {}).get('discord', {}).get('webhook_url')
        
        # Throttling configuration
        self.throttle_limits = self.config.get('notifications', {}) \
            .get('discord', {}).get('throttle_limit', {
                'movies': 10,
                'episodes': 25,
                'seasons': 5,
                'series': 2
            })
    
    def _load_config(self, config_path: str) -> Dict:
        """
        Load configuration with robust error handling.
        
        Args:
            config_path (str): Path to configuration file
        
        Returns:
            Dict: Parsed configuration
        """
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load Discord config: {e}")
            return {}
    
    def _create_embed(
        self, 
        title: str, 
        description: str, 
        color: int,
        items: Dict
    ) -> Dict:
        """
        Create a rich, detailed Discord embed.
        
        Args:
            title (str): Embed title
            description (str): Embed description
            color (int): Embed color
            items (Dict): Media items to display
        
        Returns:
            Dict: Discord embed payload
        """
        # Truncate items to respect throttle limits
        max_items = self.throttle_limits.get('movies', 10)
        truncated_items = list(items.values())[:max_items]
        
        # Group items by release group
        release_groups = {}
        for item in truncated_items:
            group = item.get('release_group', 'Unknown')
            if group not in release_groups:
                release_groups[group] = []
            release_groups[group].append(item['title'])
        
        # Create embed fields
        fields = [
            {
                "name": f"📦 Release Group: {group}",
                "value": "```\n" + "\n".join(titles[:10]) + "\n```",
                "inline": False
            }
            for group, titles in release_groups.items()
        ]
        
        return {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {
                "text": "Unmonitarr: Media Library Management"
            }
        }
    
    def send_notification(
        self, 
        state: Dict, 
        config: Optional[Dict] = None
    ) -> bool:
        """
        Send comprehensive Discord notification about media cleanup.
        
        Args:
            state (Dict): Current application state
            config (Dict, optional): Additional configuration
        
        Returns:
            bool: Whether notification was sent successfully
        """
        if not self.webhook_url:
            logger.warning("No Discord webhook configured. Skipping notification.")
            return False
        
        payload = {"embeds": []}
        
        # Radarr Unmonitored Movies Notification
        if 'radarr' in state and state['radarr'].get('unmonitored_ids'):
            movies_embed = self._create_embed(
                "🎬 Unmonitarr: Movie Cleanup",
                f"Unmonitored {len(state['radarr']['unmonitored_ids'])} movies",
                0xFF6B6B,  # Vibrant Coral
                {
                    str(idx): {
                        'title': movie.get('title', 'Unknown Movie'),
                        'release_group': 'Unknown'
                    } for idx, movie in enumerate(state['radarr'].get('unmonitored_ids', []))
                }
            )
            payload['embeds'].append(movies_embed)
        
        # Sonarr Unmonitored Series/Episodes Notification
        if 'sonarr' in state and state['sonarr'].get('unmonitored_episode_ids'):
            series_embed = self._create_embed(
                "📺 Unmonitarr: TV Series Cleanup",
                f"Unmonitored {len(state['sonarr']['unmonitored_episode_ids'])} episodes",
                0x4ECDC4,  # Teal
                {
                    str(idx): {
                        'title': f"{episode.get('series', 'Unknown')} - S{episode.get('season', '?')}E{episode.get('episode', '?')}",
                        'release_group': episode.get('release_group', 'Unknown')
                    } for idx, episode in enumerate(state['sonarr'].get('unmonitored_episode_ids', []))
                }
            )
            payload['embeds'].append(series_embed)
        
        # Send notification if we have embeds
        if payload['embeds']:
            try:
                response = requests.post(
                    self.webhook_url, 
                    json=payload, 
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()
                logger.info("🎉 Discord notification sent successfully!")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to send Discord notification: {e}")
                return False
        
        logger.info("📭 No media to report in notification")
        return False

def send_notifications(state: Dict, configs: Dict) -> bool:
    """
    Central notification dispatch function.
    
    Args:
        state (Dict): Current application state
        configs (Dict): Application configurations
    
    Returns:
        bool: Whether notifications were sent successfully
    """
    # Check if Discord notifications are enabled
    discord_config = configs.get('notifications', {}).get('discord', {})
    if not discord_config.get('enabled', False):
        logger.info("Discord notifications are disabled")
        return False
    
    try:
        # Initialize Discord notifier
        notifier = DiscordNotifier()
        
        # Send notifications
        return notifier.send_notification(state, configs)
    
    except Exception as e:
        logger.error(f"Notification dispatch failed: {e}")
        return False

# Prepare for potential future notification channels
__all__ = [
    'send_notifications',
    'DiscordNotifier'
]
