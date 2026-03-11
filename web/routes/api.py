import io
import csv
import json
from flask import Blueprint, jsonify, request, make_response, current_app
from ..database import get_db
from ..services.aggregation_service import aggregate_skus, get_issue_details, QUERY_METADATA

api_bp = Blueprint('api', __name__)


@api_bp.route('/scan/<int:scan_id>/sku-overview')
def sku_overview(scan_id):
    """Free tier: health score, stat totals, severity bar, SKU summary table."""
    data = aggregate_skus(scan_id)
    if data is None:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify(data)


@api_bp.route('/scan/<int:scan_id>/issue-details')
def issue_details(scan_id):
    """Paid tier: full issue table with friendly labels and column letters."""
    sku_filter = request.args.get('sku', '').strip()
    severity_filter = request.args.get('severity', '').strip()
    query_filter = request.args.get('query', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('RESULTS_PER_PAGE', 50)

    data = get_issue_details(scan_id, sku_filter, severity_filter, query_filter, page, per_page)
    if data is None:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify(data)


@api_bp.route('/scan/<int:scan_id>/payment-status')
def payment_status(scan_id):
    """Check payment status for a scan."""
    db = get_db()
    scan = db.execute('SELECT payment_status FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    return jsonify({'payment_status': scan['payment_status']})


@api_bp.route('/scan/<int:scan_id>/chart-data')
def get_chart_data(scan_id):
    db = get_db()
    rows = db.execute(
        'SELECT query_name, total_issues, affected_skus, issues_json '
        'FROM scan_results WHERE scan_id = ?', (scan_id,)
    ).fetchall()

    if not rows:
        return jsonify({'error': 'Scan not found'}), 404

    issues_by_query = {
        'labels': [QUERY_METADATA.get(r['query_name'], {}).get('label', r['query_name']) for r in rows],
        'data': [r['total_issues'] for r in rows]
    }

    severity_counts = {'required': 0, 'conditional': 0, 'warning': 0, 'info': 0}
    product_type_counts = {}

    for row in rows:
        issues = json.loads(row['issues_json'])
        for issue in issues:
            sev = issue.get('severity', 'info')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

            pt = issue.get('product_type', '')
            if pt and pt not in ('', 'N/A', 'Unknown'):
                product_type_counts[pt] = product_type_counts.get(pt, 0) + 1

    severity_breakdown = {
        'labels': list(severity_counts.keys()),
        'data': list(severity_counts.values())
    }

    product_type_sorted = sorted(
        product_type_counts.items(), key=lambda x: x[1], reverse=True
    )[:15]
    issues_by_product_type = {
        'labels': [pt[0] for pt in product_type_sorted],
        'data': [pt[1] for pt in product_type_sorted]
    }

    return jsonify({
        'issues_by_query': issues_by_query,
        'severity_breakdown': severity_breakdown,
        'issues_by_product_type': issues_by_product_type
    })


@api_bp.route('/scan/<int:scan_id>/search')
def search_issues(scan_id):
    sku_term = request.args.get('sku', '').strip().lower()
    severity_filter = request.args.get('severity', '').strip().lower()
    query_filter = request.args.get('query', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('RESULTS_PER_PAGE', 50)

    db = get_db()
    rows = db.execute(
        'SELECT query_name, issues_json FROM scan_results WHERE scan_id = ?',
        (scan_id,)
    ).fetchall()

    filtered = []
    for row in rows:
        if query_filter and row['query_name'] != query_filter:
            continue
        issues = json.loads(row['issues_json'])
        for issue in issues:
            if sku_term and sku_term not in issue.get('sku', '').lower():
                continue
            if severity_filter and issue.get('severity', '') != severity_filter:
                continue
            issue['_query'] = row['query_name']
            filtered.append(issue)

    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    paginated = filtered[start:start + per_page]

    return jsonify({
        'issues': paginated,
        'total': total,
        'page': page,
        'pages': total_pages
    })


@api_bp.route('/scan/<int:scan_id>/export/json')
def export_json(scan_id):
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404

    # Check payment status — export is a paid feature
    if scan['payment_status'] != 'paid':
        return jsonify({'error': 'Unlock the full report to export results'}), 403

    rows = db.execute(
        'SELECT * FROM scan_results WHERE scan_id = ?', (scan_id,)
    ).fetchall()

    output = {
        'timestamp': scan['created_at'],
        'total_queries': len(rows),
        'total_issues': scan['total_issues'],
        'total_affected_skus': scan['total_affected'],
        'queries': []
    }
    for row in rows:
        output['queries'].append({
            'query_name': row['query_name'],
            'description': row['query_description'],
            'total_issues': row['total_issues'],
            'affected_skus': row['affected_skus'],
            'issues': json.loads(row['issues_json']),
            'metadata': json.loads(row['metadata_json'])
        })

    response = make_response(json.dumps(output, indent=2))
    response.headers['Content-Type'] = 'application/json'
    safe_name = scan['filename'].rsplit('.', 1)[0] if '.' in scan['filename'] else scan['filename']
    response.headers['Content-Disposition'] = f'attachment; filename="{safe_name}_results.json"'
    return response


@api_bp.route('/scan/<int:scan_id>/export/csv')
def export_csv(scan_id):
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404

    # Check payment status — export is a paid feature
    if scan['payment_status'] != 'paid':
        return jsonify({'error': 'Unlock the full report to export results'}), 403

    rows = db.execute(
        'SELECT * FROM scan_results WHERE scan_id = ?', (scan_id,)
    ).fetchall()

    si = io.StringIO()
    fieldnames = ['query', 'row', 'sku', 'field', 'severity', 'details', 'product_type']
    writer = csv.DictWriter(si, fieldnames=fieldnames)
    writer.writeheader()

    for row in rows:
        issues = json.loads(row['issues_json'])
        for issue in issues:
            writer.writerow({
                'query': row['query_name'],
                'row': issue.get('row', ''),
                'sku': issue.get('sku', ''),
                'field': issue.get('field', ''),
                'severity': issue.get('severity', ''),
                'details': issue.get('details', ''),
                'product_type': issue.get('product_type', '')
            })

    response = make_response(si.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    safe_name = scan['filename'].rsplit('.', 1)[0] if '.' in scan['filename'] else scan['filename']
    response.headers['Content-Disposition'] = f'attachment; filename="{safe_name}_results.csv"'
    return response
