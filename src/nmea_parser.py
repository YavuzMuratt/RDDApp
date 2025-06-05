import re
from datetime import datetime, date
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
import numpy as np
from math import radians, sin, cos, sqrt, atan2

@dataclass
class GPSData:
    timestamp: datetime
    latitude_ddmm: str  # DDMM.MMMMM format
    longitude_ddmm: str  # DDDMM.MMMMM format
    latitude_decimal: float
    longitude_decimal: float
    speed_knots: float
    course_degrees: float
    fix_quality: int
    num_satellites: int
    hdop: float  # Horizontal Dilution of Precision
    altitude: float

class NMEAParser:
    def __init__(self):
        self.gps_data: List[GPSData] = []
        self.temp_data: Dict[str, Dict] = {}  # Store temporary data by timestamp
        self._current_date: Optional[date] = None
        
    def parse_line(self, line: str) -> None:
        """Parse a single NMEA sentence line."""
        if not line.startswith('$'):
            return
            
        try:
            if line.startswith('$GPRMC'):
                self._parse_gprmc(line)
            elif line.startswith('$GPGGA'):
                self._parse_gpgga(line)
        except (ValueError, IndexError) as e:
            print(f"Error parsing line: {line}\nError: {str(e)}")
            
    def _get_time_key(self, time_str: str) -> str:
        """Create a standardized time key from time string."""
        # Remove milliseconds for consistent matching
        return time_str.split('.')[0]
            
    def _parse_gprmc(self, line: str) -> None:
        """Parse GPRMC sentence."""
        parts = line.split(',')
        if len(parts) < 12 or parts[2] != 'A':  # A = valid data
            return
            
        # Parse time and date
        time_str = parts[1]
        date_str = parts[9]
        timestamp = datetime.strptime(f"{date_str}{time_str}", "%d%m%y%H%M%S.%f")
        self._current_date = timestamp.date()  # Store current date for GPGGA
        
        # Parse coordinates
        lat_ddmm = parts[3] + parts[4]  # DDMM.MMMMM + N/S
        lon_ddmm = parts[5] + parts[6]  # DDDMM.MMMMM + E/W
        
        # Convert to decimal degrees
        lat_decimal = self._ddmm_to_decimal(parts[3], parts[4])
        lon_decimal = self._ddmm_to_decimal(parts[5], parts[6])
        
        # Parse other data
        speed = float(parts[7]) if parts[7] else 0.0
        course = float(parts[8]) if parts[8] else 0.0
        
        # Store in temporary dictionary
        key = self._get_time_key(time_str)
        if key not in self.temp_data:
            self.temp_data[key] = {}
            
        self.temp_data[key].update({
            'timestamp': timestamp,
            'latitude_ddmm': lat_ddmm,
            'longitude_ddmm': lon_ddmm,
            'latitude_decimal': lat_decimal,
            'longitude_decimal': lon_decimal,
            'speed_knots': speed,
            'course_degrees': course
        })
        
        # Try to create GPS data point if we have all info
        self._try_create_gps_point(key)
        
    def _parse_gpgga(self, line: str) -> None:
        """Parse GPGGA sentence."""
        if not self._current_date:
            return  # Wait for GPRMC to set the date
            
        parts = line.split(',')
        if len(parts) < 15:
            return
            
        # Parse time
        time_str = parts[1]
        key = self._get_time_key(time_str)
        
        # Parse other data
        fix_quality = int(parts[6])
        num_satellites = int(parts[7])
        hdop = float(parts[8]) if parts[8] else 0.0
        altitude = float(parts[9]) if parts[9] else 0.0
        
        if key not in self.temp_data:
            self.temp_data[key] = {}
            
        self.temp_data[key].update({
            'fix_quality': fix_quality,
            'num_satellites': num_satellites,
            'hdop': hdop,
            'altitude': altitude
        })
        
        # Try to create GPS data point if we have all info
        self._try_create_gps_point(key)
        
    def _try_create_gps_point(self, key: str) -> None:
        """Try to create a GPS point if we have both GPRMC and GPGGA data."""
        data = self.temp_data.get(key, {})
        required_fields = [
            'timestamp', 'latitude_ddmm', 'longitude_ddmm',
            'latitude_decimal', 'longitude_decimal', 'speed_knots',
            'course_degrees', 'fix_quality', 'num_satellites',
            'hdop', 'altitude'
        ]
        
        if all(field in data for field in required_fields):
            gps_point = GPSData(**data)
            self.gps_data.append(gps_point)
            del self.temp_data[key]
        
    def _ddmm_to_decimal(self, coord: str, direction: str) -> float:
        """Convert DDMM.MMMMM format to decimal degrees."""
        if not coord or not direction:
            return 0.0
            
        # Split into degrees and minutes
        if coord.count('.') == 0:
            return 0.0
            
        # Handle coordinates with varying degree lengths (2 or 3 digits)
        dot_index = coord.index('.')
        if dot_index > 4:  # Longitude (3 digits for degrees)
            degrees = float(coord[:3])
            minutes = float(coord[3:])
        else:  # Latitude (2 digits for degrees)
            degrees = float(coord[:2])
            minutes = float(coord[2:])
        
        # Calculate decimal degrees
        decimal = degrees + (minutes / 60.0)
        
        # Apply direction
        if direction in ['S', 'W']:
            decimal = -decimal
            
        return decimal
        
    def parse_file(self, file_path: str) -> List[GPSData]:
        """Parse an entire NMEA file."""
        self.gps_data = []
        self.temp_data = {}
        self._current_date = None
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                self.parse_line(line)
                    
        # Sort data by timestamp
        self.gps_data.sort(key=lambda x: x.timestamp)
        return self.gps_data
        
    def get_coordinates(self) -> List[Tuple[float, float]]:
        """Get list of (latitude, longitude) coordinates in decimal degrees."""
        return [(data.latitude_decimal, data.longitude_decimal) for data in self.gps_data]
        
    def get_timestamps(self) -> List[datetime]:
        """Get list of timestamps."""
        return [data.timestamp for data in self.gps_data]

    def calculate_distance(self, point1: GPSData, point2: GPSData) -> float:
        """
        Calculate the distance between two GPS points in meters using the Haversine formula.
        
        Args:
            point1: First GPS point
            point2: Second GPS point
            
        Returns:
            Distance in meters
        """
        # Earth's radius in meters
        R = 6371000
        
        # Convert coordinates to radians
        lat1, lon1 = radians(point1.latitude_decimal), radians(point1.longitude_decimal)
        lat2, lon2 = radians(point2.latitude_decimal), radians(point2.longitude_decimal)
        
        # Calculate differences
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        # Haversine formula
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
        
    def get_distances(self) -> List[float]:
        """
        Calculate distances between consecutive GPS points.
        
        Returns:
            List of distances in meters
        """
        distances = []
        for i in range(len(self.gps_data) - 1):
            distance = self.calculate_distance(self.gps_data[i], self.gps_data[i+1])
            distances.append(distance)
        return distances 