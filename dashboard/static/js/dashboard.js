// Pi Fleet Manager - Dashboard JavaScript

const API_BASE = window.location.origin;
let currentDeviceId = null;
let refreshInterval = null;

// Utility functions
function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatUptime(seconds) {
    if (!seconds) return '0s';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

function timeAgo(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

// API functions
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Update functions
async function updateFleetSummary() {
    try {
        const summary = await apiCall('/api/fleet/summary');

        document.getElementById('total-devices').textContent = summary.total_devices;
        document.getElementById('online-devices').textContent = summary.online_devices;
        document.getElementById('offline-devices').textContent = summary.offline_devices;
        document.getElementById('avg-cpu').textContent = summary.averages.cpu_percent + '%';
        document.getElementById('avg-memory').textContent = summary.averages.memory_percent + '%';
        document.getElementById('avg-temp').textContent = summary.averages.temperature ?
            summary.averages.temperature + '°C' : 'N/A';

        // Update server status
        const statusBadge = document.getElementById('server-status');
        statusBadge.textContent = 'Online';
        statusBadge.className = 'status-badge online';

    } catch (error) {
        console.error('Failed to update fleet summary:', error);
        const statusBadge = document.getElementById('server-status');
        statusBadge.textContent = 'Offline';
        statusBadge.className = 'status-badge offline';
    }
}

async function updateDeviceList() {
    try {
        const data = await apiCall('/api/devices');
        const container = document.getElementById('devices-container');

        if (data.devices.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📡</div>
                    <p>No devices registered yet.</p>
                    <p style="font-size: 14px; margin-top: 10px;">Install and run the agent on your Raspberry Pi devices to get started.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = '';

        for (const device of data.devices) {
            const card = createDeviceCard(device);
            container.appendChild(card);
        }

    } catch (error) {
        console.error('Failed to update device list:', error);
    }
}

function createDeviceCard(device) {
    const card = document.createElement('div');
    card.className = `device-card ${device.status}`;
    card.onclick = () => showDeviceDetails(device.device_id);

    const statusClass = device.status === 'online' ? 'online' : 'offline';

    // Get latest metrics (we'll need to fetch these separately in a real implementation)
    // For now, we'll just show the device info
    card.innerHTML = `
        <div class="device-header">
            <div>
                <div class="device-name">${device.device_name}</div>
                <div class="device-model">${device.hardware.model || 'Unknown Model'}</div>
            </div>
            <div class="device-status ${statusClass}"></div>
        </div>
        <div class="device-info">
            <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 8px;">
                ${device.os.distribution || device.os.system || 'Unknown OS'}
            </div>
            <div style="font-size: 13px; color: var(--text-secondary);">
                Last seen: ${timeAgo(device.last_seen)}
            </div>
        </div>
    `;

    return card;
}

async function showDeviceDetails(deviceId) {
    currentDeviceId = deviceId;

    try {
        const device = await apiCall(`/api/devices/${deviceId}`);
        const metrics = await apiCall(`/api/devices/${deviceId}/metrics?limit=1`);

        const modal = document.getElementById('device-modal');
        document.getElementById('modal-device-name').textContent = device.device_name;

        // Update overview tab
        const detailsContainer = document.getElementById('device-details');
        const latestMetric = metrics.metrics[0];

        detailsContainer.innerHTML = `
            <div class="detail-grid">
                <div class="detail-section">
                    <h3>Device Information</h3>
                    <div class="detail-item">
                        <span class="detail-label">Name</span>
                        <span class="detail-value">${device.device_name}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Device ID</span>
                        <span class="detail-value">${device.device_id}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Status</span>
                        <span class="detail-value">${device.status}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Agent Version</span>
                        <span class="detail-value">${device.agent_version || 'N/A'}</span>
                    </div>
                </div>

                <div class="detail-section">
                    <h3>Hardware</h3>
                    <div class="detail-item">
                        <span class="detail-label">Model</span>
                        <span class="detail-value">${device.hardware.model || 'Unknown'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Revision</span>
                        <span class="detail-value">${device.hardware.revision || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">CPU Cores</span>
                        <span class="detail-value">${device.hardware.cpu_count || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Memory</span>
                        <span class="detail-value">${formatBytes(device.hardware.total_memory)}</span>
                    </div>
                </div>

                <div class="detail-section">
                    <h3>Operating System</h3>
                    <div class="detail-item">
                        <span class="detail-label">Distribution</span>
                        <span class="detail-value">${device.os.distribution || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">System</span>
                        <span class="detail-value">${device.os.system || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Release</span>
                        <span class="detail-value">${device.os.release || 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Architecture</span>
                        <span class="detail-value">${device.os.architecture || 'N/A'}</span>
                    </div>
                </div>

                ${latestMetric ? `
                <div class="detail-section">
                    <h3>Current Metrics</h3>
                    <div class="detail-item">
                        <span class="detail-label">CPU Usage</span>
                        <span class="detail-value">${latestMetric.cpu.percent}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Memory Usage</span>
                        <span class="detail-value">${latestMetric.memory.percent}%</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Temperature</span>
                        <span class="detail-value">${latestMetric.temperature ? latestMetric.temperature + '°C' : 'N/A'}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Uptime</span>
                        <span class="detail-value">${formatUptime(latestMetric.uptime)}</span>
                    </div>
                </div>
                ` : ''}
            </div>
        `;

        // Load command history
        loadCommandHistory(deviceId);

        modal.classList.add('active');

    } catch (error) {
        console.error('Failed to load device details:', error);
        alert('Failed to load device details');
    }
}

async function loadCommandHistory(deviceId) {
    try {
        const data = await apiCall(`/api/devices/${deviceId}/commands/history?limit=10`);
        const container = document.getElementById('command-history-list');

        if (data.commands.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary);">No command history</p>';
            return;
        }

        container.innerHTML = '';

        for (const cmd of data.commands) {
            const cmdElement = document.createElement('div');
            cmdElement.className = 'command-item';

            const result = cmd.result || {};
            const hasOutput = result.output || result.error;

            cmdElement.innerHTML = `
                <div class="command-header">
                    <span class="command-type">${cmd.type}</span>
                    <span class="command-status ${cmd.status}">${cmd.status}</span>
                </div>
                <div style="font-size: 12px; color: var(--text-secondary);">
                    ${new Date(cmd.created_at).toLocaleString()}
                </div>
                ${hasOutput ? `
                    <div class="command-output">
                        ${result.output || result.error || ''}
                    </div>
                ` : ''}
            `;

            container.appendChild(cmdElement);
        }

    } catch (error) {
        console.error('Failed to load command history:', error);
    }
}

async function sendCommand() {
    if (!currentDeviceId) return;

    const type = document.getElementById('command-type').value;
    const payload = buildCommandPayload(type);

    try {
        await apiCall(`/api/devices/${currentDeviceId}/commands`, {
            method: 'POST',
            body: JSON.stringify({ type, payload }),
        });

        alert('Command sent successfully!');
        loadCommandHistory(currentDeviceId);

    } catch (error) {
        console.error('Failed to send command:', error);
        alert('Failed to send command');
    }
}

function buildCommandPayload(type) {
    const payloadDiv = document.getElementById('command-payload');

    switch (type) {
        case 'shell':
            const command = payloadDiv.querySelector('textarea')?.value || '';
            return { command, timeout: 300 };

        case 'update':
            return { update_type: 'packages' };

        case 'service':
            const service = payloadDiv.querySelector('input[name="service"]')?.value || '';
            const action = payloadDiv.querySelector('select[name="action"]')?.value || 'status';
            return { service, action };

        case 'reboot':
            const delay = parseInt(payloadDiv.querySelector('input[name="delay"]')?.value || '1');
            return { delay };

        default:
            return {};
    }
}

function updateCommandPayloadForm() {
    const type = document.getElementById('command-type').value;
    const payloadDiv = document.getElementById('command-payload');

    switch (type) {
        case 'shell':
            payloadDiv.innerHTML = `
                <label>Command:</label>
                <textarea placeholder="Enter shell command..."></textarea>
            `;
            break;

        case 'update':
            payloadDiv.innerHTML = `
                <p style="color: var(--text-secondary); font-size: 14px;">
                    This will run 'apt-get update && apt-get upgrade -y' on the device.
                </p>
            `;
            break;

        case 'service':
            payloadDiv.innerHTML = `
                <label>Service Name:</label>
                <input type="text" name="service" placeholder="e.g., nginx">
                <label>Action:</label>
                <select name="action">
                    <option value="status">Status</option>
                    <option value="start">Start</option>
                    <option value="stop">Stop</option>
                    <option value="restart">Restart</option>
                </select>
            `;
            break;

        case 'reboot':
            payloadDiv.innerHTML = `
                <label>Delay (minutes):</label>
                <input type="number" name="delay" value="1" min="1">
            `;
            break;
    }
}

// Modal management
function closeModal() {
    const modal = document.getElementById('device-modal');
    modal.classList.remove('active');
    currentDeviceId = null;
}

// Tab management
function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
}

// Update last update time
function updateLastUpdateTime() {
    document.getElementById('last-update').textContent =
        `Last update: ${new Date().toLocaleTimeString()}`;
}

// Main update function
async function refreshAll() {
    await updateFleetSummary();
    await updateDeviceList();
    updateLastUpdateTime();
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Initial load
    refreshAll();

    // Auto-refresh every 30 seconds
    refreshInterval = setInterval(refreshAll, 30000);

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', refreshAll);

    // Modal close button
    document.querySelector('.close').addEventListener('click', closeModal);

    // Close modal on outside click
    window.addEventListener('click', (event) => {
        const modal = document.getElementById('device-modal');
        if (event.target === modal) {
            closeModal();
        }
    });

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });

    // Command type change
    document.getElementById('command-type').addEventListener('change', updateCommandPayloadForm);

    // Send command button
    document.getElementById('send-command-btn').addEventListener('click', sendCommand);

    // Initialize command form
    updateCommandPayloadForm();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});
