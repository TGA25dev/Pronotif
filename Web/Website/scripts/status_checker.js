document.addEventListener('DOMContentLoaded', function() {
    // Load the Statuspage script
    const script = document.createElement('script');
    script.src = 'https://cdn.statuspage.io/se-v2.js';
    document.head.appendChild(script);
    
    script.onload = function() {
        // Initialize it
        const sp = new StatusPage.page({ page: 'x5xv7gdnw25h' });
        
        // Get status summary
        sp.summary({
            success: function(data) {
                handleStatusData(data);
            }
        });
        
        // Set up periodic checks
        setInterval(function() {
            sp.summary({
                success: function(data) {
                    handleStatusData(data);
                }
            });
        }, 5 * 60 * 1000); // Check every 5 minutes
    };
    
    // Status elements
    const statusNotification = document.getElementById('statusNotification');
    const statusMessage = document.getElementById('statusMessage');
    const statusIcon = document.getElementById('statusIcon');
    const closeStatus = document.getElementById('closeStatus');
    
    // Close button
    closeStatus.addEventListener('click', function() {
        statusNotification.style.display = 'none';
        // Store in localStorage to prevent re-showing
        const currentIncidentId = statusNotification.dataset.incidentId;
        if (currentIncidentId) {
            localStorage.setItem(`dismissed_${currentIncidentId}`, 'true');
        }
    });
    
    function handleStatusData(data) {
        try {
            // Check for active incidents
            const incidents = data.incidents.filter(incident => 
                incident.status !== 'resolved' && incident.status !== 'completed');
                
            // Check for scheduled maintenances
            const maintenances = data.scheduled_maintenances.filter(maintenance => 
                maintenance.status !== 'completed');
            
            // Check for components with issues
            const componentsWithIssues = data.components.filter(component => 
                component.status !== 'operational');
            
            if (incidents.length > 0) {
                // Show most recent incident
                const latestIncident = incidents[0];
                if (localStorage.getItem(`dismissed_${latestIncident.id}`) !== 'true') {
                    showNotification(latestIncident, 'incident');
                }
            } else if (maintenances.length > 0) {
                // Show upcoming maintenance
                const nextMaintenance = maintenances[0];
                if (localStorage.getItem(`dismissed_${nextMaintenance.id}`) !== 'true') {
                    showNotification(nextMaintenance, 'maintenance');
                }
            } else if (componentsWithIssues.length > 0) {
                // Show component issues when there's no active incident
                showComponentIssues(componentsWithIssues);
            } else {
                // All clear, hide notification
                statusNotification.style.display = 'none';
            }
        } catch (error) {
            console.error('Error handling status data:', error);
        }
    }
    
    function showNotification(event, type) {

        statusNotification.classList.remove('incident', 'maintenance-planned', 'maintenance-ongoing');
        
        // Determine event type and styling
        let typeLabel, icon, typeClass;
        
        if (type === 'incident') {
            typeLabel = 'Incident en cours';
            icon = '🔴';
            typeClass = 'incident';
        } else {
            
            if (event.status === 'in_progress' || event.status === 'verifying') {
                typeLabel = 'Maintenance en cours';
                icon = '🔧';
                typeClass = 'maintenance-ongoing';
            } else {
                typeLabel = 'Maintenance Planifiée';
                icon = '📅';
                typeClass = 'maintenance-planned';
            }
        }
        
        statusNotification.classList.add(typeClass);
        
        // Get description and truncate if needed
        let description = event.incident_updates && event.incident_updates.length > 0 
            ? event.incident_updates[0].body 
            : '';
        
        if (description.length > 120) {
            description = description.substring(0, 117) + '...';
        }
        
        // Get and format the timestamp
        let timestamp;
        let timeDisplay = '';
        
        if (type === 'incident' || typeClass === 'maintenance-ongoing') {
            // For incidents and ongoing maintenance, show when it started/was updated
            if (event.incident_updates && event.incident_updates.length > 0) {
                timestamp = new Date(event.incident_updates[0].created_at);
            } else {
                timestamp = new Date(event.updated_at);
            }
            timeDisplay = formatTimestamp(timestamp);
        } else if (typeClass === 'maintenance-planned') {
            // For planned maintenance, show when it is scheduled to start
            if (event.scheduled_for) {
                timestamp = new Date(event.scheduled_for);
                timeDisplay = formatScheduledTime(timestamp);
            }
        }
        
        // Update notification content
        statusIcon.textContent = icon;
        statusMessage.innerHTML = `
            <span class="status-type-label ${typeClass}">${typeLabel}</span>
            <div class="status-content-wrapper">
                <strong>${event.name}</strong>
                <p class="status-description">${description}</p>
                <div class="status-time">
                    <svg viewBox="0 0 24 24" width="12" height="12">
                        <path fill="currentColor" d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                        <path fill="currentColor" d="M12.5 7H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
                    </svg> 
                    ${timeDisplay}
                </div>
            </div>
        `;
        
        // Store the incident ID for dismissal functionality
        statusNotification.dataset.incidentId = event.id;
        
        // Animation
        statusNotification.style.display = 'flex';
        setTimeout(() => {
            statusNotification.classList.add('visible');
        }, 10);
    }

    // Helper function to format timestamp
    function formatTimestamp(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        // Format based on how recent
        if (diffMins < 1) {
            return 'Maintenant';
        } else if (diffMins < 60) {
            return `Il y a ${diffMins} minute${diffMins !== 1 ? 's' : ''}`;
        } else if (diffHours < 24) {
            return `Il y a ${diffHours} heure${diffHours !== 1 ? 's' : ''}`;
        } else if (diffDays < 7) {
            return `Il y a ${diffDays} jour${diffDays !== 1 ? 's' : ''}`;
        } else {
            // Format as date for older updates
            return date.toLocaleDateString(undefined, { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric' 
            });
        }
    }

    // Helper function to format timestamps for scheduled maintenance
    function formatScheduledTime(date) {
        const now = new Date();
        const diffMs = date - now;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);
        
        if (diffMs < 0) {
            return 'Commencée';
        } else if (diffMins < 60) {
            return `Commence dans ${diffMins} minute${diffMins !== 1 ? 's' : ''}`;
        } else if (diffHours < 24) {
            return `Commence dans ${diffHours} heure${diffHours !== 1 ? 's' : ''}`;
        } else if (diffDays < 7) {
            return `Commence dans ${diffDays} jour${diffDays !== 1 ? 's' : ''}`;
        } else {
            return `Prévue pour dans ${date.toLocaleDateString(undefined, { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            })}`;
        }
    }

    function showComponentIssues(components) {
        // Clear previous classes
        statusNotification.classList.remove('incident', 'maintenance-planned', 'maintenance-ongoing', 'component-issues');
        statusNotification.classList.add('component-issues');
        
        // Determine severity
        let severityClass = 'performance';
        let icon = '⚠️';
        
        // Check for the most severe status
        if (components.some(c => c.status === 'major_outage')) {
            severityClass = 'major-outage';
            icon = '❌';
        } else if (components.some(c => c.status === 'partial_outage')) {
            severityClass = 'partial-outage';
            icon = '⚠️';
        } else if (components.some(c => c.status === 'degraded_performance')) {
            severityClass = 'degraded';
            icon = '⚠️';
        }
        
        // Generate notification ID from component names
        const componentIds = components.map(c => c.id).join('-');
        const notificationId = `components-${componentIds}`;
        
        // Check if dismissed
        if (localStorage.getItem(`dismissed_${notificationId}`) === 'true') {
            return;
        }
        
        const statusLabels = {
            'degraded_performance': 'Performances dégradées',
            'partial_outage': 'Panne partielle',
            'major_outage': 'Panne majeure'
        };

        // Create component list
        let componentListHtml = '';
        components.forEach(component => {
            const status = statusLabels[component.status] || component.status;
            componentListHtml += `<div class="component-status ${component.status}">
                <strong>${component.name}</strong>: ${status}
            </div>`;
        });
        
        // Update notification content
        statusIcon.textContent = icon;
        statusMessage.innerHTML = `
            <span class="status-type-label component-${severityClass}">Incident en cours</span>
            <div class="status-content-wrapper">
            <strong>Dysfonctionnement de certains éléments</strong>
            <p class="status-description">
                ${componentListHtml}
            </p>
            <div class="status-time">
                <svg viewBox="0 0 24 24" width="12" height="12">
                <path fill="currentColor" d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                <path fill="currentColor" d="M12.5 7H11v6l5.25 3.15.75-1.23-4.5-2.67z"/>
                </svg> 
                Maintenant
            </div>
            </div>
        `;
        
        // Store the notification ID for dismissal
        statusNotification.dataset.incidentId = notificationId;
        
        // Animation
        statusNotification.style.display = 'flex';
        setTimeout(() => {
            statusNotification.classList.add('visible');
        }, 10);
    }
});