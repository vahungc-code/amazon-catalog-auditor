import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..database import get_db

history_bp = Blueprint('history', __name__)


@history_bp.route('/')
def list_scans():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    db = get_db()

    total = db.execute('SELECT COUNT(*) FROM scans').fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)

    scans = db.execute(
        'SELECT * FROM scans ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (per_page, (page - 1) * per_page)
    ).fetchall()

    return render_template('history.html',
                           scans=scans,
                           page=page,
                           total_pages=total_pages)


@history_bp.route('/<int:scan_id>/delete', methods=['POST'])
def delete_scan(scan_id):
    db = get_db()
    db.execute('DELETE FROM scans WHERE id = ?', (scan_id,))
    db.commit()
    flash('Scan deleted.', 'success')
    return redirect(url_for('history.list_scans'))


@history_bp.route('/compare')
def compare_scans():
    id_a = request.args.get('a', type=int)
    id_b = request.args.get('b', type=int)

    if not id_a or not id_b:
        flash('Select two scans to compare.', 'error')
        return redirect(url_for('history.list_scans'))

    db = get_db()
    scan_a = db.execute('SELECT * FROM scans WHERE id = ?', (id_a,)).fetchone()
    scan_b = db.execute('SELECT * FROM scans WHERE id = ?', (id_b,)).fetchone()

    if not scan_a or not scan_b:
        flash('One or both scans not found.', 'error')
        return redirect(url_for('history.list_scans'))

    results_a = {r['query_name']: r for r in
                 db.execute('SELECT * FROM scan_results WHERE scan_id = ?', (id_a,)).fetchall()}
    results_b = {r['query_name']: r for r in
                 db.execute('SELECT * FROM scan_results WHERE scan_id = ?', (id_b,)).fetchall()}

    all_queries = sorted(set(list(results_a.keys()) + list(results_b.keys())))
    comparison = []
    for qname in all_queries:
        ra = results_a.get(qname)
        rb = results_b.get(qname)
        issues_a = ra['total_issues'] if ra else 0
        issues_b = rb['total_issues'] if rb else 0
        comparison.append({
            'query': qname,
            'issues_a': issues_a,
            'issues_b': issues_b,
            'delta': issues_b - issues_a,
        })

    return render_template('compare.html',
                           scan_a=scan_a,
                           scan_b=scan_b,
                           comparison=comparison)
