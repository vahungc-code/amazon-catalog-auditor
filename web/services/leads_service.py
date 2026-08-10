"""Durable lead capture in Supabase.

Every completed audit copies the seller-profile the user filled out on the
intake form into a Supabase `leads` table. Supabase (managed Postgres) is
durable and gives the team a self-serve CSV export from the Table Editor,
independent of the app's ephemeral SQLite file on Railway.

Design goals:
- **Never break the audit.** All work happens behind a broad try/except; a
  Supabase outage, bad credentials, or a missing dependency logs a warning and
  the audit still completes.
- **Zero-config fallback.** If SUPABASE_URL / SUPABASE_SERVICE_KEY are not set,
  lead capture is silently skipped and the app behaves exactly as before.
"""

from flask import current_app

# Module-level cache so we build the Supabase client once per process, not per
# request. `False` means "not yet initialised"; `None` means "tried and
# unavailable" (don't keep retrying the import/handshake on every audit).
_client = "uninitialised"


def _normalize_url(url):
    """Reduce whatever the user pasted to the bare project origin.

    The Supabase client expects `https://<ref>.supabase.co` with no trailing
    slash and no path. A pasted value with a trailing slash or a `/rest/v1`
    suffix causes PostgREST error PGRST125 ("Invalid path specified in request
    URL"), so we strip everything after the host defensively.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url.strip())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    # No scheme (e.g. "abc.supabase.co/rest/v1") — keep just the host segment.
    return 'https://' + url.strip().lstrip('/').split('/')[0]


def _get_client():
    global _client
    if _client != "uninitialised":
        return _client

    url = current_app.config.get('SUPABASE_URL')
    key = current_app.config.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        current_app.logger.info(
            '[leads] Supabase not configured (SUPABASE_URL / SUPABASE_SERVICE_KEY '
            'unset) — lead capture disabled.')
        _client = None
        return None

    url = _normalize_url(url)

    try:
        from supabase import create_client
        _client = create_client(url, key)
        current_app.logger.info(f'[leads] Supabase client initialised for {url}.')
    except Exception as e:
        current_app.logger.error(f'[leads] Could not initialise Supabase client: {e}')
        _client = None

    return _client


def record_lead(profile, scan_id=None, filename=None):
    """Insert one lead into the Supabase `leads` table.

    Safe to call unconditionally: returns quietly if Supabase is not configured
    or if anything goes wrong. `profile` is the dict built by the intake form
    (full_name, email, country, role, category, marketplaces, revenue).
    """
    if not profile:
        return

    client = _get_client()
    if client is None:
        return

    marketplaces = profile.get('marketplaces') or []
    if isinstance(marketplaces, (list, tuple)):
        marketplaces = ', '.join(marketplaces)

    row = {
        'scan_id': scan_id,
        'full_name': profile.get('full_name') or None,
        'email': (profile.get('email') or '').lower() or None,
        'country': profile.get('country') or None,
        'role': profile.get('role') or None,
        'category': profile.get('category') or None,
        'marketplaces': marketplaces or None,
        'revenue': profile.get('revenue') or None,
        'filename': filename or None,
        'source': 'catalog-auditor',
    }

    try:
        table = current_app.config.get('SUPABASE_LEADS_TABLE', 'leads')
        client.table(table).insert(row).execute()
        current_app.logger.info(
            f'[leads] Recorded lead for {row["email"]} (scan_id={scan_id}).')
    except Exception as e:
        # Never let a lead-capture failure affect the audit result.
        current_app.logger.error(f'[leads] Failed to record lead (scan_id={scan_id}): {e}')
