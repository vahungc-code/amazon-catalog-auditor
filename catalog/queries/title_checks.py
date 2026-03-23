"""
Title validation queries
"""

from ..query_engine import QueryPlugin


MAX_TITLE_LENGTH = 200
PROHIBITED_TITLE_CHARS = set("!$?_{}^¬¦")


class TitlePolicyViolationsQuery(QueryPlugin):
    """Find titles violating Amazon policy: excessive length or prohibited characters"""

    name = "title-policy-violations"
    description = "Find titles exceeding 200 characters or containing prohibited characters (!$?_{}^¬¦)"

    def execute(self, listings, clr_parser):
        issues = []

        for listing in listings:
            if not listing.title:
                continue

            if len(listing.title) > MAX_TITLE_LENGTH:
                issues.append({
                    'row': listing.row_number,
                    'sku': listing.sku,
                    'field': 'Title',
                    'severity': 'warning',
                    'details': f"Title length {len(listing.title)} exceeds {MAX_TITLE_LENGTH} characters",
                    'product_type': listing.product_type,
                    'violation': 'length',
                    'title': listing.title[:100] + "..."
                })

            found_chars = set(listing.title) & PROHIBITED_TITLE_CHARS
            if found_chars:
                issues.append({
                    'row': listing.row_number,
                    'sku': listing.sku,
                    'field': 'Title',
                    'severity': 'warning',
                    'details': f"Title contains prohibited characters: {', '.join(sorted(found_chars))}",
                    'product_type': listing.product_type,
                    'violation': 'prohibited_chars',
                    'prohibited_chars': list(found_chars)
                })

        return issues
