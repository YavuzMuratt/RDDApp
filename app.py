from flask import Flask, render_template, jsonify, request, send_file, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import io
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from flask_caching import Cache

from src.database import Database, RoadIssue

def get_date_range(date_range: str) -> tuple[datetime, datetime]:
    """
    Calculate start and end dates based on the date range parameter.
    
    Args:
        date_range: One of 'today', 'week', 'month', or 'all'
        
    Returns:
        Tuple of (start_date, end_date)
    """
    now = datetime.now()
    end_date = now
    
    if date_range == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'week':
        start_date = now - timedelta(days=7)
    elif date_range == 'month':
        start_date = now - timedelta(days=30)
    else:  # 'all'
        start_date = None
        
    return start_date, end_date

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['DB_PATH'] = 'src/road_issues.db'

# Configure Flask-Caching
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300  # Cache for 5 minutes
})

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Hardcoded user for demo purposes
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Hardcoded credentials for demo
        if username == 'admin' and password == 'admin':
            user = User(1)
            login_user(user)
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Main routes
@app.route('/')
@login_required
def dashboard():
    with Database(app.config['DB_PATH']) as db:
        # Get summary statistics
        total_issues = len(db.get_issues())
        issues_today = len(db.get_issues(
            start_date=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ))
        
        # Get issue type distribution
        issues = db.get_issues()
        issue_types = {}
        for issue in issues:
            issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1
        
        # Get status distribution
        status_distribution = {}
        for issue in issues:
            status_distribution[issue.status] = status_distribution.get(issue.status, 0) + 1
    
    return render_template('dashboard.html',
                         total_issues=total_issues,
                         issues_today=issues_today,
                         issue_types=issue_types,
                         status_distribution=status_distribution)

@app.route('/map')
@login_required
def map_page():
    # Create a map centered at a default location
    m = folium.Map(location=[40.7128, -74.0060], zoom_start=12)
    
    # Add a marker cluster
    marker_cluster = MarkerCluster().add_to(m)
    
    # Add markers for each road issue
    with Database(app.config['DB_PATH']) as db:
        issues = db.get_issues()
        for issue in issues:
            popup = f"""
                <b>Type:</b> {issue.issue_type}<br>
                <b>Status:</b> {issue.status}<br>
                <b>Date:</b> {issue.timestamp.strftime('%Y-%m-%d %H:%M')}<br>
                <b>Location:</b> {issue.latitude:.6f}, {issue.longitude:.6f}<br>
                <b>Confidence:</b> {issue.confidence:.2f}
            """
            if issue.image_path:
                popup += f'<br><img src="/road_issue/image/{issue.id}" width="200">'
            
            folium.Marker(
                location=[issue.latitude, issue.longitude],
                popup=popup,
                icon=folium.Icon(
                    color='red' if issue.status == 'pending' else 
                          'orange' if issue.status == 'in_progress' else 
                          'green' if issue.status == 'fixed' else 'gray'
                )
            ).add_to(marker_cluster)
    
    # Save the map to a temporary file
    map_path = os.path.join('static', 'map.html')
    m.save(map_path)
    
    return render_template('map.html', map_path=map_path)

@app.route('/stats')
@login_required
def stats():
    with Database(app.config['DB_PATH']) as db:
        # Get detailed statistics
        total_issues = len(db.get_issues())
        issues_today = len(db.get_issues(
            start_date=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ))
        
        # Get daily average
        issues = db.get_issues()
        if issues:
            first_issue = min(issues, key=lambda x: x.timestamp)
            days = (datetime.now() - first_issue.timestamp).days or 1
            daily_average = total_issues / days
        else:
            daily_average = 0
        
        # Get issue type distribution
        issue_types = {}
        for issue in issues:
            issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1
        
        # Get status distribution
        status_distribution = {}
        for issue in issues:
            status_distribution[issue.status] = status_distribution.get(issue.status, 0) + 1
        
        # Get issues over time
        issues_over_time = {}
        for issue in issues:
            date = issue.timestamp.date()
            issues_over_time[date] = issues_over_time.get(date, 0) + 1
    
    return render_template('stats.html',
                         total_issues=total_issues,
                         issues_today=issues_today,
                         daily_average=daily_average,
                         issue_types=issue_types,
                         status_distribution=status_distribution,
                         issues_over_time=issues_over_time,
                         current_time=datetime.now())

