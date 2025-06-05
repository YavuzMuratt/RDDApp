import requests
from typing import Optional, Dict
import time
import logging

class Geocoder:
    def __init__(self, user_agent: str = "RoadDamageDetector/1.0"):
        """
        Initialize the geocoder with a user agent.
        
        Args:
            user_agent: User agent string to identify the application
        """
        self.base_url = "https://nominatim.openstreetmap.org/reverse"
        self.headers = {
            'User-Agent': user_agent
        }
        self.logger = logging.getLogger(__name__)
        
    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict[str, str]]:
        """
        Convert coordinates to address information.
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            Dictionary containing address components or None if geocoding fails
        """
        params = {
            'format': 'json',
            'lat': latitude,
            'lon': longitude,
            'addressdetails': 1,
            'zoom': 18  # Get more detailed address information
        }
        
        try:
            # Add delay to respect rate limits
            time.sleep(1)
            
            response = requests.get(self.base_url, params=params, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            address = data.get('address', {})
            
            # Extract address components with fallbacks
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or 
                   address.get('county'))
            
            district = (address.get('suburb') or 
                       address.get('neighbourhood') or 
                       address.get('quarter') or 
                       address.get('district'))
            
            street = (address.get('road') or 
                     address.get('pedestrian') or 
                     address.get('footway') or 
                     address.get('path'))
            
            return {
                'city': city,
                'district': district,
                'street': street,
                'full_address': data.get('display_name', '')
            }
            
        except requests.RequestException as e:
            self.logger.error(f"Geocoding request failed: {e}")
            return None
        except (KeyError, ValueError) as e:
            self.logger.error(f"Error parsing geocoding response: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in geocoding: {e}")
            return None 