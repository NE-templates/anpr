// Enhanced Dashboard JavaScript - Save as static/dashboard.js

$(document).ready(function () {
    // Initialize dashboard
    initializeDashboard();
    
    // Update current time
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    
    // Fetch initial data
    fetchAllData();
    
    // Set up periodic updates every 30 seconds (reduced frequency for better performance)
    setInterval(() => {
        fetchRevenue();
        fetchRecentActivity();
        fetchSystemAlerts();
        fetchAdditionalStats();
    }, 30000);
    
    // Update stats every 5 minutes
    setInterval(() => {
        fetchStats();
    }, 300000);
    
    // Chart period controls
    $('.chart-controls .btn').on('click', function() {
        $('.chart-controls .btn').removeClass('active');
        $(this).addClass('active');
        const period = $(this).data('period');
        fetchStats(period);
    });
});

function initializeDashboard() {
    // Add loading states
    $('#revenue, #activeVehicles, #occupancyRate, #activeAlerts').html('<span class="loading"></span>');
    
    // Initialize placeholder activity
    loadPlaceholderActivity();
    loadPlaceholderAlerts();
}

function updateCurrentTime() {
    const now = new Date();
    const timeString = now.toLocaleString('en-US', {
        weekday: 'short',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    $('#currentTime').text(timeString);
}

function fetchAllData() {
    fetchRevenue();
    fetchStats();
    fetchRecentActivity();
    fetchSystemAlerts();
    fetchAdditionalStats();
}

function fetchRevenue() {
    $.getJSON('/api/revenue')
        .done(function (data) {
            $('#revenue').text('RWF ' + formatNumber(data.total_revenue || 0));
        })
        .fail(function(xhr, status, error) {
            console.error('Error fetching revenue:', error);
            $('#revenue').text('RWF 0');
        });
}

function fetchAdditionalStats() {
    // Fetch active vehicles count
    $.getJSON('/api/active-vehicles')
        .done(function(data) {
            $('#activeVehicles').text(data.count || 0);
        })
        .fail(function() {
            // Calculate from recent sessions if API not available
            $.getJSON('/api/recent-sessions')
                .done(function(sessions) {
                    const activeCount = sessions.filter(s => s.payment_status === 0).length;
                    $('#activeVehicles').text(activeCount);
                })
                .fail(function() {
                    $('#activeVehicles').text('0');
                });
        });
    
    // Fetch occupancy rate
    $.getJSON('/api/occupancy-rate')
        .done(function(data) {
            $('#occupancyRate').text(data.rate + '%');
        })
        .fail(function() {
            // Calculate basic occupancy if API not available
            $('#occupancyRate').text('--');
        });
    
    // Fetch active alerts count
    $.getJSON('/api/active-alerts')
        .done(function(data) {
            $('#activeAlerts').text(data.count || 0);
        })
        .fail(function() {
            $('#activeAlerts').text('0');
        });
}

function fetchStats(period = '7d') {
    $.getJSON('/api/daily-stats', { period: period })
        .done(function (data) {
            if (data && data.length > 0) {
                updateMainChart(data);
                updateRevenueChart(data);
            } else {
                console.warn('No stats data received');
                // Show empty state
                updateMainChart([]);
                updateRevenueChart([]);
            }
        })
        .fail(function(xhr, status, error) {
            console.error('Error fetching stats:', error);
            // Show error state
            updateMainChart([]);
            updateRevenueChart([]);
        });
}

function updateMainChart(data) {
    const ctx = document.getElementById('statsChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (window.statsChart instanceof Chart) {
        window.statsChart.destroy();
    }
    
    if (!data || data.length === 0) {
        // Show empty state
        ctx.fillStyle = '#666';
        ctx.textAlign = 'center';
        ctx.font = '16px sans-serif';
        ctx.fillText('No data available', ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    const labels = data.map(d => formatDate(d.date || d.timestamp));
    const vehicles = data.map(d => d.total_vehicles || 0);
    const revenue = data.map(d => parseFloat(d.revenue || d.amount || 0));
    const sessions = data.map(d => d.total_sessions || 0);

    window.statsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Vehicles',
                    data: vehicles,
                    borderColor: '#26c6da',
                    backgroundColor: 'rgba(38, 198, 218, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#26c6da',
                    pointBorderWidth: 2,
                    pointRadius: 4
                },
                {
                    label: 'Revenue (RWF)',
                    data: revenue,
                    borderColor: '#56cc9d',
                    backgroundColor: 'rgba(86, 204, 157, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#56cc9d',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    yAxisID: 'y1'
                },
                {
                    label: 'Sessions',
                    data: sessions,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#667eea',
                    pointBorderWidth: 2,
                    pointRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    titleColor: '#333',
                    bodyColor: '#666',
                    borderColor: '#ddd',
                    borderWidth: 1,
                    cornerRadius: 8,
                    displayColors: true
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#666'
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        color: '#666'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    beginAtZero: true,
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: '#666',
                        callback: function(value) {
                            return 'RWF ' + formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

function updateRevenueChart(data) {
    const ctx = document.getElementById('revenueChart').getContext('2d');
    
    if (window.revenueChart instanceof Chart) {
        window.revenueChart.destroy();
    }
    
    // Fetch revenue breakdown from API
    $.getJSON('/api/revenue-breakdown')
        .done(function(breakdown) {
            const labels = Object.keys(breakdown);
            const values = Object.values(breakdown);
            const colors = ['#667eea', '#56cc9d', '#ff8a65', '#ff5252', '#26c6da'];
            
            window.revenueChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors.slice(0, labels.length),
                        borderWidth: 0,
                        hoverOffset: 10
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 15,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = Math.round((context.parsed / total) * 100);
                                    return context.label + ': RWF ' + formatNumber(context.parsed) + ' (' + percentage + '%)';
                                }
                            }
                        }
                    },
                    cutout: '60%'
                }
            });
        })
        .fail(function() {
            // Fallback to basic chart if breakdown API fails
            const fallbackData = {
                labels: ['Parking Revenue'],
                data: [100],
                colors: ['#56cc9d']
            };
            
            window.revenueChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: fallbackData.labels,
                    datasets: [{
                        data: fallbackData.data,
                        backgroundColor: fallbackData.colors,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom'
                        }
                    },
                    cutout: '60%'
                }
            });
        });
}

