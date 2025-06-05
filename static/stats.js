// Global variables
let currentFilters = {
    dateRange: 'all',
    issueType: 'all',
    status: 'all',
    city: 'all'
};

// Chart instances
let issueTypeChart, statusChart, monthlyTrendChart;

// Initialize the statistics page
document.addEventListener('DOMContentLoaded', function() {
    // Add event listeners
    document.getElementById('dateRangeFilter').addEventListener('change', updateFilters);
    document.getElementById('issueTypeFilter').addEventListener('change', updateFilters);
    document.getElementById('statusFilter').addEventListener('change', updateFilters);
    document.getElementById('cityFilter').addEventListener('change', updateFilters);

    // Add theme change listener
    const themeObserver = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'class') {
                updateChartsTheme();
            }
        });
    });
    themeObserver.observe(document.documentElement, { attributes: true });

    // Initialize charts
    initializeCharts();
    
    // Load initial data and populate city filter
    fetchAndDisplayStats();
    populateCityFilter();
});

// Populate city filter dropdown
async function populateCityFilter() {
    try {
        const response = await fetch('/api/cities');
        if (!response.ok) throw new Error('Failed to fetch cities');
        
        const cities = await response.json();
        const cityFilter = document.getElementById('cityFilter');
        
        // Clear existing options except "All Cities"
        while (cityFilter.options.length > 1) {
            cityFilter.remove(1);
        }
        
        // Add city options
        cities.forEach(city => {
            if (city && city.trim()) {  // Only add non-null and non-empty cities
                const option = document.createElement('option');
                option.value = city;
                option.textContent = city;
                cityFilter.appendChild(option);
            }
        });
        
        // Log cities for debugging
        console.log('Available cities:', cities);
    } catch (error) {
        console.error('Error populating city filter:', error);
        showNotification('Error loading cities', 'error');
    }
}

// Initialize charts
function initializeCharts() {
    const isDarkMode = document.documentElement.classList.contains('dark');
    const textColor = isDarkMode ? '#ffffff' : '#000000';

    // Issue Type Chart
    const issueTypeCtx = document.getElementById('issueTypeChart').getContext('2d');
    issueTypeChart = new Chart(issueTypeCtx, {
        type: 'pie',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: []  // Will be populated dynamically
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: textColor,
                        padding: 20,
                        boxWidth: 20,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const value = context.raw;
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${context.label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });

    // Status Chart
    const statusCtx = document.getElementById('statusChart').getContext('2d');
    statusChart = new Chart(statusCtx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#ff4444', // pending
                    '#ffbb33', // in_progress
                    '#00C851', // fixed
                    '#33b5e5'  // false_positive
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: textColor,
                        padding: 20,
                        boxWidth: 20,
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    borderWidth: 1
                }
            }
        }
    });

    // Monthly Trend Chart
    const monthlyTrendCtx = document.getElementById('monthlyTrendChart').getContext('2d');
    monthlyTrendChart = new Chart(monthlyTrendCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Issues',
                data: [],
                borderColor: isDarkMode ? '#4B6EAF' : '#4B6EAF',
                backgroundColor: isDarkMode ? 'rgba(75, 110, 175, 0.2)' : 'rgba(75, 110, 175, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        color: textColor
                    },
                    grid: {
                        color: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
                    }
                },
                x: {
                    ticks: {
                        maxRotation: 45,
                        minRotation: 45,
                        color: textColor
                    },
                    grid: {
                        color: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
                    }
                }
            }
        }
    });
}

// Update filters and refresh data
function updateFilters() {
    currentFilters = {
        dateRange: document.getElementById('dateRangeFilter').value,
        issueType: document.getElementById('issueTypeFilter').value,
        status: document.getElementById('statusFilter').value,
        city: document.getElementById('cityFilter').value
    };
    fetchAndDisplayStats();
}

