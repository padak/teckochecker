/**
 * TeckoChecker Web UI Application
 */

class TeckoApp {
    constructor() {
        this.jobsRefreshInterval = null;  // Auto-refresh for jobs tab
        this.currentTab = 'jobs';  // Track active tab
        this.checkAuth();
    }

    /**
     * Check authentication and show login if needed
     */
    checkAuth() {
        if (!api.hasCredentials()) {
            this.showLoginModal();
        } else {
            this.init();
        }
    }

    /**
     * Show login modal
     */
    showLoginModal() {
        const modal = document.getElementById('login-modal');
        modal.style.display = 'block';
        modal.classList.add('active');

        const form = document.getElementById('login-form');
        form.addEventListener('submit', (e) => this.handleLogin(e));
    }

    /**
     * Handle login form submission
     */
    async handleLogin(e) {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;

        // Set credentials in API client
        api.setCredentials(username, password);

        // Try to validate by making a test request
        try {
            await api.getHealth();

            // Success! Hide modal and initialize app
            const modal = document.getElementById('login-modal');
            modal.style.display = 'none';
            modal.classList.remove('active');

            this.init();
        } catch (error) {
            // Login failed
            api.clearCredentials();
            alert('Login failed. Please check your username and password.');
        }
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
        this.loadHealth();

        // Start auto-refresh for jobs (default tab)
        this.startJobsAutoRefresh();
    }

