"""
Aggregation service for health score, SKU summaries, severity mapping,
query metadata, and flat-file column letter computation.
"""

import json
from ..database import get_db

# ---------------------------------------------------------------------------
# Severity mapping: raw issue severity → display tier
# ---------------------------------------------------------------------------
SEVERITY_MAP = {
    'required': 'critical',
    'conditional': 'critical',
    'warning': 'warning',
    'info': 'info',
}

# ---------------------------------------------------------------------------
# Query metadata: slug → human-readable label, description, example, group
# ---------------------------------------------------------------------------
QUERY_METADATA = {
    'missing-attributes': {
        'label': 'Missing Required Attributes',
        'description': 'Fields Amazon requires to list your product. Missing these can suppress your listing or prevent it from appearing in search.',
        'example': 'e.g. product type, brand, item name',
        'group': 'critical',
    },
    'prohibited-chars': {
        'label': 'Prohibited Characters',
        'description': 'Finds listings with characters Amazon flags or rejects in any field. These can cause update errors or listing suppression.',
        'example': 'e.g. HTML tags, excessive punctuation',
        'group': 'critical',
    },
    'missing-any-attributes': {
        'label': 'Missing Recommended Attributes',
        'description': 'Optional fields Amazon strongly recommends. Filling these improves discoverability and conversion rate.',
        'example': 'e.g. color, size, material, target audience',
        'group': 'recommended',
    },
    'product-type-mismatch': {
        'label': 'Product Type Mismatch',
        'description': 'Detects when your product type doesn\'t match your item type keyword. Affects which attributes Amazon expects and how your listing is categorized.',
        'example': 'e.g. SUPPLEMENT listed as BEVERAGE',
        'group': 'recommended',
    },
    'title-policy-violations': {
        'label': 'Title Policy Violations',
        'description': 'Checks titles for policy violations: length over 200 characters, or characters Amazon doesn\'t allow.',
        'example': 'e.g. title too long, contains ! $ ? _ { } ^ ¬ ¦',
        'group': 'recommended',
    },
    'bullets-content-quality': {
        'label': 'Bullets Content Quality',
        'description': 'Evaluates bullet point content quality across length, specificity, and structure.',
        'example': 'e.g. feature clarity, benefit language, specificity',
        'group': 'insights',
    },
    'missing-variations': {
        'label': 'Missing Variation Relationships',
        'description': 'Identifies products that look like they should be variations but aren\'t linked. Splits reviews and misses cross-sell opportunities.',
        'example': 'e.g. same product in 3 sizes listed separately',
        'group': 'insights',
    },
}

# Group ordering for display
SEVERITY_GROUPS = [
    {'key': 'critical', 'label': 'Critical', 'icon': '\U0001f534', 'color': '#EF4444',
     'description': 'Issues that can suppress listings'},
    {'key': 'recommended', 'label': 'Recommended', 'icon': '\U0001f7e1', 'color': '#F59E0B',
     'description': 'Issues that hurt discoverability'},
    {'key': 'insights', 'label': 'Insights', 'icon': '\U0001f535', 'color': '#3B82F6',
     'description': 'Optimization opportunities'},
]


# ---------------------------------------------------------------------------
# Health score computation
# ---------------------------------------------------------------------------

def compute_completeness(missing_field_issues, total_possible):
    """Compute catalog completeness as a percentage.

    missing_field_issues: number of missing attribute issues
        (from missing-attributes + missing-any-attributes queries)
    total_possible: total SKUs × total checkable fields

    Returns 0-100 percentage.
    """
    if total_possible == 0:
        return 100
    filled = total_possible - missing_field_issues
    return max(0, round((filled / total_possible) * 100))


def completeness_label(score):
    """Return (label, color) tuple for a completeness score."""
    if score >= 90:
        return 'Catalog Healthy', '#10B981'
    elif score >= 70:
        return 'Mostly Complete', '#1B75BB'
    elif score >= 50:
        return 'Needs Completion', '#F59E0B'
    else:
        return 'Critically Incomplete', '#EF4444'


# ---------------------------------------------------------------------------
# SKU aggregation
# ---------------------------------------------------------------------------