# API routes
@app.route('/api/road_issues')
@login_required
def get_road_issues():
    # Get query parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    status = request.args.get('status', 'all')
    type = request.args.get('type', 'all')
    city = request.args.get('city', 'all')
    
    with Database(app.config['DB_PATH']) as db:
        # Get issues with filters
        issues = db.get_issues(
            status=status if status != 'all' else None,
            issue_type=type if type != 'all' else None,
            city=city if city != 'all' else None
        )
        
        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_issues = issues[start_idx:end_idx]
        
        return jsonify({
            'issues': [{
                'id': issue.id,
                'timestamp': issue.timestamp.isoformat(),
                'type': issue.issue_type,
                'status': issue.status,
                'latitude': issue.latitude,
                'longitude': issue.longitude,
                'confidence': issue.confidence,
                'speed': issue.speed,
                'image_path': issue.image_path,
                'city': issue.city,
                'district': issue.district,
                'street': issue.street,
                'address': f"{issue.street or ''}, {issue.district or ''}, {issue.city or ''}".strip(', ')
            } for issue in paginated_issues],
            'total': len(issues),
            'pages': (len(issues) + per_page - 1) // per_page,
            'current_page': page
        })

@app.route('/road_issue/<int:issue_id>')
@login_required
def get_road_issue(issue_id):
    try:
        with Database(app.config['DB_PATH']) as db:
            issue = db.get_issue(issue_id)
            if not issue:
                return jsonify({'error': 'Issue not found'}), 404
                
            # Convert issue to dict for JSON serialization
            issue_dict = {
                'id': issue.id,
                'timestamp': issue.timestamp.isoformat() if issue.timestamp else None,
                'type': issue.issue_type,  # Map issue_type to type
                'status': issue.status,
                'confidence': issue.confidence,
                'latitude': issue.latitude,
                'longitude': issue.longitude,
                'address': f"{issue.street or ''}, {issue.district or ''}, {issue.city or ''}".strip(', '),
                'notes': issue.notes,
                'image_path': issue.image_path
            }
            return jsonify(issue_dict)
    except Exception as e:
        print(f"Error in get_road_issue: {str(e)}")  # Add server-side logging
        return jsonify({'error': str(e)}), 500

@app.route('/road_issue/image/<int:issue_id>')
@login_required
def get_road_issue_image(issue_id):
    try:
        with Database(app.config['DB_PATH']) as db:
            issue = db.get_issue(issue_id)
            if not issue or not issue.image_path:
                return jsonify({'error': 'Image not found'}), 404
                
            # Use the src/src/detected_issues directory
            image_path = os.path.join('src', 'src', 'detected_issues', issue.image_path)
            
            if not os.path.exists(image_path):
                return jsonify({'error': 'Image file not found'}), 404
                
            return send_file(image_path, mimetype='image/jpeg')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/road_issue/<int:issue_id>/update', methods=['POST'])
