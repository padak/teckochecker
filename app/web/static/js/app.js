/**
 * TeckoChecker Web UI Application
 */

class TeckoApp {
    constructor() {
        this.autoRefreshInterval = null;
        this.autoRefreshEnabled = false;
        this.init();
    }

    /**
     * Initialize the application
     */
    init() {
        // Setup tab navigation
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
        });

        // Setup forms
        document.getElementById('add-secret-form').addEventListener('submit', (e) => this.handleAddSecret(e));
        document.getElementById('add-job-form').addEventListener('submit', (e) => this.handleAddJob(e));

        // Setup command line
        document.getElementById('command-line').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleCommand(e.target.value);
        });

        // Load initial data
        this.loadSecrets();
        this.loadJobs();
        this.loadStats();
        this.loadHealth();
    }

    /**
     * Switch between tabs
     */
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === tabName);
        });

        // Load data for the active tab
        switch(tabName) {
            case 'secrets':
                this.loadSecrets();
                break;
            case 'jobs':
                this.loadJobs();
                break;
            case 'monitor':
                this.loadStats();
                break;
            case 'logs':
                this.loadLogs();
                break;
            case 'system':
                this.loadHealth();
                break;
        }
    }

    // ==================== Secrets Management ====================

    async loadSecrets() {
        try {
            const result = await api.getSecrets();
            const secrets = result.secrets || [];
            this.renderSecrets(secrets);
        } catch (error) {
            this.showError('Failed to load secrets', error);
        }
    }

    renderSecrets(secrets) {
        const tbody = document.getElementById('secrets-table');

        if (secrets.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center">No secrets found. Add one to get started.</td></tr>';
            return;
        }

        tbody.innerHTML = secrets.map(secret => `
            <tr>
                <td>${this.escapeHtml(secret.name)}</td>
                <td><span class="text-dim">${secret.type}</span></td>
                <td class="text-dim">${this.formatDate(secret.created_at)}</td>
                <td>
                    <button class="btn btn-danger" onclick="app.deleteSecret(${secret.id}, '${this.escapeHtml(secret.name)}')">
                        Delete
                    </button>
                </td>
            </tr>
        `).join('');
    }

    showAddSecretModal() {
        document.getElementById('add-secret-modal').classList.add('active');
    }

    async handleAddSecret(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        try {
            await api.addSecret(data);
            this.closeModal('add-secret-modal');
            e.target.reset();
            this.loadSecrets();
            this.showSuccess('Secret added successfully');
        } catch (error) {
            this.showError('Failed to add secret', error);
        }
    }

    async deleteSecret(id, name) {
        if (!confirm(`Delete secret "${name}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            await api.deleteSecret(id);
            this.loadSecrets();
            this.showSuccess('Secret deleted');
        } catch (error) {
            this.showError('Failed to delete secret', error);
        }
    }

    // ==================== Jobs Management ====================

    async loadJobs() {
        try {
            const result = await api.getJobs();
            const jobs = result.jobs || [];
            this.renderJobs(jobs);
        } catch (error) {
            this.showError('Failed to load jobs', error);
        }
    }

    renderJobs(jobs) {
        const tbody = document.getElementById('jobs-table');

        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-muted text-center">No jobs found. Create one to start polling.</td></tr>';
            return;
        }

        tbody.innerHTML = jobs.map(job => `
            <tr>
                <td class="text-dim">${job.id}</td>
                <td>${this.escapeHtml(job.name)}</td>
                <td class="text-dim">${this.escapeHtml(job.batch_id)}</td>
                <td>
                    <span class="status-dot ${job.status}"></span>
                    ${job.status}
                </td>
                <td class="text-dim">
                    ${job.next_check_at ? this.formatRelativeTime(job.next_check_at) : '-'}
                </td>
                <td>
                    ${this.renderJobActions(job)}
                </td>
            </tr>
        `).join('');
    }

    renderJobActions(job) {
        const actions = [];

        if (job.status === 'active') {
            actions.push(`<button class="btn" onclick="app.pauseJob(${job.id})">Pause</button>`);
        } else if (job.status === 'paused') {
            actions.push(`<button class="btn btn-primary" onclick="app.resumeJob(${job.id})">Resume</button>`);
        }

        actions.push(`<button class="btn btn-danger" onclick="app.deleteJob(${job.id}, '${this.escapeHtml(job.name)}')">Delete</button>`);

        return actions.join('');
    }

    async showAddJobModal() {
        // Load secrets for the dropdowns
        try {
            const result = await api.getSecrets();
            const secrets = result.secrets || [];

            const openaiSecrets = secrets.filter(s => s.type === 'openai');
            const keboolaSecrets = secrets.filter(s => s.type === 'keboola');

            document.getElementById('openai-secret-select').innerHTML =
                openaiSecrets.map(s => `<option value="${s.id}">${this.escapeHtml(s.name)}</option>`).join('');

            document.getElementById('keboola-secret-select').innerHTML =
                keboolaSecrets.map(s => `<option value="${s.id}">${this.escapeHtml(s.name)}</option>`).join('');

            document.getElementById('add-job-modal').classList.add('active');
        } catch (error) {
            this.showError('Failed to load secrets', error);
        }
    }

    async handleAddJob(e) {
        e.preventDefault();
        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);

        // Convert IDs to integers
        data.openai_secret_id = parseInt(data.openai_secret_id);
        data.keboola_secret_id = parseInt(data.keboola_secret_id);
        data.poll_interval_seconds = parseInt(data.poll_interval_seconds);

        try {
            await api.createJob(data);
            this.closeModal('add-job-modal');
            e.target.reset();
            this.loadJobs();
            this.showSuccess('Job created successfully');
        } catch (error) {
            this.showError('Failed to create job', error);
        }
    }

    async pauseJob(id) {
        try {
            await api.pauseJob(id);
            this.loadJobs();
            this.showSuccess('Job paused');
        } catch (error) {
            this.showError('Failed to pause job', error);
        }
    }

    async resumeJob(id) {
        try {
            await api.resumeJob(id);
            this.loadJobs();
            this.showSuccess('Job resumed');
        } catch (error) {
            this.showError('Failed to resume job', error);
        }
    }

    async deleteJob(id, name) {
        if (!confirm(`Delete job "${name}"?\n\nThis action cannot be undone.`)) {
            return;
        }

        try {
            await api.deleteJob(id);
            this.loadJobs();
            this.showSuccess('Job deleted');
        } catch (error) {
            this.showError('Failed to delete job', error);
        }
    }

    // ==================== Monitor ====================

    async loadStats() {
        try {
            const stats = await api.getStats();
            this.renderStats(stats);
        } catch (error) {
            this.showError('Failed to load stats', error);
        }
    }

    renderStats(stats) {
        const statusDiv = document.getElementById('system-status');
        const activityDiv = document.getElementById('recent-activity');

        statusDiv.innerHTML = `
            <div class="mb-10">
                <span class="status-dot active"></span>
                <span class="text-success">SYSTEM RUNNING</span>
            </div>
            <div class="text-secondary mb-10">Active Jobs: <span class="text-primary">${stats.active_jobs || 0}</span></div>
            <div class="text-secondary mb-10">Total Jobs: <span class="text-primary">${stats.total_jobs || 0}</span></div>
            <div class="text-secondary">Database: <span class="text-dim">${stats.database || 'sqlite'}</span></div>
        `;

        // Show recent polling logs if available
        this.loadLogs(10); // Load last 10 logs
    }

    // ==================== Logs ====================

    async loadLogs(limit = 50) {
        try {
            // For now, we'll fetch jobs and show their status
            // In a real implementation, you'd have a logs endpoint
            const result = await api.getJobs();
            const jobs = result.jobs || [];

            const activityDiv = document.getElementById('recent-activity');
            const logsDiv = document.getElementById('logs-display');

            const logLines = jobs.slice(0, limit).map(job => {
                const timestamp = this.formatTimestamp(job.last_check_at || job.created_at);
                const level = job.status === 'failed' ? 'error' : job.status === 'active' ? 'info' : 'success';
                return `<div class="log-line ${level}">[${timestamp}] Job #${job.id} (${job.name}) - Status: ${job.status}</div>`;
            }).join('');

            if (activityDiv) activityDiv.innerHTML = logLines || '<div class="text-muted">No recent activity</div>';
            if (logsDiv) logsDiv.innerHTML = logLines || '<div class="text-muted">No logs available</div>';
        } catch (error) {
            this.showError('Failed to load logs', error);
        }
    }

    toggleAutoRefresh() {
        this.autoRefreshEnabled = !this.autoRefreshEnabled;
        const btn = document.getElementById('auto-refresh-btn');

        if (this.autoRefreshEnabled) {
            btn.textContent = '▶ Auto-refresh ON';
            this.autoRefreshInterval = setInterval(() => this.loadLogs(), 5000);
        } else {
            btn.textContent = '⏸ Auto-refresh OFF';
            if (this.autoRefreshInterval) {
                clearInterval(this.autoRefreshInterval);
            }
        }
    }

    clearLogs() {
        document.getElementById('logs-display').innerHTML = '<div class="text-muted">Logs cleared</div>';
    }

    // ==================== System ====================

    async loadHealth() {
        try {
            const health = await api.getHealth();
            this.renderHealth(health);
        } catch (error) {
            this.showError('Failed to load health', error);
        }
    }

    renderHealth(health) {
        const healthDiv = document.getElementById('health-display');

        healthDiv.innerHTML = `
            <div class="mb-10">
                <span class="status-dot ${health.status === 'healthy' ? 'active' : 'failed'}"></span>
                <span class="${health.status === 'healthy' ? 'text-success' : 'text-error'}">
                    ${health.status ? health.status.toUpperCase() : 'UNKNOWN'}
                </span>
            </div>
            <pre class="text-dim">${JSON.stringify(health, null, 2)}</pre>
        `;
    }

    // ==================== Utilities ====================

    closeModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    }

    showSuccess(message) {
        console.log('✓', message);
        // You could implement a toast notification here
    }

    showError(message, error) {
        console.error('✗', message, error);
        alert(`${message}\n\n${error?.message || error}`);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatDate(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    }

    formatTimestamp(dateString) {
        if (!dateString) return '--:--:--';
        const date = new Date(dateString);
        return date.toTimeString().split(' ')[0];
    }

    formatRelativeTime(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        const now = new Date();
        const diff = Math.floor((date - now) / 1000);

        if (diff < 0) return 'overdue';
        if (diff < 60) return `in ${diff}s`;
        if (diff < 3600) return `in ${Math.floor(diff / 60)}m`;
        return `in ${Math.floor(diff / 3600)}h`;
    }

    handleCommand(command) {
        const input = document.getElementById('command-line');
        const cmd = command.trim().toLowerCase();

        switch(cmd) {
            case 'help':
                alert('Available commands:\nhelp - Show this help\nrefresh - Refresh current tab\nclear - Clear command input');
                break;
            case 'refresh':
                location.reload();
                break;
            case 'clear':
                break;
            default:
                if (cmd) {
                    alert(`Unknown command: ${cmd}\nType 'help' for available commands.`);
                }
        }

        input.value = '';
    }
}

// Initialize app when DOM is ready
let app;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => app = new TeckoApp());
} else {
    app = new TeckoApp();
}