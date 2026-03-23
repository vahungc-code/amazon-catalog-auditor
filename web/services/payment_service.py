"""
Payment service — Stripe checkout session creation, webhook verification,
and post-payment email via SendGrid.
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
        customer_creation='always',
        billing_address_collection='required',
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
    Marks the scan as paid, saves customer email, and sends report link.
    """
    session_obj = event_data
    scan_id = session_obj.get('metadata', {}).get('scan_id')

    if not scan_id:
        return False

    # Extract customer email from Stripe session
    customer_email = (
        session_obj.get('customer_email')
        or session_obj.get('customer_details', {}).get('email', '')
    )

    db = get_db()
    db.execute(
        """UPDATE scans
           SET payment_status = 'paid',
               stripe_payment_intent = ?,
               customer_email = ?
           WHERE id = ?""",
        (session_obj.get('payment_intent', ''), customer_email, int(scan_id))
    )
    db.commit()

    # Send report link email
    if customer_email:
        try:
            base_url = current_app.config.get('BASE_URL', '').rstrip('/')
            report_url = f"{base_url}/scan/{int(scan_id)}"
            current_app.logger.info(f'Sending report email to {customer_email} — {report_url}')
            send_report_email(customer_email, int(scan_id), report_url)
            current_app.logger.info(f'Report email sent successfully to {customer_email}')
        except Exception as e:
            current_app.logger.error(f'Failed to send report email to {customer_email}: {e}')

    return True


def send_report_email(to_email, scan_id, report_url):
    """Send the report link to the customer via SendGrid."""
    api_key = current_app.config.get('SENDGRID_API_KEY', '')
    from_email = current_app.config.get('SENDGRID_FROM_EMAIL', '')

    if not api_key or not from_email:
        current_app.logger.warning('SendGrid not configured — skipping report email.')
        return

    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content

    message = Mail(
        from_email=Email(from_email, 'Catalog Auditor'),
        to_emails=To(to_email),
        subject=f'Your Catalog Audit Report is Ready (Scan #{scan_id})',
    )
    message.dynamic_template_data = {
        'report_url': report_url,
        'scan_id': scan_id,
    }

    # Plain HTML email (no dynamic template required)
    html_content = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 2rem;">
        <h2 style="color: #111; font-size: 1.4rem; margin-bottom: 0.5rem;">Your Full Report is Ready</h2>
        <p style="color: #555; font-size: 0.95rem; line-height: 1.6;">
            Thanks for unlocking your catalog audit. You can access your full report anytime using the link below.
        </p>
        <p style="margin: 1.5rem 0;">
            <a href="{report_url}"
               style="display: inline-block; background: #1B75BB; color: #fff; text-decoration: none;
                      padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: 600; font-size: 0.95rem;">
                View Your Report
            </a>
        </p>
        <p style="color: #888; font-size: 0.8rem; line-height: 1.5;">
            Bookmark this link so you can come back to it anytime.<br>
            Scan #{scan_id} &mdash; Catalog Auditor by Online Seller Solutions
        </p>
    </div>
    """
    message.content = [Content('text/html', html_content)]

    sg = SendGridAPIClient(api_key)
    sg.send(message)


def verify_webhook_signature(payload, sig_header):
    """Verify the Stripe webhook signature. Returns the event or raises an error."""
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    if not webhook_secret:
        raise ValueError('Stripe webhook secret not configured.')

    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