@login_required
def update_road_issue(issue_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        with Database(app.config['DB_PATH']) as db:
            issue = db.get_issue(issue_id)
            if not issue:
                return jsonify({'error': 'Issue not found'}), 404
                
            # Update status if provided
            if 'status' in data:
                issue.status = data['status']
                
            # Update notes if provided
            if 'notes' in data:
                issue.notes = data['notes']
                
            # Save changes
            db.update_issue(issue)
            
        return jsonify({'message': 'Issue updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/road_issue/<int:issue_id>/delete', methods=['POST'])
@login_required
def delete_issue(issue_id):
    with Database(app.config['DB_PATH']) as db:
        issue = db.get_issue(issue_id)
        if not issue:
            return jsonify({'error': 'Issue not found'}), 404
            
        # Delete image file if it exists
        if issue.image_path:
            try:
                os.remove(os.path.join('src', 'src', 'detected_issues', issue.image_path))
            except OSError:
                pass
                
        if db.delete_issue(issue_id):
            return jsonify({'message': 'Issue deleted successfully'})
        return jsonify({'error': 'Failed to delete issue'}), 500

@app.route('/api/dashboard_stats')
@login_required
def get_dashboard_stats():
    with Database(app.config['DB_PATH']) as db:
        # Get total issues
        total_issues = len(db.get_issues())
        
        # Get issues from today
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        issues_today = len(db.get_issues(start_date=today))
        
        # Get issue type distribution
        issues = db.get_issues()
        issue_types = {}
        for issue in issues:
            issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1
        
        # Get most common issue type
        most_common_issue = max(issue_types.items(), key=lambda x: x[1])[0] if issue_types else 'None'
        
        # Get status distribution
        status_distribution = {}
        for issue in issues:
            status_distribution[issue.status] = status_distribution.get(issue.status, 0) + 1
        
        response = jsonify({
            'total_issues': total_issues,
            'issues_today': issues_today,
            'most_common_issue': most_common_issue,
            'issue_types': issue_types,
            'status_distribution': status_distribution
        })
        
        # Add cache control headers to prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response

@app.route('/api/cities_with_issues')
@login_required
def get_cities_with_issues():
    with Database(app.config['DB_PATH']) as db:
        issues = db.get_issues()
        cities = set()
        for issue in issues:
            # In a real application, you would use reverse geocoding here
            # For now, we'll just use coordinates as a placeholder
            cities.add(f"{issue.latitude:.6f}, {issue.longitude:.6f}")
        
        return jsonify(list(cities))

@app.route('/api/stats')
@login_required
def get_statistics():
    # Get query parameters
    date_range = request.args.get('dateRange', 'all')
    issue_type = request.args.get('issueType', 'all')
    status = request.args.get('status', 'all')
    city = request.args.get('city', 'all')
    
    start_date, end_date = get_date_range(date_range)
    
    with Database(app.config['DB_PATH']) as db:
        # Get statistics using database-level aggregation
        stats = db.get_statistics(
            start_date=start_date,
            end_date=end_date,
            issue_type=issue_type if issue_type != 'all' else None,
            status=status if status != 'all' else None,
            city=city if city != 'all' else None
        )
        
        return jsonify({
            'total_issues': stats['total_issues'],
            'issues_today': stats['issues_today'],
            'issue_types': stats['type_counts'],
            'status_distribution': stats['status_counts'],
            'monthly_trend': stats['monthly_trend'],
            'daily_average': stats['daily_average'],
            'top_areas': stats['top_areas'],
            'last_updated': datetime.now().isoformat()
        })

@app.route('/api/map_issues')
@login_required
@cache.cached(timeout=300, query_string=True)  # Cache for 5 minutes, vary by query parameters
def get_map_issues():
    # Get query parameters
    issue_type = request.args.get('issueType', 'all')
    status = request.args.get('status', 'all')
    date_range = request.args.get('dateRange', 'all')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 100))  # Load 100 issues at a time
    
    # Calculate date range
    now = datetime.now()
    start_date = None
    
    if date_range == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'week':
        start_date = now - timedelta(days=7)
    elif date_range == 'month':
        start_date = now - timedelta(days=30)
    
    with Database(app.config['DB_PATH']) as db:
        # Get issues with filters and pagination
        issues = db.get_issues(
            start_date=start_date,
            issue_type=issue_type if issue_type != 'all' else None,
            status=status if status != 'all' else None,
            limit=per_page,
            offset=(page - 1) * per_page
        )
        
        # Get total count for pagination
        total_issues = len(db.get_issues(
            start_date=start_date,
            issue_type=issue_type if issue_type != 'all' else None,
            status=status if status != 'all' else None
        ))
        
        return jsonify({
            'issues': [{
                'id': issue.id,
                'latitude': issue.latitude,
                'longitude': issue.longitude,
                'issue_type': issue.issue_type,
                'status': issue.status,
                'confidence': issue.confidence,
                'image_path': issue.image_path,
                'timestamp': issue.timestamp.isoformat() if issue.timestamp else None
            } for issue in issues],
            'total': total_issues,
            'pages': (total_issues + per_page - 1) // per_page,
            'current_page': page
        })

