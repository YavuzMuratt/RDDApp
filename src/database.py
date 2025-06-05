import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
import json

@dataclass
class RoadIssue:
    """Class representing a detected road issue in the database."""
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    issue_type: Optional[str] = None
    confidence: Optional[float] = None
    image_path: Optional[str] = None
    status: str = "pending"  # pending, in_progress, fixed, false_positive
    notes: Optional[str] = None
    bbox: Optional[Tuple[int, int, int, int]] = None  # x1, y1, x2, y2
    speed: Optional[float] = None
    fix_quality: Optional[int] = None
    num_satellites: Optional[int] = None
    hdop: Optional[float] = None
    city: Optional[str] = None
    district: Optional[str] = None
    street: Optional[str] = None

@dataclass
class RoadSegment:
    """Class representing a processed road segment in the database."""
    id: Optional[int] = None
    start_latitude: float = None
    start_longitude: float = None
    end_latitude: float = None
    end_longitude: float = None
    start_time: datetime = None
    end_time: datetime = None
    issue_count: int = 0
    average_speed: float = None
    distance: float = None  # in meters

class Database:
    def __init__(self, db_path: str = "road_issues.db"):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        
    def _create_tables(self):
        """Create necessary database tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Create road_issues table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS road_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                issue_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                image_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT,
                bbox TEXT,  -- JSON string of [x1, y1, x2, y2]
                speed REAL,
                fix_quality INTEGER,
                num_satellites INTEGER,
                hdop REAL,
                city TEXT,
                district TEXT,
                street TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create road_segments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS road_segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_latitude REAL,
                start_longitude REAL,
                end_latitude REAL,
                end_longitude REAL,
                start_time DATETIME,
                end_time DATETIME,
                issue_count INTEGER DEFAULT 0,
                average_speed REAL,
                distance REAL
            )
        """)
        
        # Create index on coordinates for faster spatial queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_coordinates 
            ON road_issues(latitude, longitude)
        """)
        
        # Create index on timestamp for faster time-based queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON road_issues(timestamp)
        """)
        
        # Create index on address fields for faster filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_city 
            ON road_issues(city)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_district 
            ON road_issues(district)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_street 
            ON road_issues(street)
        """)
        
        self.conn.commit()
        
    def add_issue(self, issue: RoadIssue) -> int:
        """
        Add a new road issue to the database.
        
        Args:
            issue: RoadIssue object containing the issue data
            
        Returns:
            The ID of the newly created issue
        """
        cursor = self.conn.cursor()
        
        # Convert bbox tuple to JSON string
        bbox_json = json.dumps(issue.bbox) if issue.bbox else None
        
        cursor.execute("""
            INSERT INTO road_issues (
                timestamp, latitude, longitude, issue_type, confidence,
                image_path, status, notes, bbox, speed, fix_quality,
                num_satellites, hdop, city, district, street
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            issue.timestamp, issue.latitude, issue.longitude,
            issue.issue_type, issue.confidence, issue.image_path,
            issue.status, issue.notes, bbox_json, issue.speed,
            issue.fix_quality, issue.num_satellites, issue.hdop,
            issue.city, issue.district, issue.street
        ))
        
        self.conn.commit()
        return cursor.lastrowid
        
    def get_issue(self, issue_id: int) -> Optional[RoadIssue]:
        """
        Retrieve a road issue by its ID.
        
        Args:
            issue_id: The ID of the issue to retrieve
            
        Returns:
            RoadIssue object or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM road_issues WHERE id = ?", (issue_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
            
        return self._row_to_issue(row)
        
    def update_issue(self, issue: RoadIssue) -> bool:
        """
        Update an existing road issue.
        
        Args:
            issue: RoadIssue object with updated data
            
        Returns:
            True if update was successful, False otherwise
        """
        if not issue.id:
            return False
            
        cursor = self.conn.cursor()
        
        # Convert bbox tuple to JSON string
        bbox_json = json.dumps(issue.bbox) if issue.bbox else None
        
        cursor.execute("""
            UPDATE road_issues SET
                timestamp = ?,
                latitude = ?,
                longitude = ?,
                issue_type = ?,
                confidence = ?,
                image_path = ?,
                status = ?,
                notes = ?,
                bbox = ?,
                speed = ?,
                fix_quality = ?,
                num_satellites = ?,
                hdop = ?,
                city = ?,
                district = ?,
                street = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            issue.timestamp, issue.latitude, issue.longitude,
            issue.issue_type, issue.confidence, issue.image_path,
            issue.status, issue.notes, bbox_json, issue.speed,
            issue.fix_quality, issue.num_satellites, issue.hdop,
            issue.city, issue.district, issue.street,
            issue.id
        ))
        
        self.conn.commit()
        return cursor.rowcount > 0
        
    def delete_issue(self, issue_id: int) -> bool:
        """
        Delete a road issue.
        
        Args:
            issue_id: The ID of the issue to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM road_issues WHERE id = ?", (issue_id,))
        self.conn.commit()
        return cursor.rowcount > 0
        
    def get_issues(
        self,
        status: Optional[str] = None,
        issue_type: Optional[str] = None,
        city: Optional[str] = None,
        district: Optional[str] = None,
        street: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_confidence: Optional[float] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "DESC"
    ) -> List[RoadIssue]:
        """
        Retrieve road issues with optional filtering.
        
        Args:
            status: Filter by status
            issue_type: Filter by issue type
            city: Filter by city
            district: Filter by district
            street: Filter by street
            start_date: Filter by start date
            end_date: Filter by end date
            min_confidence: Filter by minimum confidence
            limit: Maximum number of issues to return
            offset: Number of issues to skip
            sort_by: Field to sort by
            sort_order: Sort order (ASC or DESC)
            
        Returns:
            List of RoadIssue objects
        """
        cursor = self.conn.cursor()
        query = "SELECT * FROM road_issues WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
            
        if issue_type:
            query += " AND issue_type = ?"
            params.append(issue_type)
            
        if city:
            query += " AND city = ?"
            params.append(city)
            
        if district:
            query += " AND district = ?"
            params.append(district)
            
        if street:
            query += " AND street = ?"
            params.append(street)
            
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
            
        if min_confidence:
            query += " AND confidence >= ?"
            params.append(min_confidence)
            
        # Add sorting
        if sort_by:
            query += f" ORDER BY {sort_by} {sort_order}"
        else:
            query += " ORDER BY timestamp DESC"
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
            
        if offset is not None:
            query += " OFFSET ?"
            params.append(offset)
            
        cursor.execute(query, params)
        return [self._row_to_issue(row) for row in cursor.fetchall()]
        
    def get_issues_in_area(
        self,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        status: Optional[str] = None
    ) -> List[RoadIssue]:
        """
        Retrieve road issues within a geographical area.
        
        Args:
            min_lat: Minimum latitude
            max_lat: Maximum latitude
            min_lon: Minimum longitude
            max_lon: Maximum longitude
            status: Optional status filter
            
        Returns:
            List of RoadIssue objects
        """
        cursor = self.conn.cursor()
        query = """
            SELECT * FROM road_issues 
            WHERE latitude BETWEEN ? AND ?
            AND longitude BETWEEN ? AND ?
        """
        params = [min_lat, max_lat, min_lon, max_lon]
        
        if status:
            query += " AND status = ?"
            params.append(status)
            
        cursor.execute(query, params)
        return [self._row_to_issue(row) for row in cursor.fetchall()]
        
    def get_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        issue_type: Optional[str] = None,
        status: Optional[str] = None,
        city: Optional[str] = None
    ) -> dict:
        """
        Get comprehensive statistics about road issues using database-level aggregation.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            issue_type: Optional issue type filter
            status: Optional status filter
            city: Optional city filter
            
        Returns:
            Dictionary containing various statistics
        """
        cursor = self.conn.cursor()
        
        # Build base query conditions
        conditions = []
        params = []
        
        if start_date:
            conditions.append("timestamp >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("timestamp <= ?")
            params.append(end_date)
        if issue_type:
            conditions.append("issue_type = ?")
            params.append(issue_type)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if city:
            conditions.append("city = ?")
            params.append(city)
            
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM road_issues WHERE {where_clause}", params)
        total_issues = cursor.fetchone()[0]
        
        # Get today's count
        today = datetime.now().date()
        today_params = params + [today]
        cursor.execute(f"""
            SELECT COUNT(*) FROM road_issues 
            WHERE {where_clause} AND DATE(timestamp) = DATE(?)
        """, today_params)
        issues_today = cursor.fetchone()[0]
        
        # Get status distribution
        cursor.execute(f"""
            SELECT status, COUNT(*) 
            FROM road_issues 
            WHERE {where_clause}
            GROUP BY status
        """, params)
        status_counts = dict(cursor.fetchall())
        
        # Get issue type distribution
        cursor.execute(f"""
            SELECT issue_type, COUNT(*) 
            FROM road_issues 
            WHERE {where_clause}
            GROUP BY issue_type
        """, params)
        type_counts = dict(cursor.fetchall())
        
        # Get monthly trend
        cursor.execute(f"""
            SELECT strftime('%Y-%m', timestamp) as month, COUNT(*) 
            FROM road_issues 
            WHERE {where_clause}
            GROUP BY month
            ORDER BY month
        """, params)
        monthly_trend = dict(cursor.fetchall())
        
        # Calculate daily average
        if start_date:
            end = end_date or datetime.now()
            delta = end - start_date
            days = delta.days or 1  # Use delta.days instead of .days
            daily_average = total_issues / days
        else:
            cursor.execute("""
                SELECT 
                    (julianday(MAX(timestamp)) - julianday(MIN(timestamp))) as days
                FROM road_issues
                WHERE 1=1
            """)
            days = cursor.fetchone()[0] or 1
            daily_average = total_issues / days
        
        # Get top problem areas
        cursor.execute(f"""
            SELECT 
                city || ', ' || COALESCE(district, 'Unknown District') || ', ' || COALESCE(street, 'Unknown Street') as area,
                COUNT(*) as count,
                AVG(latitude) as avg_lat,
                AVG(longitude) as avg_lon
            FROM road_issues 
            WHERE {where_clause}
            GROUP BY area
            ORDER BY count DESC
            LIMIT 5
        """, params)
        top_areas = [(row[0], row[1], f"{row[2]:.6f}, {row[3]:.6f}") for row in cursor.fetchall()]
        
        return {
            "total_issues": total_issues,
            "issues_today": issues_today,
            "status_counts": status_counts,
            "type_counts": type_counts,
            "monthly_trend": monthly_trend,
            "daily_average": daily_average,
            "top_areas": top_areas
        }
        
    def bulk_update_status(self, issue_ids: List[int], new_status: str) -> None:
        """
        Update status for multiple issues in a single transaction.
        
        Args:
            issue_ids: List of issue IDs to update
            new_status: New status to set
        """
        cursor = self.conn.cursor()
        cursor.executemany(
            """
            UPDATE road_issues 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [(new_status, issue_id) for issue_id in issue_ids]
        )
        self.conn.commit()
        
    def bulk_delete_issues(self, issue_ids: List[int]) -> None:
        """
        Delete multiple issues in a single transaction.
        
        Args:
            issue_ids: List of issue IDs to delete
        """
        cursor = self.conn.cursor()
        cursor.executemany(
            "DELETE FROM road_issues WHERE id = ?",
            [(issue_id,) for issue_id in issue_ids]
        )
        self.conn.commit()
        
    def get_issue_image_paths(self, issue_ids: List[int]) -> List[Optional[str]]:
        """
        Get image paths for multiple issues.
        
        Args:
            issue_ids: List of issue IDs
            
        Returns:
            List of image paths (None for issues without images)
        """
        cursor = self.conn.cursor()
        cursor.executemany(
            "SELECT image_path FROM road_issues WHERE id = ?",
            [(issue_id,) for issue_id in issue_ids]
        )
        return [row[0] for row in cursor.fetchall()]
        
    def bulk_add_issues(self, issues: List[RoadIssue]) -> None:
        """
        Add multiple issues in a single transaction.
        
        Args:
            issues: List of RoadIssue objects to add
        """
        cursor = self.conn.cursor()
        cursor.executemany(
            """
            INSERT INTO road_issues (
                timestamp, latitude, longitude, issue_type, confidence,
                image_path, status, notes, bbox, speed, fix_quality,
                num_satellites, hdop, city, district, street
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(
                issue.timestamp, issue.latitude, issue.longitude,
                issue.issue_type, issue.confidence, issue.image_path,
                issue.status, issue.notes, json.dumps(issue.bbox) if issue.bbox else None,
                issue.speed, issue.fix_quality, issue.num_satellites,
                issue.hdop, issue.city, issue.district, issue.street
            ) for issue in issues]
        )
        self.conn.commit()
        
    def _row_to_issue(self, row: sqlite3.Row) -> RoadIssue:
        """Convert a database row to a RoadIssue object."""
        bbox = json.loads(row["bbox"]) if row["bbox"] else None
        return RoadIssue(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            latitude=row["latitude"],
            longitude=row["longitude"],
            issue_type=row["issue_type"],
            confidence=row["confidence"],
            image_path=row["image_path"],
            status=row["status"],
            notes=row["notes"],
            bbox=tuple(bbox) if bbox else None,
            speed=row["speed"],
            fix_quality=row["fix_quality"],
            num_satellites=row["num_satellites"],
            hdop=row["hdop"],
            city=row["city"],
            district=row["district"],
            street=row["street"]
        )
        
    def add_road_segment(self, segment: RoadSegment) -> int:
        """Add a new road segment to the database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO road_segments (
                start_latitude, start_longitude, end_latitude, end_longitude,
                start_time, end_time, issue_count, average_speed, distance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            segment.start_latitude, segment.start_longitude,
            segment.end_latitude, segment.end_longitude,
            segment.start_time, segment.end_time,
            segment.issue_count, segment.average_speed, segment.distance
        ))
        self.conn.commit()
        return cursor.lastrowid
        
    def get_road_segments(self, start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> List[RoadSegment]:
        """Get road segments with optional date filtering."""
        cursor = self.conn.cursor()
        query = "SELECT * FROM road_segments"
        params = []
        
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append("start_time >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("end_time <= ?")
                params.append(end_date)
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY start_time"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        segments = []
        for row in rows:
            segments.append(RoadSegment(
                id=row[0],
                start_latitude=row[1],
                start_longitude=row[2],
                end_latitude=row[3],
                end_longitude=row[4],
                start_time=datetime.fromisoformat(row[5]) if row[5] else None,
                end_time=datetime.fromisoformat(row[6]) if row[6] else None,
                issue_count=row[7],
                average_speed=row[8],
                distance=row[9]
            ))
            
        return segments
        
    def get_merged_road_segments(self, start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[RoadSegment]:
        """Get road segments with adjacent segments merged based on coordinates and timestamps."""
        cursor = self.conn.cursor()
        query = "SELECT * FROM road_segments"
        params = []
        
        if start_date or end_date:
            conditions = []
            if start_date:
                conditions.append("start_time >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("end_time <= ?")
                params.append(end_date)
            query += " WHERE " + " AND ".join(conditions)
            
        query += " ORDER BY start_time"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        # Convert rows to RoadSegment objects
        segments = []
        for row in rows:
            segments.append(RoadSegment(
                id=row[0],
                start_latitude=row[1],
                start_longitude=row[2],
                end_latitude=row[3],
                end_longitude=row[4],
                start_time=datetime.fromisoformat(row[5]) if row[5] else None,
                end_time=datetime.fromisoformat(row[6]) if row[6] else None,
                issue_count=row[7],
                average_speed=row[8],
                distance=row[9]
            ))
        
        # Merge adjacent segments
        merged_segments = []
        current_segment = segments[0]
        
        for next_segment in segments[1:]:
            # Check if segments are adjacent (end of current matches start of next)
            if (abs(current_segment.end_latitude - next_segment.start_latitude) < 0.0001 and
                abs(current_segment.end_longitude - next_segment.start_longitude) < 0.0001 and
                (next_segment.start_time - current_segment.end_time).total_seconds() < 5):  # 5 seconds threshold
                
                # Merge segments
                current_segment.end_latitude = next_segment.end_latitude
                current_segment.end_longitude = next_segment.end_longitude
                current_segment.end_time = next_segment.end_time
                current_segment.issue_count += next_segment.issue_count
                
                # Calculate weighted average speed
                if current_segment.distance and next_segment.distance:
                    total_distance = current_segment.distance + next_segment.distance
                    current_segment.average_speed = (
                        (current_segment.average_speed * current_segment.distance) +
                        (next_segment.average_speed * next_segment.distance)
                    ) / total_distance
                    current_segment.distance = total_distance
                elif next_segment.distance:
                    current_segment.average_speed = next_segment.average_speed
                    current_segment.distance = next_segment.distance
            else:
                merged_segments.append(current_segment)
                current_segment = next_segment
        
        # Add the last segment
        merged_segments.append(current_segment)
        
        return merged_segments
        
    def close(self):
        """Close the database connection."""
        self.conn.close()
        
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close() 