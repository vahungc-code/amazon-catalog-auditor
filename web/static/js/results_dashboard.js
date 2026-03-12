/**
 * Results Dashboard — Completeness ring, stats, expandable SKU rows, Stripe, payment polling
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

    // ------- Load SKU Overview -------
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

        document.getElementById('health-score').textContent = score + '%';
        document.getElementById('health-score').style.color = color;
        document.getElementById('health-label').textContent = 'Catalog Completeness';

        const fill = document.getElementById('health-fill');
        const circumference = 408.4;
        const offset = circumference - (score / 100) * circumference;
        fill.style.stroke = color;

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

    // ------- SKU Table with expandable rows -------
    // Store SKU data for lazy loading
    let skuList = [];
    const skuIssuesLoaded = {};  // track which SKUs already fetched

    function renderSkuTable(skus) {
        skuList = skus;
        const tbody = document.getElementById('sku-tbody');
        const countEl = document.getElementById('sku-table-count');
        countEl.textContent = `${skus.length} SKUs`;

        if (!skus.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-dim" style="padding: 2rem;">No affected SKUs.</td></tr>';
            return;
        }

        let html = '';
        skus.forEach((s, idx) => {
            const totalIssues = s.critical + s.warning + s.info;
            // Main row
            html += `
            <tr class="sku-row" data-sku-idx="${idx}" onclick="toggleSkuRow(${idx})">
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
                <td class="text-center">
                    <span class="sku-chevron" id="chevron-${idx}">&#8250;</span>
                </td>
            </tr>`;

            // Expandable detail row (content loaded lazily)
            html += `<tr class="sku-detail-row" id="sku-detail-${idx}" style="display: none;">
                <td colspan="7" style="padding: 0; border-bottom: 1px solid var(--border);">
                    <div id="sku-detail-content-${idx}">`;

            if (paymentStatus !== 'paid') {
                // FREE: Blurred preview with lock overlay (rendered immediately)
                html += renderLockedIssues(totalIssues);
            } else {
                // PAID: Show loading placeholder, fetch on expand
                html += '<div class="sku-expand-panel" style="text-align: center; padding: 1.5rem;"><div class="spinner" style="margin: 0 auto;"></div></div>';
            }

            html += `</div></td></tr>`;
        });

        tbody.innerHTML = html;
    }

    // ------- Paid: Render grouped issues -------
    function renderPaidIssues(issuesByType) {
        if (!issuesByType || Object.keys(issuesByType).length === 0) {
            return '<div class="sku-expand-panel"><p class="text-dim" style="padding: 1rem; margin: 0;">No issues found.</p></div>';
        }

        const severityOrder = { critical: 0, warning: 1, info: 2 };
        const sortedTypes = Object.entries(issuesByType).sort((a, b) => {
            return (severityOrder[a[1].severity] ?? 2) - (severityOrder[b[1].severity] ?? 2);
        });

        let html = '<div class="sku-expand-panel">';
        sortedTypes.forEach(([typeName, typeData]) => {
            const sev = typeData.severity;
            const issues = typeData.issues;
            const groupId = 'grp-' + Math.random().toString(36).substr(2, 9);

            html += `
            <div class="issue-group">
                <div class="issue-group-header" onclick="event.stopPropagation(); toggleIssueGroup('${groupId}')">
                    <span class="badge-severity badge-${sev}" style="font-size: 0.65rem;">${sev.toUpperCase()}</span>
                    <span class="issue-group-title">${esc(typeName)}</span>
                    <span class="issue-group-count">${issues.length}</span>
                    <span class="issue-group-chevron" id="chevron-${groupId}">&#8250;</span>
                </div>
                <div class="issue-group-body" id="body-${groupId}">`;

            issues.forEach(issue => {
                html += `
                    <div class="issue-row">
                        <div class="issue-row-left">
                            <div class="issue-field-name">${esc(issue.description || issue.field)}</div>
                            ${issue.field ? `<div class="issue-field-attr">${esc(issue.field)}</div>` : ''}
                        </div>
                        ${issue.column_letter ? `<span class="issue-col-badge">${esc(issue.column_letter)}</span>` : ''}
                    </div>`;
            });

            html += `</div></div>`;
        });

        html += '</div>';
        return html;
    }

    // ------- Free: Blurred locked state -------
    function renderLockedIssues(totalIssues) {
        // Generate fake blurred rows
        let fakeRows = '';
        const fakeFields = ['item_name', 'bullet_point_1', 'brand_name', 'generic_keyword', 'product_description', 'color_name'];
        for (let i = 0; i < Math.min(6, totalIssues); i++) {
            fakeRows += `
                <div class="issue-row">
                    <div class="issue-row-left">
                        <div class="issue-field-name">Missing required field: ${fakeFields[i % fakeFields.length]}</div>
                        <div class="issue-field-attr">${fakeFields[i % fakeFields.length]}</div>
                    </div>
                    <span class="issue-col-badge">C${i + 1}</span>
                </div>`;
        }

        return `
        <div class="sku-expand-panel">
            <div class="sku-locked-wrapper">
                <div class="sku-locked-blur">
                    ${fakeRows}
                </div>
                <div class="sku-locked-overlay">
                    <i class="bi bi-lock-fill" style="font-size: 1.5rem; color: var(--text-dim);"></i>
                    <div class="sku-locked-text">
                        <strong>${totalIssues} issues hidden across this SKU</strong>
                        <p>Unlock to see exact fields, flat file columns, and plain-English descriptions for every issue.</p>
                    </div>
                    <div class="sku-locked-buttons">
                        <button class="btn-accent" onclick="event.stopPropagation(); startCheckout();">
                            <i class="bi bi-unlock"></i> Unlock Full Report
                        </button>
                        <a href="#" class="btn-outline-accent" onclick="event.stopPropagation();">
                            <i class="bi bi-calendar-check"></i> Book a Consultation
                        </a>
                    </div>
                </div>
            </div>
        </div>`;
    }

    // ------- Toggle SKU expandable row -------
    window.toggleSkuRow = function (idx) {
        const detailRow = document.getElementById(`sku-detail-${idx}`);
        const chevron = document.getElementById(`chevron-${idx}`);
        const mainRow = document.querySelector(`tr[data-sku-idx="${idx}"]`);

        if (detailRow.style.display === 'none') {
            detailRow.style.display = 'table-row';
            chevron.classList.add('open');
            mainRow.classList.add('expanded');

            // Lazy-load issues for paid users on first expand
            if (paymentStatus === 'paid' && !skuIssuesLoaded[idx]) {
                skuIssuesLoaded[idx] = true;
                const sku = skuList[idx].sku;
                fetch(`/api/scan/${scanId}/sku-issues?sku=${encodeURIComponent(sku)}`)
                    .then(r => r.json())
                    .then(data => {
                        const container = document.getElementById(`sku-detail-content-${idx}`);
                        if (data.locked) {
                            const totalIssues = skuList[idx].critical + skuList[idx].warning + skuList[idx].info;
                            container.innerHTML = renderLockedIssues(totalIssues);
                        } else {
                            container.innerHTML = renderPaidIssues(data.issues_by_type || {});
                        }
                    })
                    .catch(() => {
                        const container = document.getElementById(`sku-detail-content-${idx}`);
                        container.innerHTML = '<div class="sku-expand-panel"><p class="text-critical" style="padding: 1rem; margin: 0;">Failed to load issues.</p></div>';
                    });
            }
        } else {
            detailRow.style.display = 'none';
            chevron.classList.remove('open');
            mainRow.classList.remove('expanded');
        }
    };

    // ------- Toggle issue group within expanded row -------
    window.toggleIssueGroup = function (groupId) {
        const body = document.getElementById(`body-${groupId}`);
        const chevron = document.getElementById(`chevron-${groupId}`);
        body.classList.toggle('open');
        chevron.classList.toggle('open');
    };

    // ------- CTA Banner -------
    function renderCTA(data) {
        const banner = document.getElementById('cta-banner');
        if (paymentStatus === 'paid') {
            banner.style.display = 'none';
            return;
        }
        const title = document.getElementById('cta-title');
        const subtitle = document.getElementById('cta-subtitle');
        title.textContent = `Your catalog has ${data.critical_issues.toLocaleString()} critical issues across ${data.affected_skus.toLocaleString()} SKUs`;
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

    // ------- Payment polling (if pending) -------
    const hasCheckPayment = new URLSearchParams(window.location.search).get('check_payment');
    if ((paymentStatus === 'pending' || hasCheckPayment) && paymentStatus !== 'paid') {
        let pollCount = 0;
        const pollInterval = setInterval(() => {
            pollCount++;
            fetch(`/api/scan/${scanId}/payment-status`)
                .then(r => r.json())
                .then(data => {
                    if (data.payment_status === 'paid') {
                        clearInterval(pollInterval);
                        window.location.href = window.location.pathname;
                    }
                });
            if (pollCount > 60) clearInterval(pollInterval);
        }, 5000);
    }

    // ------- Utility -------
    function esc(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
});
