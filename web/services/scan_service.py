import json
import uuid
from catalog.parser import CLRParser
from catalog.query_engine import QueryEngine
from catalog.queries import (
    MissingAttributesQuery,
    MissingAnyAttributesQuery,
    TitlePolicyViolationsQuery,
    ProhibitedCharsQuery,
)
from ..database import get_db

ALL_QUERY_CLASSES = [
    MissingAttributesQuery,
    MissingAnyAttributesQuery,
    TitlePolicyViolationsQuery,
    ProhibitedCharsQuery,
]


def get_available_queries():
    """Return list of {name, description} for all query plugins."""
    queries = []
    for cls in ALL_QUERY_CLASSES:
        instance = cls()
        queries.append({'name': instance.name, 'description': instance.description})
    return queries


def parse_clr_file(filepath):
    """Parse a CLR file and return parser + listings."""
    parser = CLRParser(filepath)
    listings = parser.get_listings()
    return parser, listings


def execute_scan(filepath, original_filename, file_hash, selected_queries=None, include_fbm_duplicates=False):
    """Parse file, run queries, persist results to DB. Returns scan_id."""
    parser = CLRParser(filepath)
    engine = QueryEngine(parser, include_fbm_duplicates=include_fbm_duplicates)

    for cls in ALL_QUERY_CLASSES:
        instance = cls()
        if selected_queries is None or instance.name in selected_queries:
            engine.register_query(instance)

    # Get total active listing count (skip inactive/removed/blank status)
    all_listings = parser.get_listings(skip_parents=False, skip_examples=True,
                                       skip_fbm_duplicates=False, active_only=True)
    total_listings = len(all_listings)

    # Build SKU → title map for product name display
    sku_names = {}
    for listing in all_listings:
        if listing.sku:
            sku_names[listing.sku] = listing.title or listing.sku

    # Serialize parser headers + field counts for completeness score
    # Count total checkable fields (required + conditional from Data Definitions)
    required_fields = parser.get_required_fields()
    conditional_fields = parser.get_conditional_fields()
    total_checkable_fields = len(required_fields) + len(conditional_fields)

    # Use total_listings for the completeness denominator
    # (Don't call parser.get_listings() again — read_only mode exhausts the iterator)
    total_possible = total_listings * total_checkable_fields

    headers_data = {
        'columns': parser.columns,
        'field_ids': parser.field_ids,
        'display_headers': parser.headers,
        'total_checkable_fields': total_checkable_fields,
        'total_possible': total_possible,
        'num_required': len(required_fields),
        'num_conditional': len(conditional_fields),
    }
    headers_json = json.dumps(headers_data)
    sku_names_json = json.dumps(sku_names)

    results = engine.execute_all()

    db = get_db()
    queries_run = [r.query_name for r in results]
    total_issues = sum(r.total_issues for r in results)

    # Count unique affected SKUs across ALL queries (not sum per-query)
    all_affected_skus = set()
    for r in results:
        for issue in r.issues:
            sku = issue.get('sku')
            if sku and sku not in ('N/A', 'SUMMARY'):
                all_affected_skus.add(sku)
    total_affected = len(all_affected_skus)

    access_token = str(uuid.uuid4())

    cursor = db.execute(
        """INSERT INTO scans
           (filename, file_hash, total_listings, total_issues,
            total_affected, queries_run, status, headers_json, sku_names_json,
            access_token)
           VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)""",
        (original_filename, file_hash, total_listings,
         total_issues, total_affected, json.dumps(queries_run),
         headers_json, sku_names_json, access_token)
    )
    scan_id = cursor.lastrowid

    for result in results:
        db.execute(
            """INSERT INTO scan_results
               (scan_id, query_name, query_description, total_issues,
                affected_skus, issues_json, metadata_json, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, result.query_name, result.query_description,
             result.total_issues, result.affected_skus,
             json.dumps(result.issues), json.dumps(result.metadata),
             result.timestamp)
        )

    db.commit()
    return scan_id
