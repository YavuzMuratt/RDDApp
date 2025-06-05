import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QProgressBar, QMessageBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox, QSplitter,
    QFrame, QStatusBar, QComboBox, QCheckBox, QTextEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QIcon, QPalette, QColor
import numpy as np
import cv2

from video_processor import VideoProcessor
from database import Database, RoadIssue
from detector import RoadDamageDetector

class VideoProcessorThread(QThread):
    """Thread for processing video in the background."""
    progress_updated = pyqtSignal(int)
    processing_finished = pyqtSignal(list)  # List of RoadIssue objects
    error_occurred = pyqtSignal(str)
    frame_ready = pyqtSignal(np.ndarray)  # Signal for processed frame

    def __init__(self, video_path: str, nmea_path: str, model_path: str, 
                 db_path: str, conf_threshold: float):
        super().__init__()
        self.video_path = video_path
        self.nmea_path = nmea_path
        self.model_path = model_path
        self.db_path = db_path
        self.conf_threshold = conf_threshold
        self.is_running = True
        self.processor = None

    def run(self):
        try:
            self.processor = VideoProcessor(
                self.video_path, 
                self.nmea_path, 
                self.model_path,
                self.db_path,
                self.conf_threshold
            )
            
            # Process video and get stored issues
            stored_issues = []
            while self.is_running and self.processor.cap.isOpened():
                ret, frame = self.processor.cap.read()
                if not ret:
                    break
                    
                # Process frame
                detections, gps_data = self.processor.process_frame(frame, self.processor.current_frame)
                
                if detections and gps_data:
                    # Draw detections on frame
                    self.processor.detector.draw_detections(frame, detections)
                    
                    # Save annotated frame
                    output_path = self.processor.output_dir / f"issue_{self.processor.current_frame:06d}.jpg"
                    cv2.imwrite(str(output_path), frame)
                    
                    # Store each detection in the database
                    for detection in detections:
                        # Get address information
                        address_info = self.processor.geocoder.reverse_geocode(
                            gps_data.latitude_decimal,
                            gps_data.longitude_decimal
                        )
                        
                        # Create RoadIssue object
                        issue = RoadIssue(
                            timestamp=gps_data.timestamp,
                            latitude=gps_data.latitude_decimal,
                            longitude=gps_data.longitude_decimal,
                            issue_type=detection.class_name,
                            confidence=detection.confidence,
                            image_path=f"issue_{self.processor.current_frame:06d}.jpg",  # Store only filename
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
                        issue_id = self.processor.db.add_issue(issue)
                        issue.id = issue_id
                        stored_issues.append(issue)
                        
                        # Save image in src/detected_issues directory
                        image_filename = f"issue_{self.processor.current_frame:06d}.jpg"
                        image_path = os.path.join('src', 'detected_issues', image_filename)
                        
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(image_path), exist_ok=True)
                        
                        # Save the image
                        cv2.imwrite(image_path, frame)
                
                # Emit frame for display
                self.frame_ready.emit(frame)
                
                # Update progress
                self.processor.current_frame += 1
                progress = (self.processor.current_frame / self.processor.frame_count) * 100
                self.progress_updated.emit(int(progress))
                
            self.processing_finished.emit(stored_issues)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.processor:
                self.processor.release()

    def stop(self):
        """Stop the video processing thread safely."""
        self.is_running = False
        if self.processor and self.processor.cap:
            self.processor.cap.release()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Road Damage Detection System")
        self.setMinimumSize(1200, 800)
        
        # Initialize paths
        self.video_path = None
        self.nmea_path = None
        self.model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "model", "mymodel.pt")
        self.db_path = "road_issues.db"
        
        # Initialize processing thread
        self.processing_thread = None
        
        # Setup UI
        self.setup_ui()
        
        # Apply dark theme
        self.apply_theme()
        
    def setup_ui(self):
        """Setup the main window UI."""
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel for controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(15)
        
        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)
        
        self.video_label = QLabel("No video file selected")
        self.nmea_label = QLabel("No NMEA file selected")
        
        self.video_button = QPushButton("Select Video File")
        self.nmea_button = QPushButton("Select NMEA File")
        
        file_layout.addWidget(self.video_label)
        file_layout.addWidget(self.video_button)
        file_layout.addWidget(self.nmea_label)
        file_layout.addWidget(self.nmea_button)
        
        # Parameters group
        param_group = QGroupBox("Detection Parameters")
        param_layout = QFormLayout(param_group)
        
        self.confidence_spinbox = QDoubleSpinBox()
        self.confidence_spinbox.setRange(0.0, 1.0)
        self.confidence_spinbox.setSingleStep(0.05)
        self.confidence_spinbox.setValue(0.5)
        
        param_layout.addRow("Confidence Threshold:", self.confidence_spinbox)
        
        # Progress group
        progress_group = QGroupBox("Processing Status")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Ready")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.process_button = QPushButton("Process Video")
        self.stop_button = QPushButton("Stop")
        self.export_button = QPushButton("Export Data")
        
        self.process_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.export_button.setEnabled(False)
        
        control_layout.addWidget(self.process_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.export_button)
        
        # Add all widgets to left panel
        left_layout.addWidget(file_group)
        left_layout.addWidget(param_group)
        left_layout.addWidget(progress_group)
        left_layout.addLayout(control_layout)
        left_layout.addStretch()
        
        # Right panel with tabs
        right_panel = QTabWidget()
        
        # Video display tab
        video_tab = QWidget()
        video_layout = QVBoxLayout(video_tab)
        
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background-color: black;")
        
        video_layout.addWidget(self.video_label)
        
        # Issues tab
        issues_tab = QWidget()
        issues_layout = QVBoxLayout(issues_tab)
        
        self.issues_table = QTableWidget()
        self.issues_table.setColumnCount(8)
        self.issues_table.setHorizontalHeaderLabels([
            "ID", "Timestamp", "Type", "Confidence", "Latitude", "Longitude",
            "Speed", "Status"
        ])
        self.issues_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        issues_layout.addWidget(self.issues_table)
        
        # Statistics tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        
        stats_layout.addWidget(self.stats_text)
        
        # Add tabs
        right_panel.addTab(video_tab, "Video")
        right_panel.addTab(issues_tab, "Detected Issues")
        right_panel.addTab(stats_tab, "Statistics")
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        # Create status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")
        
        # Connect signals
        self.video_button.clicked.connect(self.select_video)
        self.nmea_button.clicked.connect(self.select_nmea)
        self.process_button.clicked.connect(self.process_video)
        self.stop_button.clicked.connect(self.stop_processing)
        self.export_button.clicked.connect(self.export_data)
        
    def apply_theme(self):
        """Apply dark theme to the application."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            
            QGroupBox {
                background-color: #3c3f41;
                border: 1px solid #4b4b4b;
                border-radius: 8px;
                margin-top: 1.5ex;
                padding: 15px;
                font-weight: 500;
                color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px 0 5px;
                color: #ffffff;
            }
            
            QPushButton {
                background-color: #4b6eaf;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #5b7ebf;
            }
            
            QPushButton:pressed {
                background-color: #3b5e9f;
            }
            
            QPushButton:disabled {
                background-color: #3c3f41;
                color: #6c6c6c;
            }
            
            QLabel {
                color: #ffffff;
            }
            
            QProgressBar {
                border: 1px solid #4b4b4b;
                border-radius: 4px;
                text-align: center;
                background-color: #3c3f41;
                color: #ffffff;
            }
            
            QProgressBar::chunk {
                background-color: #4b6eaf;
                border-radius: 3px;
            }
            
            QTableWidget {
                background-color: #3c3f41;
                color: #ffffff;
                gridline-color: #4b4b4b;
                border: 1px solid #4b4b4b;
            }
            
            QTableWidget::item {
                padding: 5px;
            }
            
            QHeaderView::section {
                background-color: #4b4b4b;
                color: #ffffff;
                padding: 5px;
                border: 1px solid #4b4b4b;
            }
            
            QTextEdit {
                background-color: #3c3f41;
                color: #ffffff;
                border: 1px solid #4b4b4b;
                border-radius: 4px;
            }
            
            QStatusBar {
                background-color: #2b2b2b;
                color: #ffffff;
                border-top: 1px solid #4b4b4b;
            }
            
            QSplitter::handle {
                background: #4b4b4b;
                width: 2px;
            }
        """)
        
    def select_video(self):
        """Open file dialog to select video file."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov);;All Files (*)"
        )
        if file_name:
            self.video_path = file_name
            self.video_label.setText(f"Video: {os.path.basename(file_name)}")
            self.check_files_selected()
            
    def select_nmea(self):
        """Open file dialog to select NMEA file."""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select NMEA File",
            "",
            "NMEA Files (*.nmea);;All Files (*)"
        )
        if file_name:
            self.nmea_path = file_name
            self.nmea_label.setText(f"NMEA: {os.path.basename(file_name)}")
            self.check_files_selected()
            
    def check_files_selected(self):
        """Enable process button if both files are selected."""
        self.process_button.setEnabled(
            self.video_path is not None and 
            self.nmea_path is not None
        )
        
    def process_video(self):
        """Start video processing in a separate thread."""
        if self.video_path and self.nmea_path:
            self.processing_thread = VideoProcessorThread(
                self.video_path,
                self.nmea_path,
                self.model_path,
                self.db_path,
                self.confidence_spinbox.value()
            )
            
            self.processing_thread.progress_updated.connect(self.update_progress)
            self.processing_thread.processing_finished.connect(self.processing_finished)
            self.processing_thread.error_occurred.connect(self.show_error)
            self.processing_thread.frame_ready.connect(self.display_frame)
            
            self.processing_thread.start()
            
            self.process_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText("Processing...")
            self.statusBar.showMessage("Processing video...")
            
    def stop_processing(self):
        """Stop the video processing thread."""
        if self.processing_thread:
            self.processing_thread.stop()
            self.processing_thread.wait()
            self.processing_finished()
            
    def update_progress(self, value):
        """Update the progress bar."""
        self.progress_bar.setValue(value)
        
    def processing_finished(self, issues: Optional[List[RoadIssue]] = None):
        """Handle completion of video processing."""
        self.process_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.export_button.setEnabled(True)
        self.status_label.setText("Processing completed")
        self.progress_bar.setValue(0)
        self.statusBar.showMessage("Processing completed")
        
        if issues:
            self.update_issues_table(issues)
            self.update_statistics()
            
    def show_error(self, error_message):
        """Show error message in a dialog."""
        QMessageBox.critical(self, "Error", f"An error occurred: {error_message}")
        self.processing_finished()
        
    def update_issues_table(self, issues: List[RoadIssue]):
        """Update the issues table with new data."""
        self.issues_table.setRowCount(len(issues))
        
        for row, issue in enumerate(issues):
            self.issues_table.setItem(row, 0, QTableWidgetItem(str(issue.id)))
            self.issues_table.setItem(row, 1, QTableWidgetItem(
                issue.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ))
            self.issues_table.setItem(row, 2, QTableWidgetItem(issue.issue_type))
            self.issues_table.setItem(row, 3, QTableWidgetItem(
                f"{issue.confidence:.2f}"
            ))
            self.issues_table.setItem(row, 4, QTableWidgetItem(
                f"{issue.latitude:.6f}"
            ))
            self.issues_table.setItem(row, 5, QTableWidgetItem(
                f"{issue.longitude:.6f}"
            ))
            self.issues_table.setItem(row, 6, QTableWidgetItem(
                f"{issue.speed:.1f}"
            ))
            self.issues_table.setItem(row, 7, QTableWidgetItem(issue.status))
            
    def update_statistics(self):
        """Update the statistics tab with database statistics."""
        with Database(self.db_path) as db:
            stats = db.get_statistics()
            
            stats_text = f"""
            Total Issues: {stats['total_issues']}
            
            Status Distribution:
            {self.format_dict(stats['status_counts'])}
            
            Issue Type Distribution:
            {self.format_dict(stats['type_counts'])}
            
            Average Confidence: {stats['average_confidence']:.2f}
            """
            
            self.stats_text.setText(stats_text)
            
    def format_dict(self, d: dict) -> str:
        """Format a dictionary for display in statistics."""
        return "\n".join(f"  {k}: {v}" for k, v in d.items())
        
    def export_data(self):
        """Export detected issues to a CSV file."""
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_name:
            with Database(self.db_path) as db:
                issues = db.get_issues()
                
                with open(file_name, 'w') as f:
                    # Write header
                    f.write("ID,Timestamp,Type,Confidence,Latitude,Longitude,Speed,Status\n")
                    
                    # Write data
                    for issue in issues:
                        f.write(f"{issue.id},{issue.timestamp},{issue.issue_type},"
                               f"{issue.confidence},{issue.latitude},{issue.longitude},"
                               f"{issue.speed},{issue.status}\n")
                
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Data exported successfully to {file_name}"
                )

    def display_frame(self, frame: np.ndarray):
        """Display a processed frame."""
        # Convert frame to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert to QImage
        height, width, channel = frame_rgb.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        
        # Scale image to fit label while maintaining aspect ratio
        pixmap = QPixmap.fromImage(q_image)
        scaled_pixmap = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Display image
        self.video_label.setPixmap(scaled_pixmap)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec()) 