// Fetch and display statistics
async function fetchAndDisplayStats() {
    try {
        const url = new URL(`${window.location.origin}/api/stats`);
        Object.entries(currentFilters).forEach(([key, value]) => {
            if (value !== 'all') {
                url.searchParams.set(key, value);
            }
        });

        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        if (!data) throw new Error('No data received from /api/stats');

        updateSummaryCards(data);
        updateCharts(data);
        updateProblemAreas(data);
    } catch (error) {
        console.error('Error fetching statistics:', error);
        showNotification('Error loading statistics', 'error');
    }
}

// Update summary cards
function updateSummaryCards(data) {
    document.getElementById('totalIssues').textContent = data.total_issues;
    document.getElementById('issuesToday').textContent = data.issues_today;
    document.getElementById('dailyAverage').textContent = data.daily_average.toFixed(1);
    document.getElementById('lastUpdated').textContent = new Date(data.last_updated).toLocaleTimeString();
}

// Update charts
function updateCharts(data) {
    const isDarkMode = document.documentElement.classList.contains('dark');
    const textColor = isDarkMode ? '#ffffff' : '#000000';

    // Define color mapping for issue types
    const issueTypeColors = {
        'Potholes': '#FF4444',  // Red
        'Alligator Cracks': '#FFBB33',  // Orange-Yellow
        'Longitudinal Cracks': '#FFEB3B',  // Yellow
        'Transverse Cracks': '#FF9800',  // Dark Orange
        'Manhole Covers': '#9E9E9E',  // Grey
        'Patchy Road Sections': '#4CAF50'  // Green
    };

    // Update Issue Type Chart
    const issueTypes = Object.keys(data.issue_types);
    issueTypeChart.data.labels = issueTypes;
    issueTypeChart.data.datasets[0].data = Object.values(data.issue_types);
    issueTypeChart.data.datasets[0].backgroundColor = issueTypes.map(type => issueTypeColors[type] || '#6c757d');
    issueTypeChart.options.plugins.legend.labels.color = textColor;
    issueTypeChart.options.plugins.tooltip.backgroundColor = isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
    issueTypeChart.options.plugins.tooltip.titleColor = textColor;
    issueTypeChart.options.plugins.tooltip.bodyColor = textColor;
    issueTypeChart.options.plugins.tooltip.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    issueTypeChart.update();

    // Update Status Chart
    statusChart.data.labels = Object.keys(data.status_distribution);
    statusChart.data.datasets[0].data = Object.values(data.status_distribution);
    statusChart.options.plugins.legend.labels.color = textColor;
    statusChart.options.plugins.tooltip.backgroundColor = isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
    statusChart.options.plugins.tooltip.titleColor = textColor;
    statusChart.options.plugins.tooltip.bodyColor = textColor;
    statusChart.options.plugins.tooltip.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    statusChart.update();

    // Update Monthly Trend Chart
    monthlyTrendChart.data.labels = Object.keys(data.monthly_trend);
    monthlyTrendChart.data.datasets[0].data = Object.values(data.monthly_trend);
    monthlyTrendChart.options.scales.y.ticks.color = textColor;
    monthlyTrendChart.options.scales.x.ticks.color = textColor;
    monthlyTrendChart.options.scales.y.grid.color = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    monthlyTrendChart.options.scales.x.grid.color = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    monthlyTrendChart.options.plugins.tooltip.backgroundColor = isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
    monthlyTrendChart.options.plugins.tooltip.titleColor = textColor;
    monthlyTrendChart.options.plugins.tooltip.bodyColor = textColor;
    monthlyTrendChart.options.plugins.tooltip.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    monthlyTrendChart.update();
}

