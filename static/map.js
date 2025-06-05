// Utility function to debounce function calls
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Global variables
let map;
let markers = [];
let heatmapLayer = null;
let markerClusterGroup = null;
let roadSegmentsLayer = null;
let currentFilters = {
    status: 'all',
    issueType: 'all',
    dateRange: 'all',
    city: 'all'
};

// Global variables for pagination
let currentPage = 1;
let isLoading = false;
let hasMoreData = true;

// Map layers
const mapLayers = {
    street: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }),
    satellite: L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: '&copy; Esri'
    }),
    dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    })
};

// Issue type colors
const issueColors = {
    'Pothole': '#FF0000',
    'Manhole': '#808080',
    'Alligator Crack': '#FF6B00',
    'Transversal Crack': '#FFD700',
    'Longitudinal Crack': '#87CEEB',
    'Patchy Road Section': '#4CAF50',
    'Other': '#000000'
};

// Status colors
const statusColors = {
    'New': '#FF0000',
    'In Progress': '#FFA500',
    'Done': '#008000',
    'False Positive': '#808080'
};

// Road segment colors based on issue density
const segmentColors = {
    low: '#00FF00',    // Green - 0-1 issues
    medium: '#FFFF00', // Yellow - 2-3 issues
    high: '#FFA500',   // Orange - 4-5 issues
    veryHigh: '#FF0000' // Red - 6+ issues
};

// Define colors for different issue types
const issueTypeColors = {
    'Alligator Cracks': '#FFA500',  // Orange-Yellow
    'Longitudinal Cracks': '#FFFF00',  // Yellow
    'Manhole Covers': '#808080',  // Grey
    'Patchy Road Sections': '#00FF00',  // Green
    'Potholes': '#FF0000',  // Red
    'Transverse Cracks': '#FF8C00'  // Dark Orange
};

// Create a custom control for the filter panel
L.Control.Filters = L.Control.extend({
    options: {
        position: 'topleft'
    },

    onAdd: function(map) {
        const container = L.DomUtil.create('div', 'leaflet-control-filters');
        if (document.documentElement.classList.contains('dark')) {
            container.classList.add('dark');
        }

        // Create filter controls
        const filters = `
            <div class="space-y-4">
                <div>
                    <label class="filter-label ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">Issue Type</label>
                    <select id="mapIssueTypeFilter" class="filter-select ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">
                        <option value="all">All Types</option>
                        <option value="Potholes">Potholes</option>
                        <option value="Alligator Cracks">Alligator Cracks</option>
                        <option value="Longitudinal Cracks">Longitudinal Cracks</option>
                        <option value="Transverse Cracks">Transverse Cracks</option>
                        <option value="Manhole Covers">Manhole Covers</option>
                        <option value="Patchy Road Sections">Patchy Road Sections</option>
                    </select>
                </div>
                <div>
                    <label class="filter-label ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">Status</label>
                    <select id="mapStatusFilter" class="filter-select ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">
                        <option value="all">All Statuses</option>
                        <option value="pending">Pending</option>
                        <option value="in_progress">In Progress</option>
                        <option value="fixed">Fixed</option>
                        <option value="false_positive">False Positive</option>
                    </select>
                </div>
                <div>
                    <label class="filter-label ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">Date Range</label>
                    <select id="mapDateRangeFilter" class="filter-select ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">
                        <option value="all">All Time</option>
                        <option value="today">Today</option>
                        <option value="week">Last 7 Days</option>
                        <option value="month">Last 30 Days</option>
                    </select>
                </div>
                <div>
                    <label class="filter-label ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">City</label>
                    <select id="mapCityFilter" class="filter-select ${document.documentElement.classList.contains('dark') ? 'dark' : ''}">
                        <option value="all">All Cities</option>
                    </select>
                </div>
            </div>
        `;

        container.innerHTML = filters;
        container.style.display = 'none'; // Initially hidden

        // Add event listeners for filters
        container.querySelectorAll('select').forEach(select => {
            select.addEventListener('change', () => {
                currentFilters = {
                    issueType: document.getElementById('mapIssueTypeFilter').value,
                    status: document.getElementById('mapStatusFilter').value,
                    dateRange: document.getElementById('mapDateRangeFilter').value,
                    city: document.getElementById('mapCityFilter').value
                };
                fetchAndDisplayIssues();
            });
        });

        return container;
    }
});

