// Global variables
let currentPage = 1;
let totalPages = 1;
let perPage = 10;
let currentSortField = 'timestamp';
let currentSortOrder = 'desc';
let isLoading = false;
let selectedIssues = new Set();

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing dashboard...');
    
    // Initialize elements with null checks
    const statusFilter = document.getElementById('statusFilter');
    const issueTypeFilter = document.getElementById('issueTypeFilter');
    const cityFilter = document.getElementById('cityFilter');
    const itemsPerPage = document.getElementById('itemsPerPage');
    const issuesTable = document.getElementById('issuesTable');
    const pageInput = document.getElementById('pageInput');
    const pageInfo = document.getElementById('pageInfo');
    const firstPage = document.getElementById('firstPage');
    const prevPage = document.getElementById('prevPage');
    const nextPage = document.getElementById('nextPage');
    const lastPage = document.getElementById('lastPage');
    const issueTypesChart = document.getElementById('issueTypeChart');
    const statusChart = document.getElementById('statusChart');
    
    console.log('Found elements:', {
        statusFilter: !!statusFilter,
        issueTypeFilter: !!issueTypeFilter,
        cityFilter: !!cityFilter,
        itemsPerPage: !!itemsPerPage,
        issuesTable: !!issuesTable,
        pageInput: !!pageInput,
        pageInfo: !!pageInfo,
        firstPage: !!firstPage,
        prevPage: !!prevPage,
        nextPage: !!nextPage,
        lastPage: !!lastPage,
        issueTypesChart: !!issueTypesChart,
        statusChart: !!statusChart
    });
    
    // Only proceed if we have the minimum required elements
    if (!statusFilter || !issueTypeFilter || !cityFilter || !itemsPerPage || !issuesTable) {
        console.error('Required DOM elements not found');
        return;
    }

    // Add event listeners only if elements exist
    if (statusFilter) statusFilter.addEventListener('change', filterAndSearchRoadIssues);
    if (issueTypeFilter) issueTypeFilter.addEventListener('change', filterAndSearchRoadIssues);
    if (cityFilter) cityFilter.addEventListener('change', filterAndSearchRoadIssues);
    if (itemsPerPage) {
        itemsPerPage.addEventListener('change', function() {
            perPage = parseInt(this.value);
            currentPage = 1;
            fetchAndDisplayRoadIssues();
        });
    }

    // Add pagination event listeners if elements exist
    if (firstPage) firstPage.addEventListener('click', () => goToPage(1));
    if (prevPage) prevPage.addEventListener('click', () => goToPage(currentPage - 1));
    if (nextPage) nextPage.addEventListener('click', () => goToPage(currentPage + 1));
    if (lastPage) lastPage.addEventListener('click', () => goToPage(totalPages));
    if (pageInput) {
        pageInput.addEventListener('change', function() {
            const page = parseInt(this.value);
            if (page >= 1 && page <= totalPages) {
                goToPage(page);
            } else {
                this.value = currentPage;
            }
        });
    }

    // Fetch initial data
    console.log('Fetching initial data...');
    populateCityFilter();
    fetchAndDisplayRoadIssues();
    updateDashboardStats();

    // Add theme change observer
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.attributeName === 'class') {
                // Update charts when theme changes
                if (window.issueTypesChart) {
                    const isDarkMode = document.documentElement.classList.contains('dark');
                    const textColor = isDarkMode ? '#ffffff' : '#000000';
                    window.issueTypesChart.options.plugins.legend.labels.color = textColor;
                    window.issueTypesChart.update();
                }
                if (window.statusChart) {
                    const isDarkMode = document.documentElement.classList.contains('dark');
                    const textColor = isDarkMode ? '#ffffff' : '#000000';
                    window.statusChart.options.plugins.legend.labels.color = textColor;
                    window.statusChart.update();
                }
            }
        });
    });

    observer.observe(document.documentElement, {
        attributes: true
    });
});

