/**
 * TeckoChecker API Client
 */

class TeckoAPI {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
        this.credentials = null;
        this.loadCredentials();
    }

    /**
     * Load credentials from sessionStorage
     */
    loadCredentials() {
        const stored = sessionStorage.getItem('tecko_credentials');
        if (stored) {
            this.credentials = stored;
        }
    }

    /**
     * Set credentials for authentication
     */
    setCredentials(username, password) {
        const encoded = btoa(`${username}:${password}`);
        this.credentials = encoded;
        sessionStorage.setItem('tecko_credentials', encoded);
    }

    /**
     * Check if credentials are set
     */
    hasCredentials() {
        return this.credentials !== null;
    }

    /**
     * Clear credentials
     */
    clearCredentials() {
        this.credentials = null;
        sessionStorage.removeItem('tecko_credentials');
    }

    /**
     * Generic request handler
     */
    async request(method, path, body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        // Add Authorization header if credentials are available
        if (this.credentials) {
            options.headers['Authorization'] = `Basic ${this.credentials}`;
        }

        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseUrl}${path}`, options);

            if (!response.ok) {
                const error = await response.json().catch(() => ({
                    detail: `HTTP ${response.status}: ${response.statusText}`
                }));
                throw new Error(error.detail || `Request failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    // ==================== Secrets Management ====================

    /**
     * Get all secrets (without values)
     */
    async getSecrets() {
        return this.request('GET', '/admin/secrets');
    }

    /**
     * Add new secret
     */
    async addSecret(data) {
        return this.request('POST', '/admin/secrets', data);
    }

    /**
     * Delete secret
     */
    async deleteSecret(id) {
        return this.request('DELETE', `/admin/secrets/${id}`);
    }

    // ==================== Jobs Management ====================

    /**
     * Get all jobs
     */
    async getJobs() {
        return this.request('GET', '/jobs');
    }

    /**
     * Get job by ID
     */
    async getJob(id) {
        return this.request('GET', `/jobs/${id}`);
    }

    /**
     * Create new job
     */
    async createJob(data) {
        return this.request('POST', '/jobs', data);
    }

    /**
     * Update job
     */
    async updateJob(id, data) {
        return this.request('PUT', `/jobs/${id}`, data);
    }

    /**
     * Delete job
     */
    async deleteJob(id) {
        return this.request('DELETE', `/jobs/${id}`);
    }

    /**
     * Pause job
     */
    async pauseJob(id) {
        return this.request('POST', `/jobs/${id}/pause`);
    }

    /**
     * Resume job
     */
    async resumeJob(id) {
        return this.request('POST', `/jobs/${id}/resume`);
    }

    // ==================== System ====================

    /**
     * Health check
     */
    async getHealth() {
        return this.request('GET', '/health');
    }

    /**
     * System statistics
     */
    async getStats() {
        return this.request('GET', '/stats');
    }
}

// Initialize global API client
const api = new TeckoAPI();