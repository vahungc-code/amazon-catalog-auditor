document.addEventListener('DOMContentLoaded', function () {
    const section = document.getElementById('issues-section');
    if (!section) return;

    const scanId = section.dataset.scanId;
    const tbody = document.getElementById('issues-tbody');
    const pagination = document.getElementById('issues-pagination');
    const skuSearch = document.getElementById('sku-search');
    const severityFilter = document.getElementById('severity-filter');
    const queryFilter = document.getElementById('query-filter');

    let debounceTimer;

    // Initial load
    applyFilters();

    skuSearch.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => applyFilters(), 300);
    });

    severityFilter.addEventListener('change', () => applyFilters());
    queryFilter.addEventListener('change', () => applyFilters());

    function applyFilters(page) {
        page = page || 1;
        const params = new URLSearchParams({
            sku: skuSearch.value,
            severity: severityFilter.value,
            query: queryFilter.value,
            page: page
        });

        fetch(`/api/scan/${scanId}/search?${params}`)
            .then(r => r.json())
            .then(data => {
                renderIssueRows(data.issues);
                renderPagination(data.page, data.pages, data.total);
            })
            .catch(err => {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Failed to load issues.</td></tr>';
            });
    }

    function renderIssueRows(issues) {
        if (!issues.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">No issues match your filters.</td></tr>';
            return;
        }

        const severityBadge = {
            'required': '<span class="badge bg-danger">required</span>',
            'conditional': '<span class="badge bg-warning text-dark">conditional</span>',
            'warning': '<span class="badge severity-warning">warning</span>',
            'info': '<span class="badge bg-info">info</span>'
        };

        tbody.innerHTML = issues.map(issue => `
            <tr>
                <td>${issue.row || ''}</td>
                <td><code>${escapeHtml(issue.sku || '')}</code></td>
                <td><small>${escapeHtml(issue._query || '')}</small></td>
                <td>${escapeHtml(issue.field || '')}</td>
                <td>${severityBadge[issue.severity] || issue.severity || ''}</td>
                <td><small>${escapeHtml(issue.details || '')}</small></td>
            </tr>
        `).join('');
    }

    function renderPagination(currentPage, totalPages, total) {
        if (totalPages <= 1) {
            pagination.innerHTML = `<small class="text-muted">${total} issue${total !== 1 ? 's' : ''}</small>`;
            return;
        }

        let html = `<small class="text-muted">${total} issues</small><nav><ul class="pagination pagination-sm mb-0">`;

        html += `<li class="page-item ${currentPage <= 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" data-page="${currentPage - 1}">Prev</a></li>`;

        for (let p = 1; p <= totalPages; p++) {
            if (p <= 3 || p > totalPages - 2 || (p >= currentPage - 1 && p <= currentPage + 1)) {
                html += `<li class="page-item ${p === currentPage ? 'active' : ''}">
                            <a class="page-link" href="#" data-page="${p}">${p}</a></li>`;
            } else if (p === 4 || p === totalPages - 2) {
                html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
            }
        }

        html += `<li class="page-item ${currentPage >= totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" data-page="${currentPage + 1}">Next</a></li>`;
        html += '</ul></nav>';
        pagination.innerHTML = html;

        pagination.querySelectorAll('a[data-page]').forEach(link => {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                const p = parseInt(this.dataset.page);
                if (p >= 1 && p <= totalPages) applyFilters(p);
            });
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Expose for external use
    window.applyFilters = applyFilters;
});
