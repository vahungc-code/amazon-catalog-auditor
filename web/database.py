import sqlite3
import uuid
from flask import g, current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_listings  INTEGER NOT NULL DEFAULT 0,
    total_issues    INTEGER NOT NULL DEFAULT 0,
    total_affected  INTEGER NOT NULL DEFAULT 0,
    queries_run     TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'completed',
    error_message   TEXT,
    payment_status  TEXT NOT NULL DEFAULT 'free',
    stripe_session_id TEXT,
    stripe_payment_intent TEXT,
    customer_email  TEXT,
    headers_json    TEXT NOT NULL DEFAULT '{}',
    sku_names_json  TEXT NOT NULL DEFAULT '{}',
    access_token    TEXT
);

CREATE TABLE IF NOT EXISTS scan_results (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id           INTEGER NOT NULL,
    query_name        TEXT NOT NULL,
    query_description TEXT NOT NULL,
    total_issues      INTEGER NOT NULL DEFAULT 0,
    affected_skus     INTEGER NOT NULL DEFAULT 0,
    issues_json       TEXT NOT NULL DEFAULT '[]',
    metadata_json     TEXT NOT NULL DEFAULT '{}',
    timestamp         TEXT,
    FOREIGN KEY (scan_id) REFERENCES scans(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scan_results_scan_id ON scan_results(scan_id);
CREATE INDEX IF NOT EXISTS idx_scans_created_at ON scans(created_at);
"""

MIGRATIONS = [
    "ALTER TABLE scans ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'free'",
    "ALTER TABLE scans ADD COLUMN stripe_session_id TEXT",
    "ALTER TABLE scans ADD COLUMN stripe_payment_intent TEXT",
    "ALTER TABLE scans ADD COLUMN customer_email TEXT",
    "ALTER TABLE scans ADD COLUMN headers_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE scans ADD COLUMN sku_names_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE scans ADD COLUMN access_token TEXT",
]


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE_PATH'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    app.teardown_appcontext(close_db)
    with app.app_context():
        db = sqlite3.connect(app.config['DATABASE_PATH'])
        db.executescript(SCHEMA)
        # Run migrations for existing databases
        for migration in MIGRATIONS:
            try:
                db.execute(migration)
            except sqlite3.OperationalError:
                pass  # Column already exists

        # Create unique index for access_token (safe if already exists)
        try:
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_scans_access_token ON scans(access_token)")
        except sqlite3.OperationalError:
            pass

        # Backfill: generate tokens for any existing scans that lack one
        cursor = db.execute("SELECT id FROM scans WHERE access_token IS NULL")
        for row in cursor.fetchall():
            db.execute("UPDATE scans SET access_token = ? WHERE id = ?",
                       (str(uuid.uuid4()), row[0]))

        db.commit()
        db.close()