// Create a custom control for the filter toggle button
L.Control.FiltersToggle = L.Control.extend({
    options: {
        position: 'topleft'
    },

    onAdd: function(map) {
        const container = L.DomUtil.create('div', 'leaflet-control-filters-toggle');
        if (document.documentElement.classList.contains('dark')) {
            container.classList.add('dark');
        }
        container.innerHTML = '<i class="fas fa-filter"></i>';
        
        container.onclick = function() {
            const filtersPanel = document.querySelector('.leaflet-control-filters');
            if (filtersPanel.style.display === 'none') {
                filtersPanel.style.display = 'block';
            } else {
                filtersPanel.style.display = 'none';
            }
        };

        return container;
    }
});

// Create custom control for road segments toggle
L.Control.RoadSegmentsToggle = L.Control.extend({
    options: {
        position: 'topleft'
    },

    onAdd: function(map) {
        const container = L.DomUtil.create('div', 'leaflet-control-road-segments-toggle leaflet-bar leaflet-control');
        const button = L.DomUtil.create('a', 'leaflet-control-zoom-in', container);
        button.innerHTML = '<i class="fas fa-road"></i>';
        button.title = 'Toggle Road Segments';
        button.href = '#';
        
        // Prevent map click when clicking the button
        L.DomEvent.disableClickPropagation(button);
        L.DomEvent.on(button, 'click', L.DomEvent.stop);
        
        // Add click handler
        L.DomEvent.on(button, 'click', () => {
            if (roadSegmentsLayer) {
                if (map.hasLayer(roadSegmentsLayer)) {
                    map.removeLayer(roadSegmentsLayer);
                    button.classList.remove('active');
                } else {
                    map.addLayer(roadSegmentsLayer);
                    button.classList.add('active');
                }
            } else {
                // Try to fetch and create the layer if it doesn't exist
                fetchAndDisplayRoadSegments().then(() => {
                    if (roadSegmentsLayer) {
                        map.addLayer(roadSegmentsLayer);
                        button.classList.add('active');
                    }
                });
            }
        });
        
        return container;
    }
});

