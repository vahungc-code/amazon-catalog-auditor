import io
import csv
import json
from flask import Blueprint, jsonify, request, make_response, current_app
from ..database import get_db
from ..services.aggregation_service import aggregate_skus, get_issue_details, get_sku_issues, QUERY_METADATA

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


@api_bp.route('/scan/<int:scan_id>/sku-issues')
def sku_issues(scan_id):
    """Get issues for a single SKU, grouped by issue type. Paid or free preview for first SKU."""
    sku = request.args.get('sku', '').strip()
    preview = request.args.get('preview', '').strip() == '1'
    if not sku:
        return jsonify({'error': 'Missing sku parameter'}), 400
    data = get_sku_issues(scan_id, sku, allow_preview=preview)
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


@api_bp.route('/scan/<int:scan_id>/send-report-email', methods=['POST'])
def send_report_email_route(scan_id):
    """Send the report link to an email address. Paid scans only."""
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404
    if scan['payment_status'] != 'paid':
        return jsonify({'error': 'Report must be unlocked first'}), 403

    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'error': 'Invalid email address'}), 400

    try:
        from ..services.payment_service import send_report_email
        base_url = current_app.config.get('BASE_URL', '').rstrip('/')
        report_url = f"{base_url}/scan/{scan_id}"
        send_report_email(email, scan_id, report_url)

        # Also save email on the scan if not already set
        if not scan['customer_email']:
            db.execute('UPDATE scans SET customer_email = ? WHERE id = ?', (email, scan_id))
            db.commit()

        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f'Failed to send report email: {type(e).__name__}: {e}')
        return jsonify({'error': f'Failed to send email: {e}'}), 500


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
    from ..services.aggregation_service import column_index_to_letter, QUERY_METADATA

    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404

    # Check payment status — export is a paid feature
    if scan['payment_status'] != 'paid':
        return jsonify({'error': 'Unlock the full report to export results'}), 403

    # Load column headers and SKU names
    headers_raw = json.loads(scan['headers_json']) if scan['headers_json'] else {}
    if isinstance(headers_raw, dict) and 'columns' in headers_raw:
        col_headers = headers_raw['columns']
        field_ids = headers_raw.get('field_ids', {})
    else:
        col_headers = headers_raw if isinstance(headers_raw, dict) else {}
        field_ids = {}

    sku_names = json.loads(scan['sku_names_json']) if scan['sku_names_json'] else {}

    rows = db.execute(
        'SELECT * FROM scan_results WHERE scan_id = ?', (scan_id,)
    ).fetchall()

    # Collect all issues with enriched data
    all_issues = []
    for row in rows:
        query_name = row['query_name']
        meta = QUERY_METADATA.get(query_name, {})
        check_label = meta.get('label', query_name)
        issues = json.loads(row['issues_json'])
        for issue in issues:
            sku = issue.get('sku', '')
            if sku == 'SUMMARY':
                continue
            field_name = issue.get('field', '')
            col_idx = col_headers.get(field_name, 0) or field_ids.get(field_name, 0)
            col_letter = column_index_to_letter(col_idx)
            all_issues.append({
                'severity': issue.get('severity', ''),
                'sku': sku,
                'query': query_name,
                'column': col_letter,
                'attribute': field_name,
                'details': issue.get('details', ''),
            })

    # Sort by SKU, then severity (critical first), then query name
    severity_order = {'critical': 0, 'required': 0, 'warning': 1, 'info': 2}
    all_issues.sort(key=lambda x: (x['sku'], severity_order.get(x['severity'], 9), x['query']))

    si = io.StringIO()
    fieldnames = ['severity', 'sku', 'query', 'column', 'attribute', 'details']
    writer = csv.DictWriter(si, fieldnames=fieldnames)
    writer.writeheader()
    for issue in all_issues:
        writer.writerow(issue)

    response = make_response(si.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    safe_name = scan['filename'].rsplit('.', 1)[0] if '.' in scan['filename'] else scan['filename']
    response.headers['Content-Disposition'] = f'attachment; filename="{safe_name}_results.csv"'
    return response