    /**
     * Switch between tabs
     */
    switchTab(tabName) {
        // Stop jobs auto-refresh when leaving jobs tab
        if (this.currentTab === 'jobs' && tabName !== 'jobs') {
            this.stopJobsAutoRefresh();
        }

        // Update current tab
        this.currentTab = tabName;

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
                this.startJobsAutoRefresh();  // Start auto-refresh for jobs
                break;
            case 'keboola':
                // Keboola Setup tab - static content, no loading needed
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
            <tr onclick="app.showJobDetail(${job.id})" style="cursor: pointer;">
                <td class="text-dim">${job.id}</td>
                <td>${this.escapeHtml(job.name)}</td>
                <td>
                    ${this.renderBatchSummary(job)}
                </td>
                <td>
                    <span class="status-dot ${job.status}"></span>
                    ${job.status}
                </td>
                <td class="text-dim">
                    ${this.formatNextCheck(job)}
                </td>
                <td onclick="event.stopPropagation();">
                    ${this.renderJobActions(job)}
                </td>
            </tr>
        `).join('');
    }

    renderBatchSummary(job) {
        const batchCount = job.batch_count || 0;
        const completedCount = job.completed_count || 0;
        const failedCount = job.failed_count || 0;
        const inProgressCount = batchCount - completedCount - failedCount;

        let html = `<span class="batch-badge">${completedCount}/${batchCount} completed</span>`;

        if (inProgressCount > 0) {
            html += ` <span class="batch-badge in-progress">${inProgressCount} in progress</span>`;
        }

        if (failedCount > 0) {
            html += ` <span class="batch-badge failed">${failedCount} failed</span>`;
        }

        return html;
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

        // Parse batch_ids textarea into array
        const batchIdsText = formData.get('batch_ids');
        const batchIds = batchIdsText
            .split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0);

        // Validation
        if (batchIds.length === 0) {
            this.showError('Validation Error', new Error('At least one batch ID is required'));
            return;
        }
        if (batchIds.length > 10) {
            this.showError('Validation Error', new Error('Maximum 10 batch IDs allowed'));
            return;
        }

        // Validate batch_id format
        const invalidBatches = batchIds.filter(id => !id.startsWith('batch_'));
        if (invalidBatches.length > 0) {
            this.showError('Validation Error', new Error(`Invalid batch ID format: ${invalidBatches[0]} (must start with 'batch_')`));
            return;
        }

        // Build payload
        const data = {
            name: formData.get('name'),
            batch_ids: batchIds,
            openai_secret_id: parseInt(formData.get('openai_secret_id')),
            keboola_secret_id: parseInt(formData.get('keboola_secret_id')),
            keboola_stack_url: formData.get('keboola_stack_url'),
            keboola_component_id: formData.get('keboola_component_id'),
            keboola_configuration_id: formData.get('keboola_configuration_id'),
            poll_interval_seconds: parseInt(formData.get('poll_interval_seconds'))
        };

        try {
            await api.createJob(data);
            this.closeModal('add-job-modal');
            e.target.reset();
            this.loadJobs();
            this.showSuccess(`Job created with ${batchIds.length} batch ID${batchIds.length > 1 ? 's' : ''}`);
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

    /**
     * Start auto-refresh for jobs (every 10 seconds)
     */
    startJobsAutoRefresh() {
        // Clear existing interval if any
        this.stopJobsAutoRefresh();

        // Refresh every 10 seconds
        this.jobsRefreshInterval = setInterval(() => {
            this.loadJobs();
        }, 10000);
    }

    /**
     * Stop auto-refresh for jobs
     */
    stopJobsAutoRefresh() {
        if (this.jobsRefreshInterval) {
            clearInterval(this.jobsRefreshInterval);
            this.jobsRefreshInterval = null;
        }
    }

    async showJobDetail(jobId) {
        try {
            const job = await api.getJob(jobId);

            // Build batches table HTML
            const batchesHtml = job.batches && job.batches.length > 0
                ? job.batches.map(batch => `
                    <tr>
                        <td class="text-secondary">${this.escapeHtml(batch.batch_id)}</td>
                        <td class="status-${batch.status}">${batch.status}</td>
                        <td class="text-dim">${this.formatDate(batch.created_at)}</td>
                        <td class="text-dim">${batch.completed_at ? this.formatDate(batch.completed_at) : '-'}</td>
                    </tr>
                  `).join('')
                : '<tr><td colspan="4" class="text-muted text-center">No batches found</td></tr>';

            // Create modal HTML
            const modalHtml = `
                <div id="job-detail-modal" class="modal active">
                    <div class="modal-content" style="max-width: 800px;">
                        <div class="modal-header">
                            <h2 class="modal-title">Job #${job.id}: ${this.escapeHtml(job.name)}</h2>
                        </div>

                        <div class="mb-20">
                            <h3 class="text-secondary mb-10">> Batch Status</h3>
                            <table class="batches-table">
                                <thead>
                                    <tr>
                                        <th>Batch ID</th>
                                        <th>Status</th>
                                        <th>Created</th>
                                        <th>Completed</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${batchesHtml}
                                </tbody>
                            </table>
                        </div>

                        <div class="mb-20">
                            <h3 class="text-secondary mb-10">> Summary</h3>
                            <div class="text-dim">
                                <div class="mb-10">Total batches: <span class="text-primary">${job.batch_count || 0}</span></div>
                                <div class="mb-10">Completed: <span class="text-success">${job.completed_count || 0}</span></div>
                                <div class="mb-10">Failed: <span class="text-error">${job.failed_count || 0}</span></div>
                                <div class="mb-10">In progress: <span class="text-warning">${(job.batch_count || 0) - (job.completed_count || 0) - (job.failed_count || 0)}</span></div>
                                <div class="mb-10">Status: <span class="status-dot ${job.status}"></span> ${job.status}</div>
                                <div class="mb-10">Poll interval: <span class="text-primary">${job.poll_interval_seconds}s</span></div>
                            </div>
                        </div>

                        <div class="btn-group">
                            <button type="button" class="btn btn-primary" onclick="app.closeModal('job-detail-modal')">Close</button>
                        </div>
                    </div>
                </div>
            `;

            // Insert modal into DOM
            document.body.insertAdjacentHTML('beforeend', modalHtml);

            // Add click outside to close
            const modal = document.getElementById('job-detail-modal');
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeModal('job-detail-modal');
                }
            });
        } catch (error) {
            this.showError('Failed to load job details', error);
        }
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
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            // Remove dynamically created modals from DOM
            if (modalId === 'job-detail-modal') {
                modal.remove();
            }
        }
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

    formatNextCheck(job) {
        // For terminal states (completed, failed), show "Never"
        if (job.status === 'completed' || job.status === 'failed' || job.status === 'completed_with_failures') {
            return 'Never';
        }

        // For paused jobs, show "Paused"
        if (job.status === 'paused') {
            return 'Paused';
        }

        // For active jobs, check if next_check_at is in the past
        if (job.next_check_at) {
            const date = new Date(job.next_check_at);
            const now = new Date();
            const diff = Math.floor((date - now) / 1000);

            // If next_check is in the past, job is likely checking now
            if (diff < 0) {
                return 'checking...';
            }

            // Otherwise show relative time
            return this.formatRelativeTime(job.next_check_at);
        }

        return '-';
    }

    handleCommand(command) {
        const input = document.getElementById('command-line');
        const cmd = command.trim().toLowerCase();

        switch(cmd) {
            case 'help':
                this.showTerminalOutput([
                    '> TECKOCHECKER TERMINAL v0.9.5',
                    '',
                    'AVAILABLE COMMANDS:',
                    '  help     - Show this help message',
                    '  about    - About TeckoChecker',
                    '  credits  - Show credits',
                    '  snake    - Play Snake game',
                    '  hack     - Initiate hacking sequence',
                    '  matrix   - Enter the Matrix',
                    '  refresh  - Refresh current tab',
                    '  clear    - Clear terminal',
                    '',
                    'Type any command and press ENTER'
                ]);
                break;
            case 'about':
                this.showTerminalOutput([
                    '> TECKOCHECKER',
                    '',
                    'A polling orchestration system for async workflows.',
                    '',
                    'Features:',
                    '  - Multi-batch OpenAI job monitoring',
                    '  - Automatic Keboola integration',
                    '  - Real-time status tracking',
                    '  - REST API + CLI + Web UI',
                    '',
                    'Version: 0.9.5',
                    'License: MIT',
                    'Repository: github.com/padak/teckochecker'
                ]);
                break;
            case 'credits':
                this.showTerminalOutput([
                    '> CREDITS',
                    '',
                    'Inspired by: Tomas Trnka (tomas.trnka@live.com)',
                    'Spiritual Father of TeckoChecker',
                    '',
                    'Built with:',
                    '  - Python 3.11+',
                    '  - FastAPI',
                    '  - SQLite',
                    '  - Lots of caffeine',
                    '',
                    'Special thanks to the open source community!'
                ]);
                break;
            case 'snake':
                this.launchSnakeGame();
                break;
            case 'hack':
                this.runHackingSequence();
                break;
            case 'matrix':
                this.runMatrixEffect();
                break;
            case 'refresh':
                location.reload();
                break;
            case 'clear':
                break;
            default:
                if (cmd) {
                    this.showTerminalOutput([
                        `> ERROR: Unknown command '${cmd}'`,
                        `> Type 'help' for available commands`
                    ]);
                }
        }

        input.value = '';
    }

    showTerminalOutput(lines) {
        const output = lines.join('\n');
        alert(output);
    }

    launchSnakeGame() {
        const game = new SnakeGame();
        game.start();
    }

    runHackingSequence() {
        const modal = document.createElement('div');
        modal.id = 'hack-modal';
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-content hack-terminal">
                <div id="hack-output" class="hack-output"></div>
            </div>
        `;
        document.body.appendChild(modal);

        const output = document.getElementById('hack-output');
        const commands = [
            'Initializing hack sequence...',
            'Connecting to mainframe...',
            'Bypassing firewall...',
            'Decrypting database...',
            'Downloading batch files...',
            'Access granted!',
            'Just kidding :)',
            '',
            'Press ESC or click to close'
        ];

        let index = 0;
        const interval = setInterval(() => {
            if (index < commands.length) {
                output.innerHTML += `<div class="hack-line">> ${commands[index]}</div>`;
                output.scrollTop = output.scrollHeight;
                index++;
            } else {
                clearInterval(interval);
            }
        }, 500);

        const close = () => {
            modal.remove();
        };

        modal.addEventListener('click', (e) => {
            if (e.target === modal) close();
        });

        document.addEventListener('keydown', function escHandler(e) {
            if (e.key === 'Escape') {
                close();
                document.removeEventListener('keydown', escHandler);
            }
        });
    }