def aggregate_skus(scan_id):
    """Aggregate all issues by SKU for the given scan. Returns full overview dict."""
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return None

    rows = db.execute(
        'SELECT query_name, issues_json FROM scan_results WHERE scan_id = ?',
        (scan_id,)
    ).fetchall()

    # Load scan metadata
    sku_names = json.loads(scan['sku_names_json']) if scan['sku_names_json'] else {}
    headers_raw = json.loads(scan['headers_json']) if scan['headers_json'] else {}

    # headers_json may be new format {columns, total_possible, ...} or old format (flat dict)
    if isinstance(headers_raw, dict) and 'total_possible' in headers_raw:
        total_possible = headers_raw.get('total_possible', 0)
    else:
        total_possible = 0

    # Check which queries ran — if missing-any-attributes ran, skip missing-attributes
    # because missing-any-attributes already checks required + conditional (superset)
    query_names_run = [row['query_name'] for row in rows]
    has_missing_any = 'missing-any-attributes' in query_names_run
    skip_queries = set()
    if has_missing_any:
        skip_queries.add('missing-attributes')  # avoid double-counting

    # Parse column mappings for column letter lookup
    if isinstance(headers_raw, dict) and 'columns' in headers_raw:
        col_headers = headers_raw['columns']
        field_ids = headers_raw.get('field_ids', {})
    else:
        col_headers = headers_raw if isinstance(headers_raw, dict) else {}
        field_ids = {}

    # Aggregate issues per SKU
    sku_data = {}
    total_critical = 0
    total_warning = 0
    total_info = 0
    missing_field_issues = 0  # count from missing-any-attributes only

    for row in rows:
        query_name = row['query_name']

        # Skip double-counted queries
        if query_name in skip_queries:
            continue

        meta = QUERY_METADATA.get(query_name, {})
        issue_type_label = meta.get('label', query_name)
        issues = json.loads(row['issues_json'])
        for issue in issues:
            sku = issue.get('sku', '')
            if not sku or sku in ('N/A', 'SUMMARY'):
                continue

            mapped = SEVERITY_MAP.get(issue.get('severity', 'info'), 'info')

            if mapped == 'critical':
                total_critical += 1
            elif mapped == 'warning':
                total_warning += 1
            else:
                total_info += 1

            # Count missing fields for completeness score
            if query_name == 'missing-any-attributes':
                missing_field_issues += 1

            if sku not in sku_data:
                sku_data[sku] = {
                    'sku': sku,
                    'product_name': sku_names.get(sku, sku),
                    'critical': 0,
                    'warning': 0,
                    'info': 0,
                }
            sku_data[sku][mapped] += 1

    # Compute per-SKU health status
    for data in sku_data.values():
        if data['critical'] > 0:
            data['health'] = 'At Risk'
            data['health_color'] = '#EF4444'
        elif data['warning'] > 0:
            data['health'] = 'Needs Work'
            data['health_color'] = '#F59E0B'
        elif data['info'] > 0:
            data['health'] = 'Good'
            data['health_color'] = '#10B981'
        else:
            data['health'] = 'Clean'
            data['health_color'] = '#10B981'

    # SKU category counts — total SKUs with each severity (not exclusive)
    critical_skus = sum(1 for d in sku_data.values() if d['critical'] > 0)
    warning_skus = sum(1 for d in sku_data.values() if d['warning'] > 0)
    info_skus = sum(1 for d in sku_data.values() if d['info'] > 0)

    # Completeness score
    score = compute_completeness(missing_field_issues, total_possible)
    label, color = completeness_label(score)

    # Sort SKU table: worst first
    sku_table = sorted(sku_data.values(), key=lambda x: (x['critical'], x['warning'], x['info']), reverse=True)

    return {
        'health_score': score,
        'health_label': label,
        'health_color': color,
        'total_listings': scan['total_listings'],
        'affected_skus': scan['total_affected'],
        'critical_issues': total_critical,
        'total_issues': scan['total_issues'],
        'severity_bar': {
            'critical': total_critical,
            'warning': total_warning,
            'info': total_info,
        },
        'severity_sku_counts': {
            'critical_skus': critical_skus,
            'warning_skus': warning_skus,
            'info_only_skus': info_skus,
        },
        'sku_table': sku_table,
    }


# ---------------------------------------------------------------------------
# Per-SKU issue details (for expandable rows)
# ---------------------------------------------------------------------------

