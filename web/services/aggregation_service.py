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
    'title-prohibited-chars': {
        'label': 'Title Prohibited Characters',
        'description': 'Checks titles specifically for characters Amazon doesn\'t allow, which can prevent title updates from saving.',
        'example': 'e.g. ! $ ? _ { } ^ \u00ac \u00a6',
        'group': 'recommended',
    },
    'rufus-bullets': {
        'label': 'Bullet Point Quality (RUFUS)',
        'description': 'Evaluates bullet points against Amazon\'s RUFUS AI framework \u2014 the engine powering Amazon\'s shopping assistant.',
        'example': 'e.g. feature clarity, benefit language, specificity',
        'group': 'insights',
    },
    'long-titles': {
        'label': 'Title Length Issues',
        'description': 'Flags titles over 200 characters. Long titles are truncated in search results and hurt click-through rate.',
        'example': 'Amazon recommends 80\u2013150 characters',
        'group': 'insights',
    },
    'missing-variations': {
        'label': 'Missing Variation Relationships',
        'description': 'Identifies products that look like they should be variations but aren\'t linked. Splits reviews and misses cross-sell opportunities.',
        'example': 'e.g. same product in 3 sizes listed separately',
        'group': 'insights',
    },
    'new-attributes': {
        'label': 'Unused Template Attributes',
        'description': 'Finds newer Amazon attributes in your product template that haven\'t been filled yet.',
        'example': 'e.g. sustainability features, safety certifications',
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

def compute_health_score(critical_skus, warning_skus, info_skus, total_skus):
    """Compute 0-100 health score based on % of SKUs affected per severity.
    Uses SKU counts (not issue counts) so a SKU with 100 issues
    doesn't tank the score more than a SKU with 1 issue.
    """
    if total_skus == 0:
        return 100
    # Weighted percentage of affected SKUs
    penalty = (
        (critical_skus / total_skus) * 60 +
        (warning_skus / total_skus) * 25 +
        (info_skus / total_skus) * 10
    )
    return max(0, round(100 - penalty))


def health_label(score):
    """Return (label, color) tuple for a health score."""
    if score >= 70:
        return 'Good', '#10B981'
    elif score >= 40:
        return 'Needs Work', '#F59E0B'
    else:
        return 'At Risk', '#EF4444'


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

    # Load SKU names from scan metadata
    sku_names = json.loads(scan['sku_names_json']) if scan['sku_names_json'] else {}

    # Aggregate issues per SKU
    sku_data = {}
    total_critical = 0
    total_warning = 0
    total_info = 0

    for row in rows:
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

    total_skus = scan['total_listings']
    score = compute_health_score(critical_skus, warning_skus, info_skus, total_skus)
    label, color = health_label(score)

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

    headers = json.loads(scan['headers_json']) if scan['headers_json'] else {}
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
            col_letter = column_index_to_letter(headers.get(field_name, 0))

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