@app.route('/export_to_csv')
@login_required
def export_to_csv():
    # Get query parameters
    date_range = request.args.get('dateRange', 'all')
    issue_type = request.args.get('issueType', 'all')
    status = request.args.get('status', 'all')
    
    with Database(app.config['DB_PATH']) as db:
        # Calculate date range
        now = datetime.now()
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = None
        
        # Get issues with filters
        issues = db.get_issues(
            start_date=start_date,
            issue_type=issue_type if issue_type != 'all' else None,
            status=status if status != 'all' else None
        )
        
        # Create DataFrame
        df = pd.DataFrame([{
            'ID': issue.id,
            'Timestamp': issue.timestamp,
            'Issue Type': issue.issue_type,
            'Status': issue.status,
            'Latitude': issue.latitude,
            'Longitude': issue.longitude,
            'Confidence': issue.confidence,
            'Speed': issue.speed,
            'Fix Quality': issue.fix_quality,
            'Num Satellites': issue.num_satellites,
            'HDOP': issue.hdop,
            'Image Path': issue.image_path
        } for issue in issues])
        
        # Create CSV
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='road_issues.csv'
        )

@app.route('/api/export_stats')
@login_required
def export_stats():
    # Get query parameters
    format = request.args.get('format', 'csv')
    date_range = request.args.get('dateRange', 'all')
    issue_type = request.args.get('issueType', 'all')
    status = request.args.get('status', 'all')
    city = request.args.get('city', 'all')
    
    with Database(app.config['DB_PATH']) as db:
        # Calculate date range
        now = datetime.now()
        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif date_range == 'week':
            start_date = now - timedelta(days=7)
        elif date_range == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = None
        
        # Get issues with filters
        issues = db.get_issues(
            start_date=start_date,
            issue_type=issue_type if issue_type != 'all' else None,
            status=status if status != 'all' else None,
            city=city if city != 'all' else None
        )
        
        # Create DataFrame with all requested columns
        df = pd.DataFrame([{
            'ID': issue.id,
            'Issue Type': issue.issue_type,
            'Status': issue.status,
            'Address': f"{issue.street or ''}, {issue.district or ''}, {issue.city or ''}".strip(', '),
            'Timestamp': issue.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Latitude': issue.latitude,
            'Longitude': issue.longitude,
            'Confidence': issue.confidence,
            'Speed': issue.speed,
            'Fix Quality': issue.fix_quality,
            'Num Satellites': issue.num_satellites,
            'HDOP': issue.hdop,
            'Image Path': issue.image_path,
            'Notes': issue.notes
        } for issue in issues])
        
        if format == 'csv':
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name='road_issues.csv'
            )
        elif format == 'excel':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Road Issues')
            output.seek(0)
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='road_issues.xlsx'
            )
        elif format == 'pdf':
            # Create PDF using reportlab
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            # Create PDF with proper margins and landscape orientation
            output = io.BytesIO()
            # Use landscape orientation and adjust page size
            page_width, page_height = landscape(letter)
            doc = SimpleDocTemplate(output, 
                                  pagesize=(page_width, page_height),
                                  rightMargin=10, leftMargin=10,
                                  topMargin=10, bottomMargin=10)
            elements = []
            
            # Add title
            styles = getSampleStyleSheet()
            title = Paragraph(f"Road Issues Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Title'])
            elements.append(title)
            elements.append(Spacer(1, 6))
            
            # Add filters info
            filters_text = []
            if city != 'all':
                filters_text.append(f"City: {city}")
            if date_range != 'all':
                filters_text.append(f"Date Range: {date_range.replace('_', ' ').title()}")
            if issue_type != 'all':
                filters_text.append(f"Issue Type: {issue_type}")
            if status != 'all':
                filters_text.append(f"Status: {status}")
            if filters_text:
                elements.append(Paragraph("Filters: " + ", ".join(filters_text), styles['Normal']))
                elements.append(Spacer(1, 6))
            
            # Convert DataFrame to list of lists for table
            table_data = [df.columns.tolist()] + df.values.tolist()
            
            # Define fixed column widths for landscape orientation
            col_widths = [
                0.4 * inch,  # ID
                1.0 * inch,  # Issue Type
                0.8 * inch,  # Status
                1.8 * inch,  # Address
                1.2 * inch,  # Timestamp
                0.8 * inch,  # Latitude
                0.8 * inch,  # Longitude
                0.7 * inch,  # Confidence
                0.7 * inch,  # Speed
                0.7 * inch,  # Fix Quality
                0.7 * inch,  # Num Satellites
                0.7 * inch,  # HDOP
                0.8 * inch,  # Image Path
                1.2 * inch   # Notes
            ]
            
            # Calculate total table width
            total_width = sum(col_widths)
            
            # If table is wider than page, scale it down
            if total_width > (page_width - 20):  # 20 is total of left and right margins
                scale_factor = (page_width - 20) / total_width
                col_widths = [w * scale_factor for w in col_widths]
            
            # Split table into chunks to handle page breaks
            chunk_size = 30  # Increased number of rows per page
            for i in range(0, len(table_data), chunk_size):
                if i > 0:
                    elements.append(PageBreak())
                chunk = table_data[i:i + chunk_size]
                
                # Create table with fixed column widths
                chunk_table = Table(chunk, colWidths=col_widths, repeatRows=1)
                
                # Define table style
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('WORDWRAP', (0, 0), (-1, -1), True),
                    ('LEADING', (0, 0), (-1, -1), 8)  # Line spacing
                ])
                
                chunk_table.setStyle(style)
                elements.append(chunk_table)
            
            # Add summary at the end
            elements.append(PageBreak())
            elements.append(Paragraph("Summary", styles['Title']))
            elements.append(Spacer(1, 6))
            
            summary_data = [
                ["Total Issues", str(len(issues))],
                ["Date Range", date_range],
                ["Issue Type Filter", issue_type],
                ["Status Filter", status],
                ["City Filter", city],
                ["Generated On", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            ]
            
            summary_table = Table(summary_data, colWidths=[1.2*inch, 4*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ]))
            
            elements.append(summary_table)
            
            # Build PDF
            doc.build(elements)
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/pdf',
                as_attachment=True,
                download_name='road_issues.pdf'
            )
        else:
            return jsonify({'error': 'Unsupported format'}), 400

