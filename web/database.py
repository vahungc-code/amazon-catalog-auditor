import sqlite3
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
    error_message   TEXT
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
        db.commit()
        db.close()