// Add this new function to populate city filter
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
        
        console.log('Available cities:', cities);
    } catch (error) {
        console.error('Error populating city filter:', error);
        showNotification('Error loading cities', 'error');
    }
}

// Fetch and display road issues
async function fetchAndDisplayRoadIssues() {
    try {
        showLoading();
        const url = new URL('/api/road_issues', window.location.origin);
        url.searchParams.set('page', currentPage);
        url.searchParams.set('per_page', perPage);
        
        const statusFilter = document.getElementById('statusFilter').value;
        const typeFilter = document.getElementById('issueTypeFilter').value;
        const cityFilter = document.getElementById('cityFilter').value;

        if (statusFilter && statusFilter !== 'all') url.searchParams.set('status', statusFilter);
        if (typeFilter && typeFilter !== 'all') url.searchParams.set('type', typeFilter);
        if (cityFilter && cityFilter !== 'all') url.searchParams.set('city', cityFilter);

        console.log('Fetching data from:', url.toString());
        const response = await fetch(url);
        console.log('Response status:', response.status);
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        console.log('Received data:', data);
        
        if (!data || !data.issues) {
            console.error('Invalid data format received from server');
            throw new Error('Invalid data format received from server');
        }
        
        renderIssueTable(data.issues);
        updatePagination(data);
    } catch (error) {
        console.error('Error in fetchAndDisplayRoadIssues:', error);
        showNotification(`Error loading road issues: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

// Update city filter options
function updateCityFilter(issues) {
    const cityFilter = document.getElementById('cityFilter');
    if (!cityFilter) return;

    // Get unique cities from issues
    const cities = new Set();
    issues.forEach(issue => {
        if (issue.city) {
            cities.add(issue.city);
        }
    });

    // Sort cities alphabetically
    const sortedCities = Array.from(cities).sort();

    // Update city filter options
    cityFilter.innerHTML = '<option value="">All Cities</option>';
    sortedCities.forEach(city => {
        const option = document.createElement('option');
        option.value = city;
        option.textContent = city;
        cityFilter.appendChild(option);
    });
}

// Update dashboard statistics
async function updateDashboardStats() {
    try {
        console.log('Fetching dashboard stats...');
        const response = await fetch('/api/dashboard_stats', {
            method: 'GET',
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        console.log('Received dashboard stats:', data);
        
        if (!data) throw new Error('No data received from /api/dashboard_stats');

        // Update summary cards
        const totalIssuesElement = document.getElementById('totalIssues');
        const issuesTodayElement = document.getElementById('issuesToday');
        const mostCommonIssueElement = document.getElementById('mostCommonIssue');
        
        if (totalIssuesElement) totalIssuesElement.textContent = data.total_issues;
        if (issuesTodayElement) issuesTodayElement.textContent = data.issues_today;
        if (mostCommonIssueElement) mostCommonIssueElement.textContent = data.most_common_issue;

        // Update charts
        console.log('Updating issue types chart with data:', data.issue_types);
        updateIssueTypesChart(data.issue_types);
        
        console.log('Updating status chart with data:', data.status_distribution);
        updateStatusChart(data.status_distribution);
    } catch (error) {
        console.error('Error updating dashboard stats:', error);
        showNotification('Error updating dashboard stats', 'error');
    }
}

// Update issue types chart
function updateIssueTypesChart(data) {
    console.log('Starting updateIssueTypesChart with data:', data);
    const canvas = document.getElementById('issueTypeChart');
    console.log('Chart canvas found:', !!canvas);
    
    if (!canvas) {
        console.error('Issue types chart canvas not found');
        return;
    }
    
    const ctx = canvas.getContext('2d');
    console.log('2D context obtained:', !!ctx);
    
    if (!ctx) {
        console.error('Could not get 2D context for issue types chart');
        return;
    }
    
    if (window.issueTypesChart instanceof Chart) {
        console.log('Destroying existing chart');
        window.issueTypesChart.destroy();
    }

    // Define colors for different issue types
    const issueTypeColors = {
        'Alligator Cracks': '#FFA500',  // Orange-Yellow
        'Longitudinal Cracks': '#FFFF00',  // Yellow
        'Manhole Covers': '#808080',  // Grey
        'Patchy Road Sections': '#00FF00',  // Green
        'Potholes': '#FF0000',  // Red
        'Transverse Cracks': '#FF8C00'  // Dark Orange
    };

    // Check if dark mode is enabled
    const isDarkMode = document.documentElement.classList.contains('dark');
    const textColor = isDarkMode ? '#ffffff' : '#000000';

    window.issueTypesChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: Object.keys(data),
            datasets: [{
                data: Object.values(data),
                backgroundColor: Object.keys(data).map(type => issueTypeColors[type] || '#6c757d'),
                borderWidth: 1,
                borderColor: '#343a40'
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
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
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
    console.log('Chart created successfully');
}

// Update status chart
function updateStatusChart(data) {
    console.log('Updating status chart with data:', data);
    const canvas = document.getElementById('statusChart');
    if (!canvas) {
        console.error('Status chart canvas not found');
        return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) {
        console.error('Could not get 2D context for status chart');
        return;
    }

    // Destroy existing chart if it exists
    if (window.statusChart instanceof Chart) {
        window.statusChart.destroy();
    }

    const statusColors = {
        'pending': '#ffc107',      // Yellow
        'in_progress': '#0dcaf0',  // Blue
        'fixed': '#198754',        // Green
        'false_positive': '#dc3545' // Red
    };

    const labels = Object.keys(data).map(status => 
        status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())
    );
    const values = Object.values(data);
    const backgroundColors = Object.keys(data).map(status => statusColors[status] || '#6c757d');

    // Check if dark mode is enabled
    const isDarkMode = document.documentElement.classList.contains('dark');
    const textColor = isDarkMode ? '#ffffff' : '#000000';

    window.statusChart = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: backgroundColors,
                borderWidth: 1,
                borderColor: '#343a40'
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
                        font: {
                            size: 12
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
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
    console.log('Status chart updated successfully');
}

// Render issue table
function renderIssueTable(issues) {
    const tbody = document.querySelector('#issuesTable tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    issues.forEach(issue => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 dark:hover:bg-gray-700';
        
        // Checkbox
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <input type="checkbox" class="issue-checkbox rounded text-primary focus:ring-primary" 
                       value="${issue.id}" onchange="handleCheckboxChange(this)">
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">${issue.id}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="w-16 h-16 rounded-lg overflow-hidden cursor-pointer" onclick="showIssueDetails(${issue.id})">
                    <img src="/road_issue/image/${issue.id}" 
                         alt="Issue ${issue.id}" 
                         class="w-full h-full object-cover"
                         onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=\'http://www.w3.org/2000/svg\' width=\'100\' height=\'100\'><rect width=\'100%\' height=\'100%\' fill=\'%23ccc\'/><text x=\'50%\' y=\'50%\' dominant-baseline=\'middle\' text-anchor=\'middle\' fill=\'%23666\'>No Image</text></svg>'">
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getIssueTypeBadgeClass(issue.type)}">
                    <span class="w-2 h-2 rounded-full mr-2" style="background-color: ${getIssueTypeColor(issue.type)}"></span>
                    ${issue.type}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
                ${new Date(issue.timestamp).toLocaleString()}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
                ${issue.address || `${issue.latitude.toFixed(6)}, ${issue.longitude.toFixed(6)}`}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
                ${(issue.confidence * 100).toFixed(1)}%
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusBadgeClass(issue.status)}">
                    <span class="w-2 h-2 rounded-full mr-2" style="background-color: ${getStatusColor(issue.status)}"></span>
                    ${issue.status}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-200">
                <div class="flex items-center gap-2">
                    <button onclick="showIssueDetails(${issue.id})" 
                            class="w-8 h-8 flex items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 hover:bg-primary hover:text-white dark:text-gray-400 dark:hover:bg-primary dark:hover:text-white transition-all duration-200 shadow-sm hover:shadow-md">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button onclick="viewOnMap(${issue.id})"
                            class="w-8 h-8 flex items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 hover:bg-secondary hover:text-white dark:text-gray-400 dark:hover:bg-secondary dark:hover:text-white transition-all duration-200 shadow-sm hover:shadow-md">
                        <i class="fas fa-map-marker-alt"></i>
                    </button>
                    <button onclick="deleteIssue(${issue.id})"
                            class="w-8 h-8 flex items-center justify-center rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 hover:bg-danger hover:text-white dark:text-gray-400 dark:hover:bg-danger dark:hover:text-white transition-all duration-200 shadow-sm hover:shadow-md">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

// Selection functions
function toggleSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.issue-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll.checked;
        const issueId = parseInt(checkbox.value);
        if (selectAll.checked) {
            selectedIssues.add(issueId);
        } else {
            selectedIssues.delete(issueId);
        }
    });
    
    updateBulkActions();
    updateSelectedCount();
}

function handleCheckboxChange(checkbox) {
    const issueId = parseInt(checkbox.value);
    if (checkbox.checked) {
        selectedIssues.add(issueId);
    } else {
        selectedIssues.delete(issueId);
    }
    
    // Update select all checkbox state
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.issue-checkbox');
    selectAll.checked = selectedIssues.size === checkboxes.length;
    
    updateBulkActions();
    updateSelectedCount();
}

function updateSelectedCount() {
    const count = selectedIssues.size;
    const selectedCount = document.getElementById('selectedCount');
    if (selectedCount) {
        selectedCount.textContent = `${count} items selected`;
    }
    
    const bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
    const bulkUpdateBtn = document.getElementById('bulkUpdateBtn');
    if (bulkDeleteBtn) bulkDeleteBtn.disabled = count === 0;
    if (bulkUpdateBtn) bulkUpdateBtn.disabled = count === 0;
}

function updateBulkActions() {
    const bulkActionsDropdown = document.getElementById('bulkActionsDropdown');
    if (bulkActionsDropdown) {
        bulkActionsDropdown.disabled = selectedIssues.size === 0;
    }
}

// Update pagination UI
function updatePagination(data) {
    const pageInfo = document.getElementById('pageInfo');
    const firstPage = document.getElementById('firstPage');
    const prevPage = document.getElementById('prevPage');
    const nextPage = document.getElementById('nextPage');
    const lastPage = document.getElementById('lastPage');
    const pageInput = document.getElementById('pageInput');

    if (!pageInfo || !firstPage || !prevPage || !nextPage || !lastPage || !pageInput) {
        console.error('Pagination elements not found');
        return;
    }

    totalPages = Math.ceil(data.total / perPage);
    currentPage = Math.min(currentPage, totalPages);
    currentPage = Math.max(currentPage, 1);

    // Update page info
    pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    pageInput.value = currentPage;
    pageInput.max = totalPages;

    // Update button states
    firstPage.disabled = currentPage === 1;
    prevPage.disabled = currentPage === 1;
    nextPage.disabled = currentPage === totalPages;
    lastPage.disabled = currentPage === totalPages;
}

// Go to specific page
function goToPage(page) {
    if (page < 1 || page > totalPages) return;
    currentPage = page;
    fetchAndDisplayRoadIssues();
}

// Helper functions
function showLoading() {
    isLoading = true;
    const issuesTable = document.getElementById('issuesTable');
    const pageInput = document.getElementById('pageInput');
    const pageLinks = document.querySelectorAll('.page-link');
    
    if (issuesTable) issuesTable.classList.add('opacity-50');
    if (pageInput) pageInput.disabled = true;
    if (pageLinks) {
        pageLinks.forEach(btn => {
            if (btn) btn.disabled = true;
        });
    }
}

function hideLoading() {
    isLoading = false;
    const issuesTable = document.getElementById('issuesTable');
    const pageInput = document.getElementById('pageInput');
    const pageLinks = document.querySelectorAll('.page-link');
    
    if (issuesTable) issuesTable.classList.remove('opacity-50');
    if (pageInput) pageInput.disabled = false;
    if (pageLinks) {
        pageLinks.forEach(btn => {
            if (btn) btn.disabled = false;
        });
    }
}

function getStatusBadgeClass(status) {
    const classes = {
        'New': 'bg-red-100 text-red-800',
        'In Progress': 'bg-yellow-100 text-yellow-800',
        'Done': 'bg-green-100 text-green-800'
    };
    return classes[status] || 'bg-gray-100 text-gray-800';
}

function showNotification(message, type = 'success') {
    // Implementation for showing notifications
    // You can use a toast library or implement your own notification system
    console.log(`${type}: ${message}`);
}

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

// Action functions
async function viewIssue(id) {
    try {
        const response = await fetch(`/road_issue/${id}/view`);
        const data = await response.json();
        
        // Show modal with issue details
        // Implementation depends on your modal library
        console.log('View issue:', data);
    } catch (error) {
        showNotification('Error viewing issue', 'error');
    }
}

async function editIssue(id) {
    try {
        const response = await fetch(`/road_issue/${id}/edit`);
        const data = await response.json();
        
        // Show edit form
        // Implementation depends on your form handling
        console.log('Edit issue:', data);
    } catch (error) {
        showNotification('Error editing issue', 'error');
    }
}

async function deleteIssue(id) {
    if (!confirm('Are you sure you want to delete this issue?')) return;
    
    try {
        const response = await fetch(`/road_issue/${id}/delete`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('Issue deleted successfully');
            // Refresh the table and dashboard stats
            await fetchAndDisplayRoadIssues();
            await updateDashboardStats();
        } else {
            throw new Error('Failed to delete issue');
        }
    } catch (error) {
        showNotification('Error deleting issue', 'error');
    }
}

async function bulkDelete() {
    if (selectedIssues.size === 0) return;
    if (!confirm(`Are you sure you want to delete ${selectedIssues.size} issues?`)) return;
    
    try {
        const response = await fetch('/api/bulk_delete_issues', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ issue_ids: Array.from(selectedIssues) })
        });
        
        if (response.ok) {
            showNotification(`${selectedIssues.size} issues deleted successfully`);
            selectedIssues.clear();
            fetchAndDisplayRoadIssues();
            updateDashboardStats();
        } else {
            throw new Error('Failed to delete issues');
        }
    } catch (error) {
        showNotification('Error deleting issues', 'error');
    }
}

async function bulkUpdateStatus(status) {
    if (selectedIssues.size === 0) {
        showNotification('Please select at least one issue', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/bulk_update_status', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                issue_ids: Array.from(selectedIssues),
                status: status
            })
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        showNotification(data.message, 'success');
        
        // Refresh the table and dashboard stats
        await fetchAndDisplayRoadIssues();
        await updateDashboardStats();
        
        // Clear selection
        selectedIssues.clear();
        document.getElementById('selectAll').checked = false;
        document.querySelectorAll('.issue-checkbox').forEach(checkbox => {
            checkbox.checked = false;
        });
    } catch (error) {
        console.error('Error in bulk update:', error);
        showNotification('Error updating issues', 'error');
    }
}

// Filter and search function
function filterAndSearchRoadIssues() {
    currentPage = 1;
    fetchAndDisplayRoadIssues();
}

// Export function
async function exportToCSV() {
    try {
        // Get current filter values
        const statusFilter = document.getElementById('statusFilter').value;
        const typeFilter = document.getElementById('issueTypeFilter').value;
        const cityFilter = document.getElementById('cityFilter').value;

        // Build URL with filters
        const exportUrl = new URL('/export_to_csv', window.location.origin);
        if (statusFilter !== 'all') exportUrl.searchParams.set('status', statusFilter);
        if (typeFilter !== 'all') exportUrl.searchParams.set('issueType', typeFilter);
        if (cityFilter !== 'all') exportUrl.searchParams.set('city', cityFilter);

        console.log('Exporting data with URL:', exportUrl.toString());
        const response = await fetch(exportUrl);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = 'road_issues.csv';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);
    } catch (error) {
        console.error('Error exporting data:', error);
        showNotification('Error exporting data', 'error');
    }
}

// Show issue details in modal
async function showIssueDetails(issueId) {
    try {
        const response = await fetch(`/road_issue/${issueId}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const issue = await response.json();
        
        // Update modal content
        document.getElementById('modalIssueImage').src = `/road_issue/image/${issueId}`;
        document.getElementById('modalIssueType').textContent = issue.type;
        document.getElementById('modalIssueStatus').textContent = issue.status;
        document.getElementById('modalIssueConfidence').textContent = `${(issue.confidence * 100).toFixed(1)}%`;
        document.getElementById('modalIssueTimestamp').textContent = new Date(issue.timestamp).toLocaleString();
        document.getElementById('modalIssueLocation').textContent = issue.address || 'Location not available';
        document.getElementById('modalIssueNotes').value = issue.notes || '';
        
        // Store current issue ID for saving changes
        document.getElementById('issueDetailsModal').dataset.issueId = issueId;
        
        // Show modal
        document.getElementById('issueDetailsModal').classList.remove('hidden');
    } catch (error) {
        console.error('Error fetching issue details:', error);
        showNotification('Error loading issue details', 'error');
    }
}

// Save changes to issue
async function saveIssueChanges() {
    const issueId = document.getElementById('issueDetailsModal').dataset.issueId;
    const notes = document.getElementById('modalIssueNotes').value;
    
    try {
        const response = await fetch(`/road_issue/${issueId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                notes: notes
            })
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        showNotification('Changes saved successfully', 'success');
        closeIssueDetails();
        fetchAndDisplayRoadIssues(); // Refresh the table
    } catch (error) {
        console.error('Error saving changes:', error);
        showNotification('Error saving changes', 'error');
    }
}

// Close issue details modal
function closeIssueDetails() {
    document.getElementById('issueDetailsModal').classList.add('hidden');
}

// View issue on map
function viewOnMap(issueId) {
    window.location.href = `/map?issue_id=${issueId}`;
}

function getIssueTypeBadgeClass(type) {
    const classes = {
        'Potholes': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
        'Alligator Cracks': 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
        'Longitudinal Cracks': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
        'Transverse Cracks': 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
        'Manhole Covers': 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
        'Patchy Road Sections': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    };
    return classes[type] || 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
}

function getIssueTypeColor(type) {
    const colors = {
        'Potholes': '#dc3545',        // Red
        'Alligator Cracks': '#fd7e14', // Orange
        'Longitudinal Cracks': '#ffc107', // Yellow
        'Transverse Cracks': '#ffa500', // Amber
        'Manhole Covers': '#6c757d',   // Gray
        'Patchy Road Sections': '#198754' // Green
    };
    return colors[type] || '#6c757d';
}

function getStatusColor(status) {
    const colors = {
        'pending': '#ffc107',      // Yellow
        'in_progress': '#0dcaf0',  // Blue
        'fixed': '#198754',        // Green
        'false_positive': '#dc3545' // Red
    };
    return colors[status] || '#6c757d';
}

// Update individual issue status
async function updateIssueStatus(newStatus) {
    const issueId = document.getElementById('issueDetailsModal').dataset.issueId;
    if (!issueId) return;

    try {
        const response = await fetch(`/road_issue/${issueId}/update`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: newStatus
            })
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        showNotification('Status updated successfully', 'success');

        // Update the status display in the modal
        document.getElementById('modalIssueStatus').textContent = newStatus.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
        
        // Refresh the table and dashboard stats
        await fetchAndDisplayRoadIssues();
        await updateDashboardStats();
    } catch (error) {
        console.error('Error updating issue status:', error);
        showNotification('Error updating status', 'error');
    }
} 