// Initialize map and controls
function initMap() {
    // Initialize map centered on Turkey
    map = L.map('map').setView([39.9334, 32.8597], 6);
    
    // Add default layer
    mapLayers.street.addTo(map);
    
    // Add layer control
    L.control.layers({
        'Street Map': mapLayers.street,
        'Satellite': mapLayers.satellite,
        'Dark Map': mapLayers.dark
    }).addTo(map);

    // Initialize marker cluster group with improved settings
    markerClusterGroup = L.markerClusterGroup({
        maxClusterRadius: 30,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: true,
        zoomToBoundsOnClick: true,
        disableClusteringAtZoom: 16,
        spiderfyDistanceMultiplier: 1.5,
        chunkedLoading: true,
        spiderLegPolylineOptions: { 
            weight: 2, 
            color: '#666', 
            opacity: 0.7,
            dashArray: '5, 5'
        },
        spiderfyDistance: 60,
        animate: true,
        animateAddingMarkers: true
    });
    map.addLayer(markerClusterGroup);

    // Add scroll event listener for infinite loading
    map.on('moveend', debounce(() => {
        const bounds = map.getBounds();
        const zoom = map.getZoom();
        
        // Only load more data if we're zoomed in enough
        if (zoom >= 12 && hasMoreData && !isLoading) {
            fetchAndDisplayIssues(true);
        }
    }, 250));

    // Add reset view button
    L.Control.ResetView = L.Control.extend({
        onAdd: function() {
            const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            const button = L.DomUtil.create('a', 'leaflet-control-reset-view', container);
            button.innerHTML = '<i class="fas fa-globe-americas"></i>';
            button.title = 'Reset View';
            button.href = '#';
            button.onclick = (e) => {
                L.DomEvent.stopPropagation(e);
                L.DomEvent.preventDefault(e);
                map.setView([39.9334, 32.8597], 6);
            };
            return container;
        }
    });
    L.control.resetView = function(opts) {
        return new L.Control.ResetView(opts);
    };
    L.control.resetView({position: 'topleft'}).addTo(map);

    // Add fullscreen button
    L.Control.Fullscreen = L.Control.extend({
        onAdd: function() {
            const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            const button = L.DomUtil.create('a', 'leaflet-control-fullscreen', container);
            button.innerHTML = '<i class="fas fa-expand"></i>';
            button.title = 'Toggle Fullscreen';
            button.href = '#';
            button.onclick = (e) => {
                L.DomEvent.stopPropagation(e);
                L.DomEvent.preventDefault(e);
                const mapContainer = document.getElementById('map');
                if (!document.fullscreenElement) {
                    mapContainer.requestFullscreen();
                } else {
                    document.exitFullscreen();
                }
            };
            return container;
        }
    });
    L.control.fullscreen = function(opts) {
        return new L.Control.Fullscreen(opts);
    };
    L.control.fullscreen({position: 'topleft'}).addTo(map);

    // Add heatmap toggle button
    L.Control.HeatmapToggle = L.Control.extend({
        onAdd: function() {
            const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
            const button = L.DomUtil.create('a', 'leaflet-control-heatmap-toggle', container);
            button.innerHTML = '<i class="fas fa-fire"></i>';
            button.title = 'Toggle Heatmap';
            button.href = '#';
            button.onclick = (e) => {
                L.DomEvent.stopPropagation(e);
                L.DomEvent.preventDefault(e);
                if (heatmapLayer) {
                    map.removeLayer(heatmapLayer);
                    heatmapLayer = null;
                } else {
                    createHeatmap();
                }
            };
            return container;
        }
    });
    L.control.heatmapToggle = function(opts) {
        return new L.Control.HeatmapToggle(opts);
    };
    L.control.heatmapToggle({position: 'topleft'}).addTo(map);

    // Add the filter controls
    const filtersControl = new L.Control.Filters();
    const filtersToggle = new L.Control.FiltersToggle();
    map.addControl(filtersControl);
    map.addControl(filtersToggle);

    // Add road segments toggle control
    new L.Control.RoadSegmentsToggle().addTo(map);

    // Get issue ID from URL if present
    const urlParams = new URLSearchParams(window.location.search);
    const issueId = urlParams.get('issue_id');

    // Load initial data
    fetchAndDisplayIssues().then(() => {
        // Load road segments
        fetchAndDisplayRoadSegments();
        
        // If an issue ID was provided, find and focus on that marker
        if (issueId) {
            const targetMarker = markers.find(marker => {
                const popup = marker.getPopup();
                const content = popup.getContent();
                return content.includes(`ID:</span> ${issueId}`);
            });

            if (targetMarker) {
                map.setView(targetMarker.getLatLng(), 16);
                targetMarker.openPopup();
                markerClusterGroup.on('add', function() {
                    targetMarker.openPopup();
                });
            }
        }
    });

    // Update the legend after map initialization
    updateLegend();
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', initMap);

// Create heatmap layer
function createHeatmap() {
    const heatmapData = markers.map(marker => {
        const latLng = marker.getLatLng();
        return {
            lat: latLng.lat,
            lng: latLng.lng,
            value: 1
        };
    });

    heatmapLayer = L.heatLayer(heatmapData, {
        radius: 25,
        blur: 15,
        maxZoom: 10
    }).addTo(map);
}

// Fetch and display issues on the map
async function fetchAndDisplayIssues(append = false) {
    if (isLoading || !hasMoreData) {
        console.log('Skipping fetch:', { isLoading, hasMoreData });
        return;
    }
    
    try {
        isLoading = true;
        console.log('Fetching page:', currentPage);
        
        const url = new URL(`${window.location.origin}/api/map_issues`);
        
        // Add filters to URL parameters
        if (currentFilters.issueType !== 'all') {
            url.searchParams.set('issueType', currentFilters.issueType);
        }
        if (currentFilters.status !== 'all') {
            url.searchParams.set('status', currentFilters.status);
        }
        if (currentFilters.dateRange !== 'all') {
            url.searchParams.set('dateRange', currentFilters.dateRange);
        }
        if (currentFilters.city !== 'all') {
            url.searchParams.set('city', currentFilters.city);
        }
        
        // Add pagination parameters
        url.searchParams.set('page', currentPage);
        url.searchParams.set('per_page', 100);

        console.log('Fetching URL:', url.toString());
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Received data:', {
            issuesCount: data.issues.length,
            total: data.total,
            pages: data.pages,
            currentPage: data.current_page
        });
        
        // Update markers with append parameter
        updateMarkers(data.issues, append);
        
        // Update pagination state
        hasMoreData = currentPage < data.pages;
        currentPage++;
        
        console.log('Updated pagination state:', {
            hasMoreData,
            currentPage,
            totalPages: data.pages
        });
        
        // Update road segments when filters change
        if (!append && roadSegmentsLayer) {
            map.removeLayer(roadSegmentsLayer);
            await fetchAndDisplayRoadSegments();
        }
        
    } catch (error) {
        console.error('Error fetching issues:', error);
        showNotification('Error loading road issues', 'error');
    } finally {
        isLoading = false;
    }
}

