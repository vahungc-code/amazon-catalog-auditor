"""
Dashboard routes — magic-link login + user report dashboard.
Users enter their email, receive a login link, then see all scans
tied to that email in one place.
"""

import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from ..database import get_db

dashboard_bp = Blueprint('dashboard', __name__)

MAGIC_LINK_EXPIRY_MINUTES = 15


def require_dashboard_login(f):
    """Decorator: redirect to login if session has no dashboard_email."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'dashboard_email' not in session:
            flash('Please log in to view your reports.', 'error')
            return redirect(url_for('dashboard.login'))
        return f(*args, **kwargs)
    return decorated


@dashboard_bp.route('/login')
def login():
    """Show the magic-link login form."""
    # If already logged in, go straight to dashboard
    if 'dashboard_email' in session:
        return redirect(url_for('dashboard.my_reports'))
    return render_template('dashboard_login.html')


@dashboard_bp.route('/send-link', methods=['POST'])
def send_link():
    """Create a magic token and email it to the user."""
    email = request.form.get('email', '').strip().lower()
    if not email or '@' not in email:
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('dashboard.login'))

    # Check if any scans exist for this email
    db = get_db()
    scan_count = db.execute(
        "SELECT COUNT(*) FROM scans WHERE LOWER(customer_email) = ?", (email,)
    ).fetchone()[0]

    if scan_count == 0:
        flash('No reports found for that email. Please use the email you entered at checkout.', 'error')
        return redirect(url_for('dashboard.login'))

    # Create magic token
    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES)

    db.execute(
        "INSERT INTO magic_tokens (email, token, expires_at) VALUES (?, ?, ?)",
        (email, token, expires_at)
    )
    db.commit()

    # Send magic link email
    verify_url = url_for('dashboard.verify', token=token, _external=True)
    try:
        from ..services.payment_service import send_magic_link_email
        send_magic_link_email(email, verify_url)
    except Exception as e:
        current_app.logger.error(f'[dashboard] Failed to send magic link to {email}: {e}')
        flash('Failed to send login link. Please try again.', 'error')
        return redirect(url_for('dashboard.login'))

    return render_template('dashboard_check_inbox.html', email=email)


@dashboard_bp.route('/verify/<token>')
def verify(token):
    """Validate magic token, start session, redirect to dashboard."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM magic_tokens WHERE token = ?", (token,)
    ).fetchone()

    if not row:
        flash('Invalid login link. Please request a new one.', 'error')
        return redirect(url_for('dashboard.login'))

    if row['used']:
        flash('This login link has already been used. Please request a new one.', 'error')
        return redirect(url_for('dashboard.login'))

    expires_at = row['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if datetime.utcnow() > expires_at:
        flash('This login link has expired. Please request a new one.', 'error')
        return redirect(url_for('dashboard.login'))

    # Mark token as used
    db.execute("UPDATE magic_tokens SET used = 1 WHERE id = ?", (row['id'],))
    db.commit()

    # Set session
    session['dashboard_email'] = row['email']
    session.permanent = True

    return redirect(url_for('dashboard.my_reports'))


@dashboard_bp.route('/')
@require_dashboard_login
def my_reports():
    """Show all scans for the logged-in user's email."""
    email = session['dashboard_email']
    db = get_db()

    scans = db.execute(
        """SELECT * FROM scans
           WHERE LOWER(customer_email) = ?
           ORDER BY created_at DESC""",
        (email,)
    ).fetchall()

    return render_template('dashboard.html', email=email, scans=scans)


@dashboard_bp.route('/logout')
def logout():
    """Clear dashboard session."""
    session.pop('dashboard_email', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.index'))
