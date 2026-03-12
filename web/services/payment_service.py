"""
Payment service — Stripe checkout session creation and webhook verification.
"""

import stripe
from flask import current_app, url_for
from ..database import get_db


def create_checkout_session(scan_id):
    """Create a Stripe Checkout Session for a one-time payment tied to a scan.
    Returns the checkout URL or raises an exception.
    """
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

    if not stripe.api_key:
        raise ValueError('Stripe is not configured. Set STRIPE_SECRET_KEY environment variable.')

    amount = current_app.config['STRIPE_PRICE_AMOUNT']
    currency = current_app.config['STRIPE_CURRENCY']

    success_url = url_for('payment.payment_success', scan_id=scan_id, _external=True)
    cancel_url = url_for('payment.payment_cancel', scan_id=scan_id, _external=True)

    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        allow_promotion_codes=True,
        line_items=[{
            'price_data': {
                'currency': currency,
                'unit_amount': amount,
                'product_data': {
                    'name': 'Catalog Audit — Full Report Unlock',
                    'description': f'Unlock full issue details, export, and column references for scan #{scan_id}.',
                },
            },
            'quantity': 1,
        }],
        metadata={
            'scan_id': str(scan_id),
        },
        success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
        cancel_url=cancel_url,
    )

    # Mark scan as pending payment
    db = get_db()
    db.execute(
        "UPDATE scans SET payment_status = 'pending', stripe_session_id = ? WHERE id = ?",
        (session.id, scan_id)
    )
    db.commit()

    return session.url


def handle_checkout_completed(event_data):
    """Process a checkout.session.completed webhook event.
    Marks the scan as paid.
    """
    session_obj = event_data
    scan_id = session_obj.get('metadata', {}).get('scan_id')

    if not scan_id:
        return False

    db = get_db()
    db.execute(
        "UPDATE scans SET payment_status = 'paid', stripe_payment_intent = ? WHERE id = ?",
        (session_obj.get('payment_intent', ''), int(scan_id))
    )
    db.commit()
    return True


def verify_webhook_signature(payload, sig_header):
    """Verify the Stripe webhook signature. Returns the event or raises an error."""
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    if not webhook_secret:
        raise ValueError('Stripe webhook secret not configured.')

    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