function fetchRecentActivity() {
    $.getJSON('/api/recent-activity')
        .done(function(activities) {
            updateActivityList(activities);
        })
        .fail(function() {
            // Fallback to recent sessions
            $.getJSON('/api/recent-sessions?limit=5')
                .done(function(sessions) {
                    const activities = sessions.map(session => ({
                        type: session.payment_status === 1 ? 'payment' : 'entry',
                        title: session.payment_status === 1 
                            ? `Payment received from ${session.plate_number} - RWF ${formatNumber(session.amount)}`
                            : `Vehicle ${session.plate_number} entered at ${session.gate}`,
                        time: formatTimeAgo(session.timestamp),
                        icon: session.payment_status === 1 ? 'fa-credit-card' : 'fa-car'
                    }));
                    updateActivityList(activities);
                })
                .fail(function() {
                    updateActivityList([{
                        type: 'info',
                        title: 'No recent activity',
                        time: '',
                        icon: 'fa-info-circle'
                    }]);
                });
        });
}

function fetchSystemAlerts() {
    $.getJSON('/api/system-alerts')
        .done(function(alerts) {
            updateAlertsList(alerts);
        })
        .fail(function() {
            // Check for low balance cards or other issues
            $.getJSON('/api/low-balance-alerts')
                .done(function(lowBalanceAlerts) {
                    const alerts = lowBalanceAlerts.map(alert => ({
                        type: 'warning',
                        title: `Low balance: ${alert.plate_number} (RWF ${alert.balance})`,
                        time: formatTimeAgo(alert.last_seen),
                        severity: 'medium'
                    }));
                    updateAlertsList(alerts);
                })
                .fail(function() {
                    updateAlertsList([{
                        type: 'info',
                        title: 'No active alerts',
                        time: ''
                    }]);
                });
        });
}

function updateActivityList(activities) {
    const container = $('#recentActivity');
    container.empty();
    
    if (!activities || activities.length === 0) {
        container.append('<div class="no-data">No recent activity</div>');
        return;
    }
    
    activities.forEach(activity => {
        const item = $(`
            <div class="activity-item">
                <div class="activity-icon">
                    <i class="fas ${activity.icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-title">${activity.title}</div>
                    <div class="activity-time">${activity.time}</div>
                </div>
            </div>
        `);
        container.append(item);
    });
}

function updateAlertsList(alerts) {
    const container = $('#systemAlerts');
    container.empty();
    
    if (!alerts || alerts.length === 0) {
        container.append('<div class="no-data">No active alerts</div>');
        return;
    }
    
    alerts.forEach(alert => {
        const severityClass = alert.severity === 'high' ? 'alert-high' : 
                            alert.severity === 'medium' ? 'alert-medium' : 'alert-low';
        
        const item = $(`
            <div class="alert-item ${severityClass}">
                <div class="alert-icon">
                    <i class="fas fa-bell"></i>
                </div>
                <div class="alert-content">
                    <div class="alert-title">${alert.title}</div>
                    <div class="alert-time">${alert.time}</div>
                </div>
            </div>
        `);
        container.append(item);
    });
}

function loadPlaceholderActivity() {
    const container = $('#recentActivity');
    container.html('<div class="loading-state">Loading recent activities...</div>');
}

function loadPlaceholderAlerts() {
    const container = $('#systemAlerts');
    container.html('<div class="loading-state">Loading system alerts...</div>');
}

// Utility functions
function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatTimeAgo(timestamp) {
    const now = new Date();
    const date = new Date(timestamp);
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}