@app.route('/api/import/csv', methods=['POST'])
@login_required
def import_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
        
    try:
        df = pd.read_csv(file)
        required_columns = ['timestamp', 'latitude', 'longitude', 'issue_type', 'confidence']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return jsonify({'error': f'Missing required columns: {", ".join(missing_columns)}'}), 400
            
        # Convert DataFrame to list of RoadIssue objects
        issues = []
        for _, row in df.iterrows():
            issue = RoadIssue(
                timestamp=datetime.fromisoformat(row['timestamp']),
                latitude=float(row['latitude']),
                longitude=float(row['longitude']),
                issue_type=row['issue_type'],
                confidence=float(row['confidence']),
                image_path=row.get('image_path'),
                status=row.get('status', 'pending'),
                notes=row.get('notes'),
                speed=float(row.get('speed', 0)),
                fix_quality=int(row.get('fix_quality', 0)),
                num_satellites=int(row.get('num_satellites', 0)),
                hdop=float(row.get('hdop', 0))
            )
            issues.append(issue)
            
        with Database(app.config['DB_PATH']) as db:
            # Use bulk insert
            db.bulk_add_issues(issues)
                
        return jsonify({'message': f'Successfully imported {len(issues)} issues'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/images', methods=['POST'])
@login_required
def import_images():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
        
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files selected'}), 400
        
    try:
        with Database(app.config['DB_PATH']) as db:
            for file in files:
                if file.filename == '':
                    continue
                    
                # Save the file in the src/src/detected_issues directory
                filename = f"issue_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
                os.makedirs(os.path.join('src', 'src', 'detected_issues'), exist_ok=True)
                file.save(os.path.join('src', 'src', 'detected_issues', filename))
                
                # Create a new issue with the image
                issue = RoadIssue(
                    timestamp=datetime.now(),
                    latitude=0.0,  # Default values, should be updated later
                    longitude=0.0,
                    issue_type='unknown',
                    confidence=0.0,
                    image_path=filename,
                    status='pending'
                )
                db.add_issue(issue)
                
        return jsonify({'message': 'Images imported successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk_update_status', methods=['POST'])
@login_required
def bulk_update_status():
    try:
        data = request.get_json()
        issue_ids = data.get('issue_ids', [])
        new_status = data.get('status')
        
        if not issue_ids or not new_status:
            return jsonify({'error': 'Missing required parameters'}), 400
            
        if new_status not in ['pending', 'in_progress', 'fixed', 'false_positive']:
            return jsonify({'error': 'Invalid status'}), 400
            
        with Database(app.config['DB_PATH']) as db:
            # Use a single transaction for all updates
            db.bulk_update_status(issue_ids, new_status)
                    
        return jsonify({'message': f'Updated status for {len(issue_ids)} issues'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk_delete_issues', methods=['POST'])
@login_required
def bulk_delete_issues():
    try:
        data = request.get_json()
        issue_ids = data.get('issue_ids', [])
        
        if not issue_ids:
            return jsonify({'error': 'No issues selected'}), 400
            
        with Database(app.config['DB_PATH']) as db:
            # Get image paths before deletion
            image_paths = db.get_issue_image_paths(issue_ids)
            
            # Delete issues in a single transaction
            db.bulk_delete_issues(issue_ids)
            
            # Delete image files
            for image_path in image_paths:
                if image_path:
                    try:
                        os.remove(os.path.join('src', 'src', 'detected_issues', image_path))
                    except OSError:
                        pass
                
        return jsonify({'message': f'Deleted {len(issue_ids)} issues'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cities')
@login_required
def get_cities():
    """Get a list of unique cities from the database."""
    try:
        with Database(app.config['DB_PATH']) as db:
            # Get all issues and extract unique cities
            issues = db.get_issues()
            cities = sorted(set(issue.city for issue in issues if issue.city))
            return jsonify(cities)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/road_segments')
@login_required
def get_road_segments():
    """Get road segments with optional date filtering."""
    # Get query parameters
    date_range = request.args.get('dateRange', 'all')
    
    # Calculate date range
    now = datetime.now()
    start_date = None
    
    if date_range == 'today':
        # Start of today
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == 'week':
        # Last 7 days
        start_date = now - timedelta(days=7)
    elif date_range == 'month':
        # Last 30 days
        start_date = now - timedelta(days=30)
    
    with Database(app.config['DB_PATH']) as db:
        # Use get_road_segments instead of get_merged_road_segments
        segments = db.get_road_segments(start_date=start_date)
        
        return jsonify([{
            'id': segment.id,
            'start_latitude': segment.start_latitude,
            'start_longitude': segment.start_longitude,
            'end_latitude': segment.end_latitude,
            'end_longitude': segment.end_longitude,
            'start_time': segment.start_time.isoformat() if segment.start_time else None,
            'end_time': segment.end_time.isoformat() if segment.end_time else None,
            'issue_count': segment.issue_count,
            'average_speed': segment.average_speed,
            'distance': segment.distance
        } for segment in segments])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True) 