// Get marker icon based on issue type and status
function getMarkerIcon(issueType, status) {
    const issueTypeColors = {
        'Potholes': '#FF0000',  // Red
        'Alligator Cracks': '#FFA500',  // Orange-Yellow
        'Longitudinal Cracks': '#FFFF00',  // Yellow
        'Transverse Cracks': '#FF8C00',  // Dark Orange
        'Manhole Covers': '#808080',  // Grey
        'Patchy Road Sections': '#00FF00'  // Green
    };

    const color = issueTypeColors[issueType] || '#6c757d';

    return L.divIcon({
        className: 'custom-div-icon',
        html: `
            <div style="
                position: relative;
                width: 30px;
                height: 30px;
            ">
                <div style="
                    position: absolute;
                    width: 20px;
                    height: 20px;
                    background: ${color};
                    border: 2px solid white;
                    border-radius: 50%;
                    left: 5px;
                    top: 5px;
                    box-shadow: 0 0 3px rgba(0,0,0,0.5);
                "></div>
                <div style="
                    position: absolute;
                    width: 0;
                    height: 0;
                    border-left: 6px solid transparent;
                    border-right: 6px solid transparent;
                    border-top: 10px solid ${color};
                    left: 9px;
                    top: 25px;
                    filter: drop-shadow(0 1px 1px rgba(0,0,0,0.3));
                "></div>
            </div>
        `,
        iconSize: [30, 35],
        iconAnchor: [15, 35]
    });
}

// Helper function to add small random offset to coordinates
function addRandomOffset(lat, lng) {
    // Add a very small random offset (about 1-2 meters)
    const offset = 0.00001; // Approximately 1 meter
    return [
        lat + (Math.random() * offset * 2 - offset),
        lng + (Math.random() * offset * 2 - offset)
    ];
}

