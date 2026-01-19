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
            charities: document.getElementById('opt-charities'),
            fca: document.getElementById('opt-fca'),
            dvla: document.getElementById('opt-dvla'),
            electoral: document.getElementById('opt-electoral'),
            police: document.getElementById('opt-police'),
            // New sources
            insolvency: document.getElementById('opt-insolvency'),
            disqualified: document.getElementById('opt-disqualified'),
            landRegistry: document.getElementById('opt-land-registry'),
            sanctions: document.getElementById('opt-sanctions'),
            food: document.getElementById('opt-food'),
            gazette: document.getElementById('opt-gazette'),
            cqc: document.getElementById('opt-cqc'),
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
        this.charitiesContainer = document.getElementById('charities-content');
        this.fcaContainer = document.getElementById('fca-content');
        this.donationsContainer = document.getElementById('donations-content');
        this.crimesContainer = document.getElementById('crimes-content');
        this.correlationsContainer = document.getElementById('correlations-content');
        // New containers
        this.insolvencyContainer = document.getElementById('insolvency-content');
        this.disqualifiedContainer = document.getElementById('disqualified-content');
        this.sanctionsContainer = document.getElementById('sanctions-content');
        this.gazetteContainer = document.getElementById('gazette-content');
        this.propertyContainer = document.getElementById('property-content');
        this.foodContainer = document.getElementById('food-content');
        this.cqcContainer = document.getElementById('cqc-content');
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
            companies: this.searchOptions.companies?.checked ?? true,
            vehicles: this.searchOptions.vehicles?.checked ?? true,
            legal: this.searchOptions.legal?.checked ?? true,
            contracts: this.searchOptions.contracts?.checked ?? true,
            charities: this.searchOptions.charities?.checked ?? true,
            fca: this.searchOptions.fca?.checked ?? true,
            dvla: this.searchOptions.dvla?.checked ?? true,
            electoral: this.searchOptions.electoral?.checked ?? true,
            police: this.searchOptions.police?.checked ?? false,
            // New sources
            insolvency: this.searchOptions.insolvency?.checked ?? true,
            disqualified: this.searchOptions.disqualified?.checked ?? true,
            land_registry: this.searchOptions.landRegistry?.checked ?? false,
            sanctions: this.searchOptions.sanctions?.checked ?? true,
            food: this.searchOptions.food?.checked ?? false,
            gazette: this.searchOptions.gazette?.checked ?? true,
            cqc: this.searchOptions.cqc?.checked ?? false,
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
        this.updateTabCount('charities', data.charities.length);
        this.updateTabCount('fca', data.fca_firms.length + data.fca_individuals.length);
        this.updateTabCount('donations', data.donations.length);
        this.updateTabCount('crimes', data.crimes.length);
        this.updateTabCount('correlations', data.correlations.length);
        // New tabs
        this.updateTabCount('insolvency', data.insolvency_records?.length || 0);
        this.updateTabCount('disqualified', data.disqualified_directors?.length || 0);
        this.updateTabCount('sanctions', data.sanctioned_entities?.length || 0);
        this.updateTabCount('gazette', data.gazette_notices?.length || 0);
        this.updateTabCount('property', data.property_transactions?.length || 0);
        this.updateTabCount('food', data.food_establishments?.length || 0);
        this.updateTabCount('cqc', data.cqc_locations?.length || 0);

        // Render each section
        this.renderCompanies(data.companies);
        this.renderOfficers(data.officers);
        this.renderVehicles(data.vehicles);
        this.renderLegalCases(data.legal_cases);
        this.renderContracts(data.contracts);
        this.renderCharities(data.charities);
        this.renderFCA(data.fca_firms, data.fca_individuals);
        this.renderDonations(data.donations);
        this.renderCrimes(data.crimes);
        this.renderCorrelations(data.correlations);
        // New renders
        this.renderInsolvency(data.insolvency_records || []);
        this.renderDisqualified(data.disqualified_directors || []);
        this.renderSanctions(data.sanctioned_entities || []);
        this.renderGazette(data.gazette_notices || []);
        this.renderProperty(data.property_transactions || []);
        this.renderFood(data.food_establishments || []);
        this.renderCQC(data.cqc_locations || []);

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
        const tabOrder = [
            'companies', 'officers', 'insolvency', 'disqualified', 'sanctions', 'gazette',
            'legal', 'charities', 'fca', 'contracts', 'donations',
            'vehicles', 'property', 'food', 'cqc', 'crimes', 'correlations'
        ];
        const counts = {
            companies: data.companies.length,
            officers: data.officers.length,
            vehicles: data.vehicles.length,
            legal: data.legal_cases.length,
            contracts: data.contracts.length,
            charities: data.charities.length,
            fca: data.fca_firms.length + data.fca_individuals.length,
            donations: data.donations.length,
            crimes: data.crimes.length,
            correlations: data.correlations.length,
            insolvency: data.insolvency_records?.length || 0,
            disqualified: data.disqualified_directors?.length || 0,
            sanctions: data.sanctioned_entities?.length || 0,
            gazette: data.gazette_notices?.length || 0,
            property: data.property_transactions?.length || 0,
            food: data.food_establishments?.length || 0,
            cqc: data.cqc_locations?.length || 0,
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

    renderInsolvency(records) {
        if (!records.length) {
            this.insolvencyContainer.innerHTML = this.emptyState('No insolvency records found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Status</th>
                        <th>Court</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    ${records.map(r => `
                        <tr>
                            <td><strong>${this.escapeHtml(r.forenames || '')} ${this.escapeHtml(r.surname)}</strong></td>
                            <td><span class="badge badge-warning">${r.case_type || '-'}</span></td>
                            <td>${r.status || '-'}</td>
                            <td>${this.escapeHtml(r.court) || '-'}</td>
                            <td>${this.formatDate(r.start_date)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.insolvencyContainer.innerHTML = html;
    }

    renderDisqualified(directors) {
        if (!directors.length) {
            this.disqualifiedContainer.innerHTML = this.emptyState('No disqualified directors found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>From</th>
                        <th>Until</th>
                        <th>Reason</th>
                        <th>Companies</th>
                    </tr>
                </thead>
                <tbody>
                    ${directors.map(d => `
                        <tr>
                            <td><strong>${this.escapeHtml(d.name)}</strong></td>
                            <td>${this.formatDate(d.disqualified_from)}</td>
                            <td>${this.formatDate(d.disqualified_until)}</td>
                            <td>${this.escapeHtml(d.reason) || '-'}</td>
                            <td>${(d.company_names || []).slice(0, 2).join(', ') || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.disqualifiedContainer.innerHTML = html;
    }

    renderSanctions(entities) {
        if (!entities.length) {
            this.sanctionsContainer.innerHTML = this.emptyState('No sanctioned entities found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Regime</th>
                        <th>Nationality</th>
                        <th>Aliases</th>
                    </tr>
                </thead>
                <tbody>
                    ${entities.map(e => `
                        <tr class="sanctions-row">
                            <td><strong>${this.escapeHtml(e.name)}</strong></td>
                            <td><span class="badge badge-danger">${e.entity_type || '-'}</span></td>
                            <td>${this.escapeHtml(e.regime) || '-'}</td>
                            <td>${this.escapeHtml(e.nationality) || '-'}</td>
                            <td>${(e.aliases || []).slice(0, 2).join(', ') || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.sanctionsContainer.innerHTML = html;
    }

    renderGazette(notices) {
        if (!notices.length) {
            this.gazetteContainer.innerHTML = this.emptyState('No gazette notices found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Type</th>
                        <th>Published</th>
                        <th>Link</th>
                    </tr>
                </thead>
                <tbody>
                    ${notices.map(n => `
                        <tr>
                            <td class="truncate" style="max-width: 400px">${this.escapeHtml(n.title)}</td>
                            <td><span class="badge badge-info">${n.notice_type || '-'}</span></td>
                            <td>${this.formatDate(n.publication_date)}</td>
                            <td>
                                ${n.notice_url
                                    ? `<a href="${n.notice_url}" target="_blank" class="clickable">View</a>`
                                    : '-'
                                }
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.gazetteContainer.innerHTML = html;
    }

    renderProperty(transactions) {
        if (!transactions.length) {
            this.propertyContainer.innerHTML = this.emptyState('No property transactions found (try a UK postcode)');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Address</th>
                        <th>Price</th>
                        <th>Type</th>
                        <th>Tenure</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    ${transactions.map(t => `
                        <tr>
                            <td class="truncate" style="max-width: 300px">${this.escapeHtml(t.full_address)}</td>
                            <td><strong>${this.formatCurrency(t.price)}</strong></td>
                            <td>${t.property_type_name || t.property_type || '-'}</td>
                            <td>${t.tenure_name || t.tenure || '-'}</td>
                            <td>${this.formatDate(t.transaction_date)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.propertyContainer.innerHTML = html;
    }

    renderFood(establishments) {
        if (!establishments.length) {
            this.foodContainer.innerHTML = this.emptyState('No food establishments found');
            return;
        }

        const html = `
            <div class="card-grid">
                ${establishments.map(e => this.foodCard(e)).join('')}
            </div>
        `;
        this.foodContainer.innerHTML = html;
    }

    foodCard(establishment) {
        const rating = establishment.rating_value || 'N/A';
        let ratingClass = 'badge-info';
        if (rating === '5') ratingClass = 'badge-success';
        else if (rating === '4') ratingClass = 'badge-success';
        else if (rating === '3') ratingClass = 'badge-warning';
        else if (rating === '2' || rating === '1' || rating === '0') ratingClass = 'badge-danger';

        return `
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title truncate">${this.escapeHtml(establishment.business_name)}</div>
                        <div class="card-subtitle">${establishment.business_type || '-'}</div>
                    </div>
                    <span class="badge ${ratingClass}">Rating: ${rating}</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">Address</span>
                        <span class="card-value truncate">${this.escapeHtml(establishment.address_line_1 || '')} ${establishment.postcode || ''}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Hygiene</span>
                        <span class="card-value">${establishment.hygiene_score ?? '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Structural</span>
                        <span class="card-value">${establishment.structural_score ?? '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Inspected</span>
                        <span class="card-value">${this.formatDate(establishment.rating_date)}</span>
                    </div>
                </div>
            </div>
        `;
    }

    renderCQC(locations) {
        if (!locations.length) {
            this.cqcContainer.innerHTML = this.emptyState('No CQC registered providers found');
            return;
        }

        const html = `
            <div class="card-grid">
                ${locations.map(l => this.cqcCard(l)).join('')}
            </div>
        `;
        this.cqcContainer.innerHTML = html;
    }

    cqcCard(location) {
        const rating = location.overall_rating || 'Not rated';
        let ratingClass = 'badge-info';
        if (rating === 'Outstanding') ratingClass = 'badge-success';
        else if (rating === 'Good') ratingClass = 'badge-success';
        else if (rating === 'Requires improvement') ratingClass = 'badge-warning';
        else if (rating === 'Inadequate') ratingClass = 'badge-danger';

        return `
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title truncate">${this.escapeHtml(location.name)}</div>
                        <div class="card-subtitle">${location.location_type || '-'}</div>
                    </div>
                    <span class="badge ${ratingClass}">${rating}</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">Provider</span>
                        <span class="card-value truncate">${this.escapeHtml(location.provider_name) || '-'}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Address</span>
                        <span class="card-value truncate">${this.escapeHtml(location.town || '')} ${location.postcode || ''}</span>
                    </div>
                    ${location.number_of_beds ? `
                    <div class="card-row">
                        <span class="card-label">Beds</span>
                        <span class="card-value">${location.number_of_beds}</span>
                    </div>
                    ` : ''}
                    <div class="card-row">
                        <span class="card-label">Inspected</span>
                        <span class="card-value">${this.formatDate(location.report_date)}</span>
                    </div>
                </div>
            </div>
        `;
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

    renderCharities(charities) {
        if (!charities.length) {
            this.charitiesContainer.innerHTML = this.emptyState('No charities found');
            return;
        }

        const html = `
            <div class="card-grid">
                ${charities.map(c => this.charityCard(c)).join('')}
            </div>
        `;
        this.charitiesContainer.innerHTML = html;
    }

    charityCard(charity) {
        const status = charity.charity_status || 'Unknown';
        const statusClass = status.toLowerCase() === 'registered' ? 'badge-success' : 'badge-warning';

        return `
            <div class="card">
                <div class="card-header">
                    <div>
                        <div class="card-title truncate">${this.escapeHtml(charity.charity_name)}</div>
                        <div class="card-subtitle">Charity ${charity.charity_number}</div>
                    </div>
                    <span class="badge ${statusClass}">${status}</span>
                </div>
                <div class="card-body">
                    <div class="card-row">
                        <span class="card-label">Registered</span>
                        <span class="card-value">${this.formatDate(charity.registration_date)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Income</span>
                        <span class="card-value">${this.formatCurrency(charity.income)}</span>
                    </div>
                    <div class="card-row">
                        <span class="card-label">Spending</span>
                        <span class="card-value">${this.formatCurrency(charity.spending)}</span>
                    </div>
                    ${charity.activities ? `
                    <div class="card-row">
                        <span class="card-label">Activities</span>
                        <span class="card-value truncate" style="max-width: 200px">${this.escapeHtml(charity.activities)}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
    }

    renderFCA(firms, individuals) {
        const totalCount = firms.length + individuals.length;
        if (!totalCount) {
            this.fcaContainer.innerHTML = this.emptyState('No FCA regulated firms or individuals found');
            return;
        }

        let html = '';

        if (firms.length) {
            html += `
                <h3 style="margin-bottom: 1rem;">Firms (${firms.length})</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>FRN</th>
                            <th>Status</th>
                            <th>Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${firms.map(f => `
                            <tr>
                                <td><strong>${this.escapeHtml(f.firm_name)}</strong></td>
                                <td>${f.frn || '-'}</td>
                                <td>
                                    <span class="badge ${f.status === 'Authorised' ? 'badge-success' : 'badge-warning'}">
                                        ${f.status || '-'}
                                    </span>
                                </td>
                                <td>${this.escapeHtml(f.firm_type) || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        if (individuals.length) {
            html += `
                <h3 style="margin: 1.5rem 0 1rem;">Individuals (${individuals.length})</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>IRN</th>
                            <th>Status</th>
                            <th>Firm</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${individuals.map(i => `
                            <tr>
                                <td><strong>${this.escapeHtml(i.name)}</strong></td>
                                <td>${i.irn || '-'}</td>
                                <td>
                                    <span class="badge ${i.status === 'Active' ? 'badge-success' : 'badge-warning'}">
                                        ${i.status || '-'}
                                    </span>
                                </td>
                                <td>${this.escapeHtml(i.firm_name) || '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        }

        this.fcaContainer.innerHTML = html;
    }

    renderDonations(donations) {
        if (!donations.length) {
            this.donationsContainer.innerHTML = this.emptyState('No political donations found');
            return;
        }

        const html = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Donor</th>
                        <th>Recipient</th>
                        <th>Amount</th>
                        <th>Type</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    ${donations.map(d => `
                        <tr>
                            <td class="clickable" onclick="app.searchQuery('${this.escapeHtml(d.donor_name || '')}')">${this.escapeHtml(d.donor_name)}</td>
                            <td class="clickable" onclick="app.searchQuery('${this.escapeHtml(d.recipient_name || '')}')">${this.escapeHtml(d.recipient_name)}</td>
                            <td><strong>${this.formatCurrency(d.amount)}</strong></td>
                            <td>${d.donation_type || '-'}</td>
                            <td>${this.formatDate(d.received_date || d.accepted_date)}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        this.donationsContainer.innerHTML = html;
    }

    renderCrimes(crimes) {
        if (!crimes.length) {
            this.crimesContainer.innerHTML = this.emptyState('No crime data found (try entering a UK postcode)');
            return;
        }

        // Group by category
        const byCategory = {};
        crimes.forEach(c => {
            const cat = c.category || 'Unknown';
            byCategory[cat] = (byCategory[cat] || 0) + 1;
        });

        const summaryHtml = `
            <div class="crime-summary" style="margin-bottom: 1.5rem; display: flex; flex-wrap: wrap; gap: 0.5rem;">
                ${Object.entries(byCategory).map(([cat, count]) => `
                    <span class="badge badge-info">${cat.replace(/-/g, ' ')}: ${count}</span>
                `).join('')}
            </div>
        `;

        const tableHtml = `
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>Location</th>
                        <th>Month</th>
                        <th>Outcome</th>
                    </tr>
                </thead>
                <tbody>
                    ${crimes.slice(0, 50).map(c => `
                        <tr>
                            <td>${c.category?.replace(/-/g, ' ') || '-'}</td>
                            <td>${this.escapeHtml(c.street_name) || c.location_name || '-'}</td>
                            <td>${c.month || '-'}</td>
                            <td>${c.outcome_status || 'Under investigation'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${crimes.length > 50 ? `<p class="text-muted" style="margin-top: 1rem;">Showing 50 of ${crimes.length} crimes</p>` : ''}
        `;

        this.crimesContainer.innerHTML = summaryHtml + tableHtml;
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
                        ->
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
                    <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">x</button>
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
