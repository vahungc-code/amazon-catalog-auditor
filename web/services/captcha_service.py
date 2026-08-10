"""Cloudflare Turnstile verification for the intake form.

Server-side check that a form submission carried a valid Turnstile token,
proving it came from the widget (anti-spam). Uses only the standard library so
no extra dependency is needed.

Behaviour:
- **Disabled by default.** If TURNSTILE_SECRET_KEY is unset, verification is
  skipped and every submission passes — the form works with no CAPTCHA.
- **Fail-closed on a real rejection.** If Cloudflare says the token is invalid
  or missing, the submission is rejected.
- **Fail-open on infrastructure errors.** If Cloudflare is unreachable/timeouts,
  we log and allow the submission through, so a Cloudflare hiccup never costs
  you real leads.
"""

import json
import urllib.parse
import urllib.request

from flask import current_app

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def is_enabled():
    """True if Turnstile is configured (both keys present)."""
    cfg = current_app.config
    return bool(cfg.get('TURNSTILE_SITE_KEY') and cfg.get('TURNSTILE_SECRET_KEY'))


def verify(token, remoteip=None):
    """Verify a Turnstile token. Returns True if the submission may proceed."""
    secret = current_app.config.get('TURNSTILE_SECRET_KEY')
    if not secret:
        return True  # CAPTCHA disabled — allow.

    if not token:
        current_app.logger.info('[captcha] Missing Turnstile token — rejecting.')
        return False

    data = {'secret': secret, 'response': token}
    if remoteip:
        data['remoteip'] = remoteip
    payload = urllib.parse.urlencode(data).encode()

    try:
        req = urllib.request.Request(VERIFY_URL, data=payload)
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode())
    except Exception as e:
        # Infrastructure error — fail open so real users aren't blocked.
        current_app.logger.error(f'[captcha] Turnstile verify request failed, allowing: {e}')
        return True

    if result.get('success'):
        return True

    current_app.logger.info(
        f'[captcha] Turnstile rejected submission: {result.get("error-codes")}')
    return False