def get_sku_issues(scan_id, sku, allow_preview=False):
    """Get issues for a single SKU, grouped by issue type. Gated behind payment.
    allow_preview=True bypasses the gate for the free preview SKU (first/worst SKU)."""
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return None

    if scan['payment_status'] != 'paid' and not allow_preview:
        return {'locked': True}

    headers_raw = json.loads(scan['headers_json']) if scan['headers_json'] else {}
    if isinstance(headers_raw, dict) and 'columns' in headers_raw:
        col_headers = headers_raw['columns']
        field_ids = headers_raw.get('field_ids', {})
    else:
        col_headers = headers_raw if isinstance(headers_raw, dict) else {}
        field_ids = {}

    # Check skip queries
    rows = db.execute(
        'SELECT query_name, issues_json FROM scan_results WHERE scan_id = ?',
        (scan_id,)
    ).fetchall()

    query_names_run = [row['query_name'] for row in rows]
    has_missing_any = 'missing-any-attributes' in query_names_run
    skip_queries = set()
    if has_missing_any:
        skip_queries.add('missing-attributes')

    issues_by_type = {}
    for row in rows:
        query_name = row['query_name']
        if query_name in skip_queries:
            continue

        meta = QUERY_METADATA.get(query_name, {})
        issue_type_label = meta.get('label', query_name)
        raw_issues = json.loads(row['issues_json'])

        for issue in raw_issues:
            issue_sku = issue.get('sku', '')
            if issue_sku != sku:
                continue

            mapped = SEVERITY_MAP.get(issue.get('severity', 'info'), 'info')
            field_name = issue.get('field', '')
            col_idx = col_headers.get(field_name, 0) or field_ids.get(field_name, 0)
            col_letter = column_index_to_letter(col_idx)

            if issue_type_label not in issues_by_type:
                issues_by_type[issue_type_label] = {
                    'severity': mapped,
                    'issues': [],
                }
            issues_by_type[issue_type_label]['issues'].append({
                'field': field_name,
                'description': issue.get('details', ''),
                'column_letter': col_letter,
            })

    return {'locked': False, 'issues_by_type': issues_by_type}


# ---------------------------------------------------------------------------
# Issue details (for paid tier)
# ---------------------------------------------------------------------------

def get_issue_details(scan_id, sku_filter='', severity_filter='', query_filter='', page=1, per_page=50):
    """Get full issue details with friendly labels and column letters. Gated behind payment."""
    db = get_db()
    scan = db.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
    if not scan:
        return None

    if scan['payment_status'] != 'paid':
        return {'locked': True, 'message': 'Unlock full report to see issue details'}

    headers_raw = json.loads(scan['headers_json']) if scan['headers_json'] else {}
    # Support new format {columns: {...}, field_ids: {...}} and old format (flat dict)
    if isinstance(headers_raw, dict) and 'columns' in headers_raw:
        headers = headers_raw['columns']
        field_ids = headers_raw.get('field_ids', {})
    else:
        headers = headers_raw
        field_ids = {}
    rows = db.execute(
        'SELECT query_name, issues_json FROM scan_results WHERE scan_id = ?',
        (scan_id,)
    ).fetchall()

    issues = []
    for row in rows:
        query_slug = row['query_name']
        meta = QUERY_METADATA.get(query_slug, {})
        raw_issues = json.loads(row['issues_json'])

        if query_filter and query_slug != query_filter:
            continue

        for issue in raw_issues:
            sku = issue.get('sku', '')
            if not sku or sku in ('N/A', 'SUMMARY'):
                continue
            if sku_filter and sku_filter.lower() not in sku.lower():
                continue

            mapped_sev = SEVERITY_MAP.get(issue.get('severity', 'info'), 'info')
            if severity_filter and mapped_sev != severity_filter:
                continue

            field_name = issue.get('field', '')
            # Try Template column headers first, then Data Definitions field IDs
            col_idx = headers.get(field_name, 0) or field_ids.get(field_name, 0)
            col_letter = column_index_to_letter(col_idx)

            issues.append({
                'sku': sku,
                'issue_type': meta.get('label', query_slug),
                'severity': mapped_sev,
                'severity_label': mapped_sev.capitalize(),
                'description': issue.get('details', ''),
                'column_letter': col_letter,
                'column_name': field_name,
                'technical_attribute': field_name,
                'query_slug': query_slug,
            })

    total = len(issues)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    paginated = issues[start:start + per_page]

    return {
        'locked': False,
        'issues': paginated,
        'total': total,
        'page': page,
        'pages': total_pages,
    }


# ---------------------------------------------------------------------------
# Flat-file column letter conversion
# ---------------------------------------------------------------------------

def column_index_to_letter(index):
    """Convert 1-based column index to Excel-style letter (1->A, 26->Z, 27->AA)."""
    if not index or index <= 0:
        return ''
    result = ''
    while index > 0:
        index -= 1
        result = chr(65 + index % 26) + result
        index //= 26
    return result
