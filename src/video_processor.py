import cv2
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from pathlib import Path
from nmea_parser import NMEAParser, GPSData
from detector import RoadDamageDetector, Detection
from database import Database, RoadIssue, RoadSegment
from geocoder import Geocoder
import os

class VideoProcessor:
    def __init__(self, video_path: str, nmea_path: str, model_path: str, db_path: str = "road_issues.db", conf_threshold: float = 0.5):
        """
        Initialize the video processor with video and NMEA data.
        
        Args:
            video_path: Path to the video file
            nmea_path: Path to the NMEA file
            model_path: Path to the YOLO model
            db_path: Path to the SQLite database file
            conf_threshold: Confidence threshold for detections
        """
        self.video_path = video_path
        self.nmea_path = nmea_path
        
        # Initialize video capture
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
            
        # Get video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Parse NMEA data
        self.nmea_parser = NMEAParser()
        self.gps_data = self.nmea_parser.parse_file(nmea_path)
        
        # Initialize detector
        self.detector = RoadDamageDetector(model_path, conf_threshold)
        
        # Initialize database
        self.db = Database(db_path)
        
        # Initialize geocoder
        self.geocoder = Geocoder()
        
        # Create output directory for detected issues
        self.output_dir = Path("src/detected_issues")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize frame counter and timestamp
        self.current_frame = 0
        self.start_time = None
        
        # Initialize cooldown tracking
        self.cooldown_period = 3.0  # 3 seconds cooldown
        self.last_detection_times = {}  # Maps issue type to last detection timestamp
        
        # Initialize road segment tracking
        self.current_segment = None
        self.segment_distance = 0.0
        self.segment_speeds = []
        self.segment_issues = 0
        self.segment_start_time = None
        self.segment_start_gps = None
        self.segment_length = 50.0  # meters between segments
        
    def get_frame_timestamp(self, frame_number: int) -> Optional[datetime]:
        """
        Calculate the timestamp for a given frame number.
        
        Args:
            frame_number: The frame number to get timestamp for
            
        Returns:
            The calculated timestamp or None if start time is not set
        """
        if self.start_time is None:
            return None
            
        # Calculate time offset from start
        seconds = frame_number / self.fps
        return self.start_time + timedelta(seconds=seconds)
        
    def find_closest_gps_data(self, timestamp: datetime) -> Optional[GPSData]:
        """
        Find the closest GPS data point for a given timestamp.
        
        Args:
            timestamp: The timestamp to find GPS data for
            
        Returns:
            The closest GPS data point or None if no data available
        """
        if not self.gps_data:
            return None
            
        # Find the closest GPS data point
        closest = min(self.gps_data, key=lambda x: abs((x.timestamp - timestamp).total_seconds()))
        return closest
        
    def process_frame(self, frame: np.ndarray, frame_number: int) -> Tuple[List[Detection], Optional[GPSData]]:
        """
        Process a single frame and return detections with GPS data.
        
        Args:
            frame: The frame to process
            frame_number: The frame number
            
        Returns:
            Tuple of (detections, gps_data)
        """
        # Get timestamp for this frame
        timestamp = self.get_frame_timestamp(frame_number)
        if timestamp is None:
            # Set start time to first GPS data point
            if self.gps_data:
                self.start_time = self.gps_data[0].timestamp
                timestamp = self.get_frame_timestamp(frame_number)
            else:
                return [], None
                
        # Get closest GPS data
        gps_data = self.find_closest_gps_data(timestamp)
        if gps_data is None:
            return [], None
            
        # Update road segment
        self._update_road_segment(gps_data, timestamp)
            
        # Detect road issues
        detections = self.detector.detect(frame)
        
        # Filter detections based on cooldown
        filtered_detections = []
        for detection in detections:
            issue_type = detection.class_name
            last_detection = self.last_detection_times.get(issue_type)
            
            # If no previous detection or enough time has passed
            if last_detection is None or (timestamp - last_detection).total_seconds() >= self.cooldown_period:
                filtered_detections.append(detection)
                self.last_detection_times[issue_type] = timestamp
                self.segment_issues += 1
        
        return filtered_detections, gps_data
        
    def _update_road_segment(self, gps_data: GPSData, timestamp: datetime):
        """Update the current road segment with new GPS data."""
        if self.segment_start_gps is None:
            # Start new segment
            self.segment_start_gps = gps_data
            self.segment_start_time = timestamp
            self.segment_distance = 0.0
            self.segment_speeds = []
            self.segment_issues = 0
        else:
            # Calculate distance from last point
            distance = self.nmea_parser.calculate_distance(self.segment_start_gps, gps_data)
            self.segment_distance += distance
            
            # Add speed to segment
            if gps_data.speed_knots > 0:
                self.segment_speeds.append(gps_data.speed_knots)
            
            # If we've traveled enough distance, save the segment
            if self.segment_distance >= self.segment_length:
                # Calculate average speed
                avg_speed = sum(self.segment_speeds) / len(self.segment_speeds) if self.segment_speeds else 0.0
                
                # Create and save segment
                segment = RoadSegment(
                    start_latitude=self.segment_start_gps.latitude_decimal,
                    start_longitude=self.segment_start_gps.longitude_decimal,
                    end_latitude=gps_data.latitude_decimal,
                    end_longitude=gps_data.longitude_decimal,
                    start_time=self.segment_start_time,
                    end_time=timestamp,
                    issue_count=self.segment_issues,
                    average_speed=avg_speed,
                    distance=self.segment_distance
                )
                self.db.add_road_segment(segment)
                
                # Reset for next segment
                self.segment_start_gps = gps_data
                self.segment_start_time = timestamp
                self.segment_distance = 0.0
                self.segment_speeds = []
                self.segment_issues = 0
        
    def process_video(self) -> List[RoadIssue]:
        """
        Process the entire video and store detected issues in the database.
        
        Returns:
            List of RoadIssue objects that were stored in the database
        """
        stored_issues = []
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
                
            # Process frame
            detections, gps_data = self.process_frame(frame, self.current_frame)
            
            if detections and gps_data:
                # Draw detections on frame
                self.detector.draw_detections(frame, detections)
                
                # Save annotated frame
                output_path = self.output_dir / f"issue_{self.current_frame:06d}.jpg"
                cv2.imwrite(str(output_path), frame)
                
                # Store each detection in the database
                for detection in detections:
                    # Get address information
                    address_info = self.geocoder.reverse_geocode(
                        gps_data.latitude_decimal,
                        gps_data.longitude_decimal
                    )
                    
                    # Create RoadIssue object with relative path
                    issue = RoadIssue(
                        timestamp=gps_data.timestamp,
                        latitude=gps_data.latitude_decimal,
                        longitude=gps_data.longitude_decimal,
                        issue_type=detection.class_name,
                        confidence=detection.confidence,
                        image_path=f"issue_{self.current_frame:06d}.jpg",  # Store only filename
                        bbox=detection.bbox,
                        speed=gps_data.speed_knots,
                        fix_quality=gps_data.fix_quality,
                        num_satellites=gps_data.num_satellites,
                        hdop=gps_data.hdop,
                        city=address_info.get('city') if address_info else None,
                        district=address_info.get('district') if address_info else None,
                        street=address_info.get('street') if address_info else None
                    )
                    
                    # Store in database
                    issue_id = self.db.add_issue(issue)
                    issue.id = issue_id
                    stored_issues.append(issue)
                
            self.current_frame += 1
            
            # Print progress
            if self.current_frame % 100 == 0:
                progress = (self.current_frame / self.frame_count) * 100
                print(f"Processing: {progress:.1f}% complete")
                
        return stored_issues
        
    def release(self):
        """Release video capture resources and close database connection."""
        if self.cap is not None:
            self.cap.release()
        if self.db is not None:
            self.db.close()
            
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release() 