// Update markers on the map
function updateMarkers(issues, append = false) {
    // Only clear existing markers if not appending
    if (!append) {
        markers.forEach(marker => marker.remove());
        markers = [];
        markerClusterGroup.clearLayers();
    }

    if (!issues) {
        // If no issues provided, fetch them
        fetchAndDisplayIssues();
        return;
    }

    // Group issues by coordinates to handle duplicates
    const coordinateGroups = {};
    issues.forEach(issue => {
        const key = `${issue.latitude},${issue.longitude}`;
        if (!coordinateGroups[key]) {
            coordinateGroups[key] = [];
        }
        coordinateGroups[key].push(issue);
    });

    // Add new markers with offset for duplicates
    Object.values(coordinateGroups).forEach(group => {
        if (group.length === 1) {
            // Single marker at this coordinate
            const issue = group[0];
            const marker = L.marker([issue.latitude, issue.longitude], {
                icon: getMarkerIcon(issue.type || issue.issue_type, issue.status)
            });
            marker.bindPopup(createPopupContent(issue));
            markers.push(marker);
            markerClusterGroup.addLayer(marker);
        } else {
            // Multiple markers at the same coordinate
            group.forEach(issue => {
                const [lat, lng] = addRandomOffset(issue.latitude, issue.longitude);
                const marker = L.marker([lat, lng], {
                    icon: getMarkerIcon(issue.type || issue.issue_type, issue.status)
                });
                marker.bindPopup(createPopupContent(issue));
                markers.push(marker);
                markerClusterGroup.addLayer(marker);
            });
        }
    });

    // Update heatmap if active
    if (heatmapLayer) {
        map.removeLayer(heatmapLayer);
        createHeatmap();
    }

    // Only fit bounds if not appending
    if (!append && markers.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

// Create popup content for a marker
function createPopupContent(issue) {
    // Parse the timestamp properly
    let timestamp;
    try {
        // Try parsing as ISO string first
        timestamp = new Date(issue.timestamp);
        
        // If invalid, try parsing as a different format
        if (isNaN(timestamp.getTime())) {
            // Try parsing as a string with timezone
            timestamp = new Date(issue.timestamp.replace(' ', 'T') + 'Z');
        }
        
        // If still invalid, use current date as fallback
        if (isNaN(timestamp.getTime())) {
            console.warn('Invalid timestamp format:', issue.timestamp);
            timestamp = new Date();
        }
    } catch (error) {
        console.error('Error parsing timestamp:', error);
        timestamp = new Date();
    }

    console.log('Issue data in popup:', issue); // Debug log
    return `
        <div class="issue-popup">
            <img src="/road_issue/image/${issue.id}" alt="Road Issue ${issue.id}">
            <div class="space-y-2">
                <div>
                    <span class="font-semibold">ID:</span> ${issue.id}
                </div>
                <div>
                    <span class="font-semibold">Type:</span> ${issue.type || issue.issue_type || 'Unknown'}
                </div>
                <div>
                    <span class="font-semibold">Status:</span> 
                    <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadgeClass(issue.status)}">
                        ${issue.status || 'pending'}
                    </span>
                </div>
                <div>
                    <span class="font-semibold">Date:</span> ${timestamp.toLocaleDateString()}
                </div>
                <div>
                    <span class="font-semibold">Time:</span> ${timestamp.toLocaleTimeString()}
                </div>
                <div>
                    <span class="font-semibold">Location:</span> ${issue.address || `${issue.latitude}, ${issue.longitude}`}
                </div>
                <div class="flex space-x-2 mt-2">
                    <button onclick="updateIssueStatus(${issue.id}, 'in_progress')" class="text-yellow-600 hover:text-yellow-900">
                        <i class="fas fa-clock"></i> In Progress
                    </button>
                    <button onclick="updateIssueStatus(${issue.id}, 'fixed')" class="text-green-600 hover:text-green-900">
                        <i class="fas fa-check"></i> Fixed
                    </button>
                    <button onclick="deleteIssue(${issue.id})" class="text-red-600 hover:text-red-900">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            </div>
        </div>
    `;
}

// Update issue status
async function updateIssueStatus(issueId, newStatus) {
    try {
        console.log(`Updating issue ${issueId} to status: ${newStatus}`); // Debug log
        const response = await fetch(`/road_issue/${issueId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Update response:', result); // Debug log

        if (result.message) {
            showNotification('Status updated successfully', 'success');
            // Refresh the markers to show updated status
            await fetchAndDisplayIssues();
        } else {
            throw new Error('Failed to update status');
        }
    } catch (error) {
        console.error('Error updating issue status:', error);
        showNotification('Error updating status: ' + error.message, 'error');
    }
}

// Delete issue
async function deleteIssue(issueId) {
    if (!confirm('Are you sure you want to delete this issue?')) return;

    try {
        console.log(`Deleting issue ${issueId}`); // Debug log
        const response = await fetch(`/road_issue/${issueId}/delete`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const result = await response.json();
        console.log('Delete response:', result); // Debug log

        if (result.message) {
            showNotification('Issue deleted successfully', 'success');
            // Refresh the markers to remove deleted issue
            await fetchAndDisplayIssues();
        } else {
            throw new Error('Failed to delete issue');
        }
    } catch (error) {
        console.error('Error deleting issue:', error);
        showNotification('Error deleting issue: ' + error.message, 'error');
    }
}

// Get status badge class
function getStatusBadgeClass(status) {
    const classes = {
        'pending': 'bg-red-100 text-red-800',
        'in_progress': 'bg-yellow-100 text-yellow-800',
        'fixed': 'bg-green-100 text-green-800',
        'false_positive': 'bg-gray-100 text-gray-800'
    };
    return classes[status] || 'bg-gray-100 text-gray-800';
}

// Show notification
function showNotification(message, type = 'success') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
    notification.style.zIndex = '9999';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Fetch and display road segments
async function fetchAndDisplayRoadSegments() {
    try {
        const url = new URL(`${window.location.origin}/api/road_segments`);
        
        // Add date range filter
        if (currentFilters.dateRange !== 'all') {
            url.searchParams.set('dateRange', currentFilters.dateRange);
        }

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const segments = await response.json();
        
        // Create a new layer for road segments
        roadSegmentsLayer = L.layerGroup();
        
        // Group segments by their start coordinates to identify continuous paths
        const segmentGroups = [];
        let currentGroup = [];
        
        for (let i = 0; i < segments.length; i++) {
            const segment = segments[i];
            currentGroup.push(segment);
            
            // Check if this is the last segment or if the next segment is not adjacent
            if (i === segments.length - 1 || 
                !isAdjacentSegment(segment, segments[i + 1])) {
                segmentGroups.push(currentGroup);
                currentGroup = [];
            }
        }
        
        // Process each group of segments
        segmentGroups.forEach(group => {
            // Calculate aggregated data for the group
            const groupData = {
                totalIssues: group.reduce((sum, seg) => sum + seg.issue_count, 0),
                totalDistance: group.reduce((sum, seg) => sum + (seg.distance || 0), 0),
                weightedSpeed: group.reduce((sum, seg) => {
                    if (seg.average_speed && seg.distance) {
                        return sum + (seg.average_speed * seg.distance);
                    }
                    return sum;
                }, 0),
                startTime: new Date(group[0].start_time),
                endTime: new Date(group[group.length - 1].end_time)
            };
            
            // Calculate issues per kilometer
            const distanceKm = groupData.totalDistance / 1000;
            const issuesPerKm = distanceKm > 0 ? groupData.totalIssues / distanceKm : groupData.totalIssues;
            
            // Determine color based on issues per kilometer
            let color;
            if (issuesPerKm <= 1) {
                color = segmentColors.low;
            } else if (issuesPerKm <= 3) {
                color = segmentColors.medium;
            } else if (issuesPerKm <= 5) {
                color = segmentColors.high;
            } else {
                color = segmentColors.veryHigh;
            }
            
            // Create polylines for each segment in the group
            group.forEach(segment => {
                const polyline = L.polyline([
                    [segment.start_latitude, segment.start_longitude],
                    [segment.end_latitude, segment.end_longitude]
                ], {
                    color: color,
                    weight: 5,
                    opacity: 0.7,
                    smoothFactor: 1
                });
                
                // Add popup with aggregated group information
                const popupContent = `
                    <div class="segment-popup">
                        <h4>Road Section</h4>
                        <p><strong>Total Issues:</strong> ${groupData.totalIssues}</p>
                        <p><strong>Issues per km:</strong> ${issuesPerKm.toFixed(1)}</p>
                        <p><strong>Average Speed:</strong> ${(groupData.weightedSpeed / groupData.totalDistance).toFixed(1) || 'N/A'} knots</p>
                        <p><strong>Total Distance:</strong> ${(groupData.totalDistance / 1000).toFixed(1)} km</p>
                        <p><strong>Time:</strong> ${groupData.startTime.toLocaleString()} - ${groupData.endTime.toLocaleString()}</p>
                    </div>
                `;
                
                polyline.bindPopup(popupContent);
                roadSegmentsLayer.addLayer(polyline);
            });
        });
        
        return roadSegmentsLayer;
        
    } catch (error) {
        console.error('Error fetching road segments:', error);
        showNotification('Error loading road segments', 'error');
        return null;
    }
}

// Helper function to check if two segments are adjacent
function isAdjacentSegment(segment1, segment2) {
    if (!segment1 || !segment2) return false;
    
    const coordThreshold = 0.0001; // Approximately 11 meters
    const timeThreshold = 5; // 5 seconds
    
    const coordMatch = 
        Math.abs(segment1.end_latitude - segment2.start_latitude) < coordThreshold &&
        Math.abs(segment1.end_longitude - segment2.start_longitude) < coordThreshold;
    
    const timeMatch = 
        (new Date(segment2.start_time) - new Date(segment1.end_time)) / 1000 < timeThreshold;
    
    return coordMatch && timeMatch;
}

// Update the legend in the page
function updateLegend() {
    const legendContainer = document.querySelector('.legend-container');
    if (!legendContainer) return;

    // Add road segments section to the legend
    const roadSegmentsLegend = document.createElement('div');
    roadSegmentsLegend.className = 'legend-section';
    roadSegmentsLegend.innerHTML = `
        <h3>Road Segments</h3>
        <div class="legend-item">
            <div class="legend-color" style="background-color: ${segmentColors.low}"></div>
            <span>0-1 issues/km</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: ${segmentColors.medium}"></div>
            <span>1-3 issues/km</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: ${segmentColors.high}"></div>
            <span>3-5 issues/km</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background-color: ${segmentColors.veryHigh}"></div>
            <span>5+ issues/km</span>
        </div>
    `;

    // Add the road segments legend after the status legend
    const statusLegend = legendContainer.querySelector('.legend-section:last-child');
    if (statusLegend) {
        statusLegend.after(roadSegmentsLegend);
    } else {
        legendContainer.appendChild(roadSegmentsLegend);
    }
}

// Reset pagination when filters change
function resetPagination() {
    currentPage = 1;
    hasMoreData = true;
    markers = [];
    markerClusterGroup.clearLayers();
    fetchAndDisplayIssues(false);
}

// Add filter change listeners
document.querySelectorAll('.filter-control').forEach(control => {
    control.addEventListener('change', () => {
        resetPagination();
    });
}); 