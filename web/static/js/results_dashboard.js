/**
 * Results Dashboard — Tab switching, health score, SKU table, CTA, Stripe, payment polling
 */
document.addEventListener('DOMContentLoaded', function () {
    const app = document.getElementById('results-app');
    if (!app) return;

    const scanId = app.dataset.scanId;
    const paymentStatus = app.dataset.paymentStatus;

    // ------- Initialize Bootstrap tooltips -------
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new bootstrap.Tooltip(el);
    });

    // ------- Tab switching -------
    window.switchTab = function (tab) {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
        document.getElementById(`panel-${tab}`).classList.add('active');

        // Load issue details on first switch (paid only)
        if (tab === 'details' && paymentStatus === 'paid' && !detailsLoaded) {
            loadIssueDetails();
        }
    };

    // ------- Load SKU Overview (free tier) -------
    fetch(`/api/scan/${scanId}/sku-overview`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('overview-loading').style.display = 'none';
            document.getElementById('overview-content').style.display = 'block';
            renderHealthScore(data);
            renderStats(data);
            renderSeverityBar(data.severity_bar);
            renderQuickCounts(data.severity_sku_counts);
            renderSkuTable(data.sku_table);
            renderCTA(data);
        })
        .catch(err => {
            document.getElementById('overview-loading').innerHTML =
                '<p class="text-critical">Failed to load overview data.</p>';
            console.error(err);
        });

    // ------- Completeness Score Ring -------
    function renderHealthScore(data) {
        const score = data.health_score;
        const color = data.health_color;
        const label = data.health_label;

        document.getElementById('health-score').textContent = score + '%';
        document.getElementById('health-score').style.color = color;
        // Static label stays "CATALOG COMPLETENESS"
        document.getElementById('health-label').textContent = 'Catalog Completeness';
        // Dynamic status line — colored to match the ring
        document.getElementById('health-status').textContent = label;
        document.getElementById('health-status').style.color = color;

        const fill = document.getElementById('health-fill');
        const circumference = 408.4; // 2 * PI * 65
        const offset = circumference - (score / 100) * circumference;
        fill.style.stroke = color;

        // Animate after a brief delay
        setTimeout(() => {
            fill.style.strokeDashoffset = offset;
        }, 100);
    }

    // ------- Stat Cards -------
    function renderStats(data) {
        document.getElementById('stat-listings').textContent = data.total_listings.toLocaleString();
        document.getElementById('stat-affected').textContent = data.affected_skus.toLocaleString();
        document.getElementById('stat-critical').textContent = data.critical_issues.toLocaleString();
        document.getElementById('stat-total').textContent = data.total_issues.toLocaleString();
    }

    // ------- Severity Bar -------
    function renderSeverityBar(sev) {
        const total = sev.critical + sev.warning + sev.info;
        const bar = document.getElementById('severity-bar');
        if (total === 0) {
            bar.innerHTML = '<div class="severity-bar-segment info" style="width: 100%;"></div>';
            return;
        }
        bar.innerHTML = `
            <div class="severity-bar-segment critical" style="width: ${(sev.critical / total * 100).toFixed(1)}%"></div>
            <div class="severity-bar-segment warning" style="width: ${(sev.warning / total * 100).toFixed(1)}%"></div>
            <div class="severity-bar-segment info" style="width: ${(sev.info / total * 100).toFixed(1)}%"></div>
        `;
        document.getElementById('sev-critical-count').textContent = sev.critical.toLocaleString();
        document.getElementById('sev-warning-count').textContent = sev.warning.toLocaleString();
        document.getElementById('sev-info-count').textContent = sev.info.toLocaleString();
    }

    // ------- Quick Counts -------
    function renderQuickCounts(counts) {
        document.getElementById('qc-critical').textContent = counts.critical_skus.toLocaleString();
        document.getElementById('qc-warning').textContent = counts.warning_skus.toLocaleString();
        document.getElementById('qc-info').textContent = counts.info_only_skus.toLocaleString();
    }

    // ------- SKU Table -------
    function renderSkuTable(skus) {
        const tbody = document.getElementById('sku-tbody');
        const countEl = document.getElementById('sku-table-count');
        countEl.textContent = `${skus.length} SKUs`;

        if (!skus.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-dim" style="padding: 2rem;">No affected SKUs.</td></tr>';
            return;
        }

        tbody.innerHTML = skus.map(s => `
            <tr>
                <td><code>${esc(s.sku)}</code></td>
                <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                    title="${esc(s.product_name)}">${esc(s.product_name)}</td>
                <td class="text-end">${s.critical > 0 ? `<span class="text-critical">${s.critical}</span>` : '<span class="text-dim">0</span>'}</td>
                <td class="text-end">${s.warning > 0 ? `<span class="text-warning-custom">${s.warning}</span>` : '<span class="text-dim">0</span>'}</td>
                <td class="text-end">${s.info > 0 ? `<span class="text-info-custom">${s.info}</span>` : '<span class="text-dim">0</span>'}</td>
                <td>
                    <span class="sku-health">
                        <span class="sku-health-dot" style="background: ${s.health_color};"></span>
                        ${s.health}
                    </span>
                </td>
            </tr>
        `).join('');
    }

    // ------- CTA Banner -------
    function renderCTA(data) {
        const banner = document.getElementById('cta-banner');
        if (paymentStatus === 'paid') {
            banner.style.display = 'none';
            return;
        }
        const title = document.getElementById('cta-title');
        const subtitle = document.getElementById('cta-subtitle');
        title.textContent = `Your catalog has ${data.critical_issues} critical issues across ${data.affected_skus} SKUs`;
        subtitle.textContent = 'Unlock the full report to see every issue with fix instructions and flat-file column references.';
    }

    // ------- Stripe Checkout -------
    window.startCheckout = function () {
        const btn = document.getElementById('btn-unlock');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:0.5rem;"></span> Redirecting...';
        }
        fetch(`/payment/scan/${scanId}/create-checkout`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.url) {
                    window.location.href = data.url;
                } else {
                    alert(data.error || 'Failed to start checkout.');
                    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-unlock"></i> Unlock Full Report'; }
                }
            })
            .catch(err => {
                alert('Failed to connect to payment service.');
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-unlock"></i> Unlock Full Report'; }
            });
    };

    // ------- Issue Details (paid tier) -------
    let detailsLoaded = false;

    function loadIssueDetails(page) {
        page = page || 1;
        const skuSearch = document.getElementById('detail-sku-search');
        const sevFilter = document.getElementById('detail-severity-filter');
        const queryFilter = document.getElementById('detail-query-filter');

        if (!skuSearch) return; // locked view

        const params = new URLSearchParams({
            sku: skuSearch.value,
            severity: sevFilter.value,
            query: queryFilter.value,
            page: page,
        });

        fetch(`/api/scan/${scanId}/issue-details?${params}`)
            .then(r => r.json())
            .then(data => {
                if (data.locked) return;
                detailsLoaded = true;
                renderDetailRows(data.issues);
                renderDetailPagination(data.page, data.pages, data.total);
            })
            .catch(err => {
                document.getElementById('detail-tbody').innerHTML =
                    '<tr><td colspan="6" class="text-center text-critical" style="padding:2rem;">Failed to load issues.</td></tr>';
            });
    }

    function renderDetailRows(issues) {
        const tbody = document.getElementById('detail-tbody');
        const countEl = document.getElementById('detail-total-count');

        if (!issues || !issues.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-dim" style="padding:2rem;">No issues match your filters.</td></tr>';
            if (countEl) countEl.textContent = '';
            return;
        }

        tbody.innerHTML = issues.map(i => `
            <tr>
                <td><code>${esc(i.sku)}</code></td>
                <td>${esc(i.issue_type)}</td>
                <td><span class="badge-severity badge-${i.severity}">${i.severity_label}</span></td>
                <td style="max-width: 300px;"><small>${esc(i.description)}</small></td>
                <td>${i.column_letter ? `<code>${esc(i.column_letter)}</code>` : '<span class="text-dim">—</span>'}</td>
                <td><small class="text-dim">${esc(i.technical_attribute || '')}</small></td>
            </tr>
        `).join('');
    }

    function renderDetailPagination(currentPage, totalPages, total) {
        const container = document.getElementById('detail-pagination');
        const countEl = document.getElementById('detail-total-count');
        if (countEl) countEl.textContent = `${total} issues`;

        if (!container || totalPages <= 1) {
            if (container) container.innerHTML = `<small class="text-dim">${total} issue${total !== 1 ? 's' : ''}</small>`;
            return;
        }

        let html = `<small class="text-dim">${total} issues</small><ul class="pagination-dark">`;
        html += `<li><a class="page-link-dark ${currentPage <= 1 ? 'disabled' : ''}" data-page="${currentPage - 1}">Prev</a></li>`;

        for (let p = 1; p <= totalPages; p++) {
            if (p <= 3 || p > totalPages - 2 || (p >= currentPage - 1 && p <= currentPage + 1)) {
                html += `<li><a class="page-link-dark ${p === currentPage ? 'active' : ''}" data-page="${p}">${p}</a></li>`;
            } else if (p === 4 || p === totalPages - 2) {
                html += `<li><span class="page-link-dark disabled">...</span></li>`;
            }
        }

        html += `<li><a class="page-link-dark ${currentPage >= totalPages ? 'disabled' : ''}" data-page="${currentPage + 1}">Next</a></li>`;
        html += '</ul>';
        container.innerHTML = html;

        container.querySelectorAll('a[data-page]').forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                const p = parseInt(this.dataset.page);
                if (p >= 1 && p <= totalPages) loadIssueDetails(p);
            });
        });
    }

    // Detail filters
    if (paymentStatus === 'paid') {
        let debounce;
        const skuSearch = document.getElementById('detail-sku-search');
        const sevFilter = document.getElementById('detail-severity-filter');
        const queryFilter = document.getElementById('detail-query-filter');

        if (skuSearch) {
            skuSearch.addEventListener('input', () => {
                clearTimeout(debounce);
                debounce = setTimeout(() => loadIssueDetails(), 300);
            });
        }
        if (sevFilter) sevFilter.addEventListener('change', () => loadIssueDetails());
        if (queryFilter) queryFilter.addEventListener('change', () => loadIssueDetails());

        // Auto-load details if we're on paid view
        loadIssueDetails();
    }

    // ------- Payment polling (if pending) -------
    if (paymentStatus === 'pending' || new URLSearchParams(window.location.search).get('check_payment')) {
        let pollCount = 0;
        const pollInterval = setInterval(() => {
            pollCount++;
            fetch(`/api/scan/${scanId}/payment-status`)
                .then(r => r.json())
                .then(data => {
                    if (data.payment_status === 'paid') {
                        clearInterval(pollInterval);
                        window.location.reload();
                    }
                });
            if (pollCount > 60) clearInterval(pollInterval); // stop after 5 minutes
        }, 5000);
    }

    // ------- Utility -------
    function esc(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
});
