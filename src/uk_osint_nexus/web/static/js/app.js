// UK OSINT Nexus - Frontend Application

class OSINTApp {
    constructor() {
        this.currentResults = null;
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        // Search elements
        this.searchInput = document.getElementById('search-input');
        this.searchBtn = document.getElementById('search-btn');
        this.searchOptions = {
            companies: document.getElementById('opt-companies'),
            vehicles: document.getElementById('opt-vehicles'),
            legal: document.getElementById('opt-legal'),
            contracts: document.getElementById('opt-contracts'),
        };

        // Results elements
        this.resultsSection = document.getElementById('results-section');
        this.loadingEl = document.getElementById('loading');
        this.tabContainer = document.getElementById('tabs');
        this.tabContents = document.querySelectorAll('.tab-content');

        // Content containers
        this.companiesContainer = document.getElementById('companies-content');
        this.officersContainer = document.getElementById('officers-content');
        this.vehiclesContainer = document.getElementById('vehicles-content');
        this.legalContainer = document.getElementById('legal-content');
        this.contractsContainer = document.getElementById('contracts-content');
        this.correlationsContainer = document.getElementById('correlations-content');
    }

    bindEvents() {
        // Search
        this.searchBtn.addEventListener('click', () => this.performSearch());
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });

        // Tabs
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });

        // Export buttons
        document.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', () => this.exportResults(btn.dataset.format));
        });
    }

    async performSearch() {
        const query = this.searchInput.value.trim();
        if (!query) {
            this.showNotification('Please enter a search query', 'warning');
            return;
        }

        // Build URL params
        const params = new URLSearchParams({
            q: query,
            companies: this.searchOptions.companies.checked,
            vehicles: this.searchOptions.vehicles.checked,
            legal: this.searchOptions.legal.checked,
            contracts: this.searchOptions.contracts.checked,
            max_results: 20,
            correlate: true,
        });

        // Show loading
        this.showLoading(true);
        this.resultsSection.classList.remove('active');

        try {
            const response = await fetch(`/api/search?${params}`);
            if (!response.ok) {
                throw new Error(`Search failed: ${response.statusText}`);
            }
            const data = await response.json();
            this.currentResults = data;
            this.displayResults(data);
        } catch (error) {
            console.error('Search error:', error);
            this.showNotification(`Search failed: ${error.message}`, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    displayResults(data) {
        // Update tab counts
        this.updateTabCount('companies', data.companies.length);
        this.updateTabCount('officers', data.officers.length);
        this.updateTabCount('vehicles', data.vehicles.length);
        this.updateTabCount('legal', data.legal_cases.length);
        this.updateTabCount('contracts', data.contracts.length);
        this.updateTabCount('correlations', data.correlations.length);

        // Render each section
        this.renderCompanies(data.companies);
        this.renderOfficers(data.officers);
        this.renderVehicles(data.vehicles);
        this.renderLegalCases(data.legal_cases);
        this.renderContracts(data.contracts);
        this.renderCorrelations(data.correlations);

        // Update header stats
        document.getElementById('total-results').textContent = data.total_results;
        document.getElementById('search-timestamp').textContent = new Date(data.timestamp).toLocaleString();

        // Show results section and activate first populated tab
        this.resultsSection.classList.add('active');
        this.activateFirstPopulatedTab(data);

        // Show errors if any
        if (Object.keys(data.errors).length > 0) {
            console.warn('Search errors:', data.errors);
            this.showNotification(`Some sources had errors: ${Object.keys(data.errors).join(', ')}`, 'warning');
        }
    }

    updateTabCount(tabName, count) {
        const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
        const countEl = tab?.querySelector('.tab-count');
        if (countEl) {
            countEl.textContent = count;
        }
    }

    activateFirstPopulatedTab(data) {
        const tabOrder = ['companies', 'officers', 'vehicles', 'legal', 'contracts', 'correlations'];
        const counts = {
            companies: data.companies.length,
            officers: data.officers.length,
            vehicles: data.vehicles.length,
            legal: data.legal_cases.length,
            contracts: data.contracts.length,
            correlations: data.correlations.length,
        };

        for (const tab of tabOrder) {
            if (counts[tab] > 0) {
                this.switchTab(tab);
                return;
            }
        }
        // If nothing found, show companies (will show empty state)
        this.switchTab('companies');
    }

    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });

        // Update tab contents
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}-content`);
        });
    }

    renderCompanies(companies) {
        if (!companies.length) {
            this.companiesContainer.innerHTML = this.emptyState('No companies found');
            return;
        }

        const html = `
            <div class="card-grid">
                ${companies.map(c => this.companyCard(c)).join('')}
            </div>
        `;
        this.companiesContainer.innerHTML = html;
    }

    companyCard(company) {
        const status = company.company_status || 'Unknown';
        const statusClass = status.toLowerCase() === 'active' ? 'badge-success' : 'badge-danger';

        return `
            <div class="card" onclick="app.viewCompany('${company.company_number}')">
                <div class="card-header">
                    <div>
                        <div class="card-title truncate">${this.escapeHtml(company.company_name)}</div>
                        <div class="card-subtitle">${company.company_number}</div>
                    </div>
                    <span class="badge ${statusClass}">${status}</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">Type</span>
                        <span class="card-value">${company.company_type || '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Incorporated</span>
                        <span class="card-value">${this.formatDate(company.date_of_creation)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">SIC Codes</span>
                        <span class="card-value">${(company.sic_codes || []).slice(0, 2).join(', ') || '-'}</span>
                    </div>
                    ${company.registered_office_address ? `
                    <div class="card-row">
                        <span class="card-label">Address</span>
                        <span class="card-value truncate" style="max-width: 200px">${this.formatAddress(company.registered_office_address)}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderOfficers(officers) {
        if (!officers.length) {
            this.officersContainer.innerHTML = this.emptyState('No officers found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Role</th>
                        <th>Company</th>
                        <th>Appointed</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${officers.map(o => `
                        <tr>
                            <td><strong>${this.escapeHtml(o.name)}</strong></td>
                            <td>${o.role || '-'}</td>
                            <td class="clickable" onclick="app.searchQuery('${this.escapeHtml(o.company_name || '')}')">${this.escapeHtml(o.company_name) || '-'}</td>
                            <td>${this.formatDate(o.appointed_on)}</td>
                            <td>
                                ${o.resigned_on
                                    ? `<span class="badge badge-danger">Resigned</span>`
                                    : `<span class="badge badge-success">Active</span>`
                                }
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.officersContainer.innerHTML = html;
    }

    renderVehicles(vehicles) {
        if (!vehicles.length) {
            this.vehiclesContainer.innerHTML = this.emptyState('No vehicles found');
            return;
        }

        const html = `
            <div class="card-grid">
                ${vehicles.map(v => this.vehicleCard(v)).join('')}
            </div>
        `;
        this.vehiclesContainer.innerHTML = html;
    }

    vehicleCard(vehicle) {
        const motStatus = vehicle.mot_status || 'Unknown';
        const motClass = motStatus === 'PASSED' ? 'badge-success' : 'badge-danger';

        return `
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title">${vehicle.registration_number}</div>
                        <div class="card-subtitle">${vehicle.make || ''} ${vehicle.model || ''}</div>
                    </div>
                    <span class="badge ${motClass}">MOT: ${motStatus}</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">Colour</span>
                        <span class="card-value">${vehicle.colour || '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Fuel Type</span>
                        <span class="card-value">${vehicle.fuel_type || '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Year</span>
                        <span class="card-value">${vehicle.year_of_manufacture || '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">MOT Expiry</span>
                        <span class="card-value">${this.formatDate(vehicle.mot_expiry_date)}</span>
                    </div>
                    ${vehicle.mot_history && vehicle.mot_history.length ? `
                    <div class="card-row">
                        <span class="card-label">MOT Tests</span>
                        <span class="card-value">${vehicle.mot_history.length} records</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderLegalCases(cases) {
        if (!cases.length) {
            this.legalContainer.innerHTML = this.emptyState('No legal cases found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Citation</th>
                        <th>Case Name</th>
                        <th>Court</th>
                        <th>Date</th>
                        <th>Link</th>
                    </tr>
                </thead>
                <tbody>
                    ${cases.map(c => `
                        <tr>
                            <td>${this.escapeHtml(c.neutral_citation) || '-'}</td>
                            <td class="truncate" style="max-width: 300px" title="${this.escapeHtml(c.case_name)}">${this.escapeHtml(c.case_name)}</td>
                            <td>${this.escapeHtml(c.court) || '-'}</td>
                            <td>${this.formatDate(c.date_judgment)}</td>
                            <td>
                                ${c.full_text_url
                                    ? `<a href="${c.full_text_url}" target="_blank" class="clickable">View</a>`
                                    : '-'
                                }
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.legalContainer.innerHTML = html;
    }

    renderContracts(contracts) {
        if (!contracts.length) {
            this.contractsContainer.innerHTML = this.emptyState('No contracts found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Buyer</th>
                        <th>Supplier</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${contracts.map(c => `
                        <tr>
                            <td class="truncate" style="max-width: 250px" title="${this.escapeHtml(c.title)}">${this.escapeHtml(c.title)}</td>
                            <td class="clickable" onclick="app.searchQuery('${this.escapeHtml(c.buyer_name || '')}')">${this.escapeHtml(c.buyer_name) || '-'}</td>
                            <td class="clickable" onclick="app.searchQuery('${this.escapeHtml(c.supplier_name || '')}')">${this.escapeHtml(c.supplier_name) || '-'}</td>
                            <td>${this.formatCurrency(c.awarded_value || c.value_high)}</td>
                            <td><span class="badge badge-info">${c.status || '-'}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.contractsContainer.innerHTML = html;
    }

    renderCorrelations(correlations) {
        if (!correlations.length) {
            this.correlationsContainer.innerHTML = this.emptyState('No correlations found between results');
            return;
        }

        const html = `
            <div class="correlations-list">
                ${correlations.map(c => this.correlationItem(c)).join('')}
            </div>
            <div id="graph-container">
                <canvas id="correlation-graph"></canvas>
            </div>
        `;
        this.correlationsContainer.innerHTML = html;

        // Draw graph if we have correlations
        this.drawCorrelationGraph(correlations);
    }

    correlationItem(correlation) {
        const confidence = Math.round(correlation.confidence * 100);
        let confidenceClass = 'confidence-low';
        if (confidence >= 80) confidenceClass = 'confidence-high';
        else if (confidence >= 60) confidenceClass = 'confidence-medium';

        return `
            <div class="correlation-item">
                <div class="correlation-confidence ${confidenceClass}">${confidence}%</div>
                <div class="correlation-detail">
                    <div class="correlation-link">
                        <span class="badge badge-info">${correlation.source_type}</span>
                        →
                        <span class="badge badge-info">${correlation.target_type}</span>
                        <span class="text-muted">(${correlation.link_type})</span>
                    </div>
                    <div class="correlation-evidence">
                        ${correlation.evidence.map(e => this.escapeHtml(e)).join('<br>')}
                    </div>
                </div>
            </div>
        `;
    }

    drawCorrelationGraph(correlations) {
        // Simple visualization - could be enhanced with D3.js or Vis.js
        const canvas = document.getElementById('correlation-graph');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const container = document.getElementById('graph-container');
        canvas.width = container.offsetWidth;
        canvas.height = 400;

        // Extract unique entities
        const entities = new Set();
        correlations.forEach(c => {
            entities.add(c.source_type);
            entities.add(c.target_type);
        });

        // Position entities in a circle
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(centerX, centerY) - 80;
        const entityArray = Array.from(entities);
        const positions = {};

        entityArray.forEach((entity, i) => {
            const angle = (i / entityArray.length) * 2 * Math.PI - Math.PI / 2;
            positions[entity] = {
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle),
            };
        });

        // Draw connections
        correlations.forEach(c => {
            const from = positions[c.source_type];
            const to = positions[c.target_type];
            if (!from || !to) return;

            const confidence = c.confidence;
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.strokeStyle = confidence >= 0.8 ? '#38a169' : confidence >= 0.6 ? '#d69e2e' : '#e53e3e';
            ctx.lineWidth = 2 + confidence * 3;
            ctx.globalAlpha = 0.6;
            ctx.stroke();
            ctx.globalAlpha = 1;
        });

        // Draw entity nodes
        const colors = {
            company: '#3182ce',
            person: '#38a169',
            vehicle: '#d69e2e',
            legal_case: '#e53e3e',
            contract: '#805ad5',
        };

        entityArray.forEach(entity => {
            const pos = positions[entity];
            const color = colors[entity] || '#718096';

            // Node circle
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 30, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 3;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#2d3748';
            ctx.font = 'bold 12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(entity.replace('_', ' ').toUpperCase(), pos.x, pos.y + 50);
        });
    }

    async viewCompany(companyNumber) {
        try {
            const response = await fetch(`/api/company/${companyNumber}?include_officers=true&include_filings=true`);
            if (!response.ok) throw new Error('Failed to load company');
            const data = await response.json();
            this.showCompanyModal(data);
        } catch (error) {
            this.showNotification(`Error loading company: ${error.message}`, 'error');
        }
    }

    showCompanyModal(company) {
        // Simple modal - could be enhanced with a proper modal library
        const officers = company.officers || [];
        const filings = company.filings || [];

        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h2>${this.escapeHtml(company.company_name)}</h2>
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">×</button>
                </div>
                <div class="modal-body">
                    <h3>Company Details</h3>
                    <p><strong>Number:</strong> ${company.company_number}</p>
                    <p><strong>Status:</strong> ${company.company_status}</p>
                    <p><strong>Type:</strong> ${company.company_type}</p>
                    <p><strong>Incorporated:</strong> ${this.formatDate(company.date_of_creation)}</p>
                    ${company.registered_office_address ? `
                        <p><strong>Address:</strong> ${this.formatAddress(company.registered_office_address)}</p>
                    ` : ''}

                    ${officers.length ? `
                        <h3>Officers (${officers.length})</h3>
                        <ul>
                            ${officers.slice(0, 10).map(o => `
                                <li>${this.escapeHtml(o.name)} - ${o.role}
                                    ${o.resigned_on ? '(Resigned)' : '(Active)'}
                                </li>
                            `).join('')}
                        </ul>
                    ` : ''}

                    ${filings.length ? `
                        <h3>Recent Filings</h3>
                        <ul>
                            ${filings.slice(0, 5).map(f => `
                                <li>${f.date || '-'}: ${this.escapeHtml(f.description || 'Filing')}</li>
                            `).join('')}
                        </ul>
                    ` : ''}
                </div>
            </div>
        `;

        // Add modal styles if not present
        if (!document.getElementById('modal-styles')) {
            const style = document.createElement('style');
            style.id = 'modal-styles';
            style.textContent = `
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0,0,0,0.5);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 1000;
                }
                .modal {
                    background: white;
                    border-radius: 12px;
                    max-width: 600px;
                    max-height: 80vh;
                    overflow-y: auto;
                    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
                }
                .modal-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 1.5rem;
                    border-bottom: 1px solid var(--border-color);
                }
                .modal-header h2 {
                    font-size: 1.25rem;
                    color: var(--primary-color);
                }
                .modal-close {
                    background: none;
                    border: none;
                    font-size: 1.5rem;
                    cursor: pointer;
                    color: var(--text-muted);
                }
                .modal-body {
                    padding: 1.5rem;
                }
                .modal-body h3 {
                    margin-top: 1.5rem;
                    margin-bottom: 0.5rem;
                    color: var(--primary-color);
                }
                .modal-body ul {
                    padding-left: 1.5rem;
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(modal);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    }

    searchQuery(query) {
        if (!query) return;
        this.searchInput.value = query;
        this.performSearch();
    }

    async exportResults(format) {
        if (!this.currentResults) {
            this.showNotification('No results to export', 'warning');
            return;
        }

        try {
            const response = await fetch(`/api/export?q=${encodeURIComponent(this.currentResults.query)}&format=${format}`);
            if (!response.ok) throw new Error('Export failed');
            const data = await response.json();

            // Download the file
            const blob = new Blob([data.content], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `osint-report-${Date.now()}.${format === 'markdown' ? 'md' : format}`;
            a.click();
            URL.revokeObjectURL(url);

            this.showNotification(`Exported as ${format.toUpperCase()}`, 'success');
        } catch (error) {
            this.showNotification(`Export failed: ${error.message}`, 'error');
        }
    }

    // Utility methods
    showLoading(show) {
        this.loadingEl.classList.toggle('active', show);
        this.searchBtn.disabled = show;
    }

    showNotification(message, type = 'info') {
        // Simple notification - could be enhanced
        const colors = {
            success: '#38a169',
            warning: '#d69e2e',
            error: '#e53e3e',
            info: '#3182ce',
        };

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            background: ${colors[type] || colors.info};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            z-index: 2000;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    emptyState(message) {
        return `
            <div class="empty-state">
                <div class="empty-state-icon">🔍</div>
                <p>${message}</p>
            </div>
        `;
    }

    formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-GB');
        } catch {
            return dateStr;
        }
    }

    formatCurrency(value) {
        if (!value) return '-';
        return new Intl.NumberFormat('en-GB', {
            style: 'currency',
            currency: 'GBP',
            maximumFractionDigits: 0,
        }).format(value);
    }

    formatAddress(addr) {
        if (!addr) return '-';
        const parts = [
            addr.address_line_1,
            addr.address_line_2,
            addr.locality,
            addr.region,
            addr.postal_code,
        ].filter(Boolean);
        return parts.join(', ');
    }

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Add CSS animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Initialize app
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new OSINTApp();
});
