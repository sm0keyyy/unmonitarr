"""
Unmonitarr API Client Module

Provides abstract and concrete implementations for interacting 
with Radarr and Sonarr APIs.
"""

import logging
import requests # type: ignore
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

logger = logging.getLogger('unmonitarr.api')

class BaseApiClient(ABC):
    """
    Abstract base class for API interactions with media management services.
    
    Provides a consistent interface for fetching and manipulating media.
    """
    
    def __init__(self, config: Dict):
        """
        Initialize API client with configuration.
        
        Args:
            config (dict): Service configuration dictionary
        """
        self.host = config.get('host', 'localhost')
        self.port = config.get('port', 7878)
        self.api_key = config.get('apikey')
        self.base_url = f"http://{self.host}:{self.port}/api/v3"
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """
        Validate client configuration.
        
        Raises:
            ValueError: If configuration is invalid
        """
        if not all([self.host, self.port, self.api_key]):
            raise ValueError("Incomplete API client configuration")
    
    def _build_headers(self) -> Dict[str, str]:
        """
        Build standard API request headers.
        
        Returns:
            dict: Headers for API requests
        """
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[Dict]:
        """
        Make a generic API request with error handling.
        
        Args:
            method (str): HTTP method (get, post, put)
            endpoint (str): API endpoint
            **kwargs: Additional request arguments
        
        Returns:
            dict or None: Response data or None if request fails
        """
        url = f"{self.base_url}/{endpoint}"
        headers = self._build_headers()
        
        try:
            response = requests.request(
                method, 
                url, 
                headers=headers, 
                timeout=30,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API Request Error: {e}")
            return None
    
    @abstractmethod
    def fetch_media(self) -> List[Dict]:
        """
        Fetch all media items.
        
        Abstract method to be implemented by subclasses.
        
        Returns:
            List of media dictionaries
        """
        pass
    
    @abstractmethod
    def unmonitor_media(self, media_item: Dict) -> bool:
        """
        Unmonitor a specific media item.
        
        Abstract method to be implemented by subclasses.
        
        Args:
            media_item (dict): Media item to unmonitor
        
        Returns:
            bool: Whether unmonitoring was successful
        """
        pass

class RarrApiClient(BaseApiClient):
    """
    Specialized API client for Radarr interactions.
    """
    
    def fetch_media(self) -> List[Dict]:
        """
        Fetch all movies from Radarr.
        
        Returns:
            List of movie dictionaries
        """
        movies = self._make_request('get', 'movie')
        return movies or []
    
    def unmonitor_media(self, movie: Dict) -> bool:
        """
        Unmonitor a specific movie.
        
        Args:
            movie (dict): Movie to unmonitor
        
        Returns:
            bool: Whether unmonitoring was successful
        """
        # Create a copy to prevent mutation of original
        unmonitor_movie = movie.copy()
        unmonitor_movie['monitored'] = False
        
        result = self._make_request(
            'put', 
            f'movie/{movie["id"]}', 
            json=unmonitor_movie
        )
        
        return result is not None

class SonarrApiClient(BaseApiClient):
    """
    Specialized API client for Sonarr interactions.
    """
    
    def fetch_media(self) -> List[Dict]:
        """
        Fetch all series from Sonarr.
        
        Returns:
            List of series dictionaries
        """
        series = self._make_request('get', 'series')
        return series or []
    
    def fetch_episodes(self, series_id: int) -> List[Dict]:
        """
        Fetch episodes for a specific series.
        
        Args:
            series_id (int): ID of the series
        
        Returns:
            List of episode dictionaries
        """
        episodes = self._make_request('get', f'episode?seriesId={series_id}')
        return [ep for ep in (episodes or []) if ep.get('hasFile', False)]
    
    def unmonitor_media(self, series: Dict) -> bool:
        """
        Unmonitor a specific series.
        
        Args:
            series (dict): Series to unmonitor
        
        Returns:
            bool: Whether unmonitoring was successful
        """
        # Create a copy to prevent mutation of original
        unmonitor_series = series.copy()
        unmonitor_series['monitored'] = False
        
        result = self._make_request(
            'put', 
            f'series/{series["id"]}', 
            json=unmonitor_series
        )
        
        return result is not None
    
    def unmonitor_episode(self, episode: Dict) -> bool:
        """
        Unmonitor a specific episode.
        
        Args:
            episode (dict): Episode to unmonitor
        
        Returns:
            bool: Whether unmonitoring was successful
        """
        # Create a copy to prevent mutation of original
        unmonitor_episode = episode.copy()
        unmonitor_episode['monitored'] = False
        
        result = self._make_request(
            'put', 
            f'episode/{episode["id"]}', 
            json=unmonitor_episode
        )
        
        return result is not None

# Export key classes
__all__ = ['RarrApiClient', 'SonarrApiClient']
