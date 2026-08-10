import os
import re
import uuid
import hashlib
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app

from ..intake_options import ROLES, CATEGORIES, MARKETPLACES, REVENUE_BANDS, COUNTRIES
from ..services import captcha_service

main_bp = Blueprint('main', __name__)

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


@main_bp.route('/')
def index():
    return render_template('index.html')


def _render_intake(form):
    """Render the intake form with all shared context (option lists + the
    Turnstile site key). Used both for the initial GET and for re-rendering
    after a validation error."""
    return render_template(
        'intake.html',
        roles=ROLES,
        categories=CATEGORIES,
        marketplaces=MARKETPLACES,
        revenue_bands=REVENUE_BANDS,
        countries=COUNTRIES,
        turnstile_site_key=current_app.config.get('TURNSTILE_SITE_KEY', ''),
        form=form,
    )


@main_bp.route('/get-started')
def get_started():
    """Lead-intake form. Collects seller profile, then the CLR file, and
    submits both together to /upload."""
    return _render_intake({})


def _parse_profile(form):
    """Pull the intake fields off a submitted form and validate them.

    Returns (profile_dict, errors_list). Values are constrained to the known
    option sets so nothing arbitrary lands in the database.
    """
    full_name = form.get('full_name', '').strip()
    email = form.get('email', '').strip().lower()
    country = form.get('country', '').strip()
    role = form.get('role', '').strip()
    category = form.get('category', '').strip()
    marketplaces = [m for m in form.getlist('marketplaces') if m in MARKETPLACES]
    revenue = form.get('revenue', '').strip()

    errors = []
    if not full_name:
        errors.append('Please enter your full name.')
    if not EMAIL_RE.match(email):
        errors.append('Please enter a valid email address.')
    if country not in COUNTRIES:
        errors.append('Please select your country.')
    if role not in ROLES:
        errors.append('Please select your role.')
    if category not in CATEGORIES:
        errors.append('Please select your main selling category.')
    if not marketplaces:
        errors.append('Please select at least one Amazon marketplace.')
    if revenue not in REVENUE_BANDS:
        errors.append('Please select your approximate annual Amazon revenue.')

    profile = {
        'full_name': full_name,
        'email': email,
        'country': country,
        'role': role,
        'category': category,
        'marketplaces': marketplaces,
        'revenue': revenue,
    }
    return profile, errors


@main_bp.route('/find-report', methods=['POST'])
def find_report():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash('Please enter your email address.', 'error')
        return redirect(url_for('main.index'))

    from ..database import get_db
    db = get_db()
    scans = db.execute(
        """SELECT id, filename, created_at, access_token FROM scans
           WHERE LOWER(customer_email) = ? AND payment_status = 'paid'
           ORDER BY created_at DESC""",
        (email,)
    ).fetchall()

    if not scans:
        flash('No paid reports found for that email. Please check the address you used at checkout.', 'error')
        return redirect(url_for('main.index'))

    scan = scans[0]
    if len(scans) > 1:
        flash(f'Found {len(scans)} reports for {email}. Showing the most recent.', 'info')

    # Use token-based URL for permanent access
    if scan['access_token']:
        return redirect(url_for('scan.view_results_by_token', token=scan['access_token']))
    return redirect(url_for('scan.view_results', scan_id=scan['id']))


@main_bp.route('/upload', methods=['POST'])
def upload_file():
    profile, errors = _parse_profile(request.form)

    file = request.files.get('clr_file')
    file_missing = not file or file.filename == ''
    if file_missing:
        errors.append('Please choose a CLR file to upload.')
    elif not allowed_file(file.filename):
        errors.append('Only .xlsx and .xlsm files are supported.')

    # Anti-spam: verify the Turnstile token (no-op if CAPTCHA isn't configured).
    if not captcha_service.verify(request.form.get('cf-turnstile-response')):
        errors.append('CAPTCHA verification failed. Please try again.')

    if errors:
        for err in errors:
            flash(err, 'error')
        # Re-render the form with the values the user already entered.
        return _render_intake(profile), 400

    upload_id = str(uuid.uuid4())
    ext = file.filename.rsplit('.', 1)[1].lower()
    safe_filename = f"{upload_id}.{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], safe_filename)
    file.save(filepath)

    file_hash = compute_sha256(filepath)

    # Run the full audit (all queries) immediately and go straight to results.
    from ..services.scan_service import execute_scan
    try:
        scan_id = execute_scan(
            filepath=filepath,
            original_filename=file.filename,
            file_hash=file_hash,
            selected_queries=None,  # None = run every query
            profile=profile,
        )
    except Exception as e:
        flash(f'We could not read that file: {e}', 'error')
        return _render_intake(profile), 400

    return redirect(url_for('scan.view_results', scan_id=scan_id))
