document.addEventListener('DOMContentLoaded', function () {
    const dashboard = document.getElementById('dashboard');
    if (!dashboard) return;

    const scanId = dashboard.dataset.scanId;

    fetch(`/api/scan/${scanId}/chart-data`)
        .then(r => r.json())
        .then(data => {
            renderIssuesByQuery(data.issues_by_query);
            renderSeverityBreakdown(data.severity_breakdown);
            renderIssuesByProductType(data.issues_by_product_type);
        })
        .catch(err => console.error('Failed to load chart data:', err));

    function renderIssuesByQuery(data) {
        const ctx = document.getElementById('chart-by-query');
        if (!ctx || !data.labels.length) return;

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Issues',
                    data: data.data,
                    backgroundColor: 'rgba(54, 162, 235, 0.7)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }

    function renderSeverityBreakdown(data) {
        const ctx = document.getElementById('chart-severity');
        if (!ctx) return;

        // Filter out zero values
        const filtered = { labels: [], data: [], colors: [] };
        const colorMap = {
            'required': '#dc3545',
            'conditional': '#ffc107',
            'warning': '#fd7e14',
            'info': '#0dcaf0'
        };
        data.labels.forEach((label, i) => {
            if (data.data[i] > 0) {
                filtered.labels.push(label);
                filtered.data.push(data.data[i]);
                filtered.colors.push(colorMap[label] || '#6c757d');
            }
        });

        if (!filtered.data.length) return;

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: filtered.labels,
                datasets: [{
                    data: filtered.data,
                    backgroundColor: filtered.colors
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12 } }
                }
            }
        });
    }

    function renderIssuesByProductType(data) {
        const ctx = document.getElementById('chart-by-product-type');
        const row = document.getElementById('product-type-chart-row');
        if (!ctx || !data.labels.length) return;

        row.style.display = '';

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Issues',
                    data: data.data,
                    backgroundColor: 'rgba(255, 159, 64, 0.7)',
                    borderColor: 'rgba(255, 159, 64, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 } }
                }
            }
        });
    }
});