    runMatrixEffect() {
        const modal = document.createElement('div');
        modal.id = 'matrix-modal';
        modal.className = 'modal active';
        modal.innerHTML = `
            <div class="modal-content matrix-container">
                <canvas id="matrix-canvas"></canvas>
                <div class="matrix-text">THE MATRIX HAS YOU...<br>Press ESC to exit</div>
            </div>
        `;
        document.body.appendChild(modal);

        const canvas = document.getElementById('matrix-canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth * 0.9;
        canvas.height = window.innerHeight * 0.8;

        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%^&*()';
        const fontSize = 14;
        const columns = canvas.width / fontSize;
        const drops = Array(Math.floor(columns)).fill(1);

        const draw = () => {
            ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.fillStyle = '#00ff41';
            ctx.font = fontSize + 'px monospace';

            for (let i = 0; i < drops.length; i++) {
                const text = chars[Math.floor(Math.random() * chars.length)];
                ctx.fillText(text, i * fontSize, drops[i] * fontSize);

                if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        };

        const matrixInterval = setInterval(draw, 33);

        const close = () => {
            clearInterval(matrixInterval);
            modal.remove();
        };

        modal.addEventListener('click', (e) => {
            if (e.target === modal) close();
        });

        document.addEventListener('keydown', function escHandler(e) {
            if (e.key === 'Escape') {
                close();
                document.removeEventListener('keydown', escHandler);
            }
        });
    }
}

// Initialize app when DOM is ready
let app;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => app = new TeckoApp());
} else {
    app = new TeckoApp();
}