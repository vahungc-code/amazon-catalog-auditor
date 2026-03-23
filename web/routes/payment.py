"""
Payment routes — Stripe checkout creation, success/cancel redirects, and webhook.
"""

from flask import Blueprint, jsonify, redirect, url_for, flash, request, current_app
from ..database import get_db
from ..services.payment_service import (
    create_checkout_session,
    handle_checkout_completed,
    verify_webhook_signature,
)

payment_bp = Blueprint('payment', __name__)


@payment_bp.route('/scan/<int:scan_id>/create-checkout', methods=['POST'])
def create_checkout(scan_id):
    """Create a Stripe Checkout Session and return the URL."""
    db = get_db()
    scan = db.execute('SELECT id, payment_status FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return jsonify({'error': 'Scan not found'}), 404

    if scan['payment_status'] == 'paid':
        return jsonify({'error': 'This scan is already unlocked.'}), 400

    try:
        checkout_url = create_checkout_session(scan_id)
        return jsonify({'url': checkout_url})
    except ValueError as e:
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        current_app.logger.error(f'Stripe checkout error: {e}')
        return jsonify({'error': 'Failed to create checkout session.'}), 500


@payment_bp.route('/scan/<int:scan_id>/success')
def payment_success(scan_id):
    """Post-payment redirect from Stripe. Redirects to results page."""
    flash('Payment successful! Your full report is now unlocked.', 'success')
    return redirect(url_for('scan.view_results', scan_id=scan_id, check_payment='1'))


@payment_bp.route('/scan/<int:scan_id>/cancel')
def payment_cancel(scan_id):
    """Payment cancelled. Redirect back to results page."""
    flash('Payment was cancelled. You can unlock your report anytime.', 'info')
    return redirect(url_for('scan.view_results', scan_id=scan_id))


@payment_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Stripe webhook endpoint. Processes checkout.session.completed events."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    if not sig_header:
        return jsonify({'error': 'Missing signature'}), 400

    try:
        event = verify_webhook_signature(payload, sig_header)
    except ValueError:
        return jsonify({'error': 'Invalid payload'}), 400
    except Exception as e:
        current_app.logger.error(f'Webhook signature verification failed: {e}')
        return jsonify({'error': 'Signature verification failed'}), 400

    current_app.logger.info(f'[webhook] Received event type: {event["type"]}')

    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        success = handle_checkout_completed(session_data)
        if not success:
            current_app.logger.warning('[webhook] Could not find scan_id in session metadata')
            return jsonify({'error': 'No scan_id in metadata'}), 400
    else:
        current_app.logger.info(f'[webhook] Ignoring event type: {event["type"]}')

    return jsonify({'status': 'ok'}), 200
