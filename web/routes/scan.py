import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from ..services.aggregation_service import QUERY_METADATA
from ..database import get_db

scan_bp = Blueprint('scan', __name__)


@scan_bp.route('/<int:scan_id>')
def view_results(scan_id):
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        flash('Scan not found.', 'error')
        return redirect(url_for('main.index'))

    results = db.execute(
        'SELECT * FROM scan_results WHERE scan_id = ? ORDER BY total_issues DESC',
        (scan_id,)
    ).fetchall()

    queries_run = json.loads(scan['queries_run'])

    return render_template('results.html',
                           scan=scan,
                           results=results,
                           queries_run=queries_run,
                           payment_status=scan['payment_status'],
                           query_metadata=QUERY_METADATA)


@scan_bp.route('/report/<token>')
def view_results_by_token(token):
    """Permanent access to a scan report via UUID token."""
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE access_token = ?', (token,)).fetchone()
    if not scan:
        flash('Report not found.', 'error')
        return redirect(url_for('main.index'))

    results = db.execute(
        'SELECT * FROM scan_results WHERE scan_id = ? ORDER BY total_issues DESC',
        (scan['id'],)
    ).fetchall()

    queries_run = json.loads(scan['queries_run'])

    return render_template('results.html',
                           scan=scan,
                           results=results,
                           queries_run=queries_run,
                           payment_status=scan['payment_status'],
                           query_metadata=QUERY_METADATA)


@scan_bp.route('/<int:scan_id>/query/<query_name>')
def view_query_detail(scan_id, query_name):
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        flash('Scan not found.', 'error')
        return redirect(url_for('main.index'))

    result = db.execute(
        'SELECT * FROM scan_results WHERE scan_id = ? AND query_name = ?',
        (scan_id, query_name)
    ).fetchone()
    if not result:
        flash('Query result not found.', 'error')
        return redirect(url_for('scan.view_results', scan_id=scan_id))

    issues = json.loads(result['issues_json'])
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('RESULTS_PER_PAGE', 50)
    total_pages = max(1, (len(issues) + per_page - 1) // per_page)
    page = min(page, total_pages)
    start = (page - 1) * per_page
    paginated_issues = issues[start:start + per_page]

    meta = QUERY_METADATA.get(query_name, {})

    return render_template('results_detail.html',
                           scan=scan,
                           result=result,
                           issues=paginated_issues,
                           page=page,
                           total_pages=total_pages,
                           total_issues=len(issues),
                           query_meta=meta)
