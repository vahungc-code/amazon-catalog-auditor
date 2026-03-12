import json
from catalog.parser import CLRParser
from catalog.query_engine import QueryEngine
from catalog.queries import (
    MissingAttributesQuery,
    MissingAnyAttributesQuery,
    LongTitlesQuery,
    TitleProhibitedCharsQuery,
    RufusBulletsQuery,
    ProhibitedCharsQuery,
    ProductTypeMismatchQuery,
    MissingVariationsQuery,
    NewAttributesQuery,
)
from ..database import get_db

ALL_QUERY_CLASSES = [
    MissingAttributesQuery,
    MissingAnyAttributesQuery,
    LongTitlesQuery,
    TitleProhibitedCharsQuery,
    RufusBulletsQuery,
    ProhibitedCharsQuery,
    ProductTypeMismatchQuery,
    MissingVariationsQuery,
    NewAttributesQuery,
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

    # Get the true total listing count (no filtering) so the dashboard is accurate
    all_listings = parser.get_listings(skip_parents=False, skip_examples=True, skip_fbm_duplicates=False)
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

    # Use the filtered listing count (the ones queries actually run on)
    scanned_listings = parser.get_listings()
    total_possible = len(scanned_listings) * total_checkable_fields

    headers_data = {
        'columns': parser.headers,
        'total_checkable_fields': total_checkable_fields,
        'total_possible': total_possible,
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
            if sku:
                all_affected_skus.add(sku)
    total_affected = len(all_affected_skus)

    cursor = db.execute(
        """INSERT INTO scans
           (filename, file_hash, total_listings, total_issues,
            total_affected, queries_run, status, headers_json, sku_names_json)
           VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?)""",
        (original_filename, file_hash, total_listings,
         total_issues, total_affected, json.dumps(queries_run),
         headers_json, sku_names_json)
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
