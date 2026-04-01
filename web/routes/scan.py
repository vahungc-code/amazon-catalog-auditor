import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from ..services.scan_service import get_available_queries, parse_clr_file, execute_scan
from ..services.aggregation_service import QUERY_METADATA, SEVERITY_GROUPS
from ..database import get_db

scan_bp = Blueprint('scan', __name__)


@scan_bp.route('/options/<upload_id>')
def scan_options(upload_id):
    upload_meta = session.get('upload')
    if not upload_meta or upload_meta.get('upload_id') != upload_id:
        flash('Upload session expired. Please upload again.', 'error')
        return redirect(url_for('main.index'))

    try:
        parser, listings = parse_clr_file(upload_meta['filepath'])
        product_types = sorted(set(
            l.product_type for l in listings if l.product_type
        ))
        queries = get_available_queries()
    except Exception as e:
        flash(f'Error reading file: {e}', 'error')
        return redirect(url_for('main.index'))

    return render_template('scan_options.html',
                           filename=upload_meta['original_filename'],
                           listing_count=len(listings),
                           product_types=product_types,
                           queries=queries,
                           upload_id=upload_id,
                           query_metadata=QUERY_METADATA,
                           severity_groups=SEVERITY_GROUPS)


@scan_bp.route('/run/<upload_id>', methods=['POST'])
def run_scan(upload_id):
    upload_meta = session.get('upload')
    if not upload_meta or upload_meta.get('upload_id') != upload_id:
        flash('Upload session expired. Please upload again.', 'error')
        return redirect(url_for('main.index'))

    selected_queries = request.form.getlist('queries')
    run_all = 'run_all' in request.form or not selected_queries

    try:
        scan_id = execute_scan(
            filepath=upload_meta['filepath'],
            original_filename=upload_meta['original_filename'],
            file_hash=upload_meta['file_hash'],
            selected_queries=None if run_all else selected_queries
        )
    except Exception as e:
        flash(f'Scan failed: {e}', 'error')
        return redirect(url_for('main.index'))

    session.pop('upload', None)
    return redirect(url_for('scan.view_results', scan_id=scan_id))


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