// Update problem areas table
function updateProblemAreas(data) {
    const tbody = document.getElementById('problemAreasTable');
    tbody.innerHTML = '';
    
    if (!data.top_areas || data.top_areas.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td colspan="3" class="px-2 py-1 text-center text-gray-500 dark:text-gray-400">
                No problem areas found
            </td>
        `;
        tbody.appendChild(row);
        return;
    }
    
    data.top_areas.forEach(area => {
        const [address, count, coordinates] = area;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-2 py-1 whitespace-nowrap text-gray-900 dark:text-gray-100">${address}</td>
            <td class="px-2 py-1 whitespace-nowrap text-gray-900 dark:text-gray-100">${count}</td>
            <td class="px-2 py-1 whitespace-nowrap">
                <button class="px-2 py-1 bg-primary hover:bg-primary-dark text-white rounded text-xs transition-all duration-200 flex items-center" onclick="viewOnMap('${coordinates}')">
                    <i class="fas fa-map-marker-alt mr-1"></i> View
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// Export statistics
function exportStats(format) {
    try {
        const url = new URL(`${window.location.origin}/api/export_stats`);
        url.searchParams.set('format', format);
        Object.entries(currentFilters).forEach(([key, value]) => {
            if (value !== 'all') {
                url.searchParams.set(key, value);
            }
        });

        // Create a temporary link and click it to trigger download
        const link = document.createElement('a');
        link.href = url.toString();
        link.target = '_blank';
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Show success notification
        showNotification(`Exporting data as ${format.toUpperCase()}...`, 'info');
    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Error exporting data', 'error');
    }
}

// View location on map
function viewOnMap(coordinates) {
    // Split coordinates and convert to numbers
    const [lat, lon] = coordinates.split(',').map(coord => parseFloat(coord.trim()));
    
    // Store coordinates in session storage
    sessionStorage.setItem('selectedLocation', JSON.stringify({
        lat: lat,
        lng: lon,
        zoom: 15
    }));
    
    // Redirect to map page
    window.location.href = '/map';
}

// Show notification
function showNotification(message, type = 'success') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-2 rounded-lg shadow-lg transition-all duration-300 ${
        type === 'success' ? 'bg-green-500' : 
        type === 'error' ? 'bg-red-500' : 
        type === 'info' ? 'bg-blue-500' : 'bg-gray-500'
    } text-white`;
    
    // Add message
    notification.textContent = message;
    
    // Add to document
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Update charts theme
function updateChartsTheme() {
    const isDarkMode = document.documentElement.classList.contains('dark');
    const textColor = isDarkMode ? '#ffffff' : '#000000';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const tooltipBg = isDarkMode ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)';
    const tooltipBorder = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    // Update Issue Type Chart
    if (issueTypeChart) {
        issueTypeChart.options.plugins.legend.labels.color = textColor;
        issueTypeChart.options.plugins.tooltip.backgroundColor = tooltipBg;
        issueTypeChart.options.plugins.tooltip.titleColor = textColor;
        issueTypeChart.options.plugins.tooltip.bodyColor = textColor;
        issueTypeChart.options.plugins.tooltip.borderColor = tooltipBorder;
        issueTypeChart.update();
    }

    // Update Status Chart
    if (statusChart) {
        statusChart.options.plugins.legend.labels.color = textColor;
        statusChart.options.plugins.tooltip.backgroundColor = tooltipBg;
        statusChart.options.plugins.tooltip.titleColor = textColor;
        statusChart.options.plugins.tooltip.bodyColor = textColor;
        statusChart.options.plugins.tooltip.borderColor = tooltipBorder;
        statusChart.update();
    }

    // Update Monthly Trend Chart
    if (monthlyTrendChart) {
        monthlyTrendChart.options.plugins.tooltip.backgroundColor = tooltipBg;
        monthlyTrendChart.options.plugins.tooltip.titleColor = textColor;
        monthlyTrendChart.options.plugins.tooltip.bodyColor = textColor;
        monthlyTrendChart.options.plugins.tooltip.borderColor = tooltipBorder;
        monthlyTrendChart.options.scales.y.ticks.color = textColor;
        monthlyTrendChart.options.scales.x.ticks.color = textColor;
        monthlyTrendChart.options.scales.y.grid.color = gridColor;
        monthlyTrendChart.options.scales.x.grid.color = gridColor;
        monthlyTrendChart.update();
    }
}

// Update stats (refresh button handler)
function updateStats() {
    fetchAndDisplayStats();
    showNotification('Refreshing statistics...', 'info');
} 