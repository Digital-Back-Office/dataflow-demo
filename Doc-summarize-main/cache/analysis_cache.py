"""
SQLite Analysis Cache
Stores pre-computed analysis results so features load instantly when switching documents.
"""

import os
import json
import sqlite3
import hashlib
from typing import Optional, Dict, Any


class AnalysisCache:
    """Persistent SQLite cache for document analysis results."""

    def __init__(self, db_path: str = "data/analysis_cache.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    doc_name   TEXT NOT NULL,
                    feature    TEXT NOT NULL,
                    result     TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    PRIMARY KEY (doc_name, feature)
                )
            """)

    @staticmethod
    def _hash_content(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def get(self, doc_name: str, feature: str, content_hash: str) -> Optional[Any]:
        """Return cached result if it exists and content hash matches."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT result, content_hash FROM analysis_cache WHERE doc_name = ? AND feature = ?",
                (doc_name, feature),
            ).fetchone()
        if row and row[1] == content_hash:
            return json.loads(row[0])
        return None

    def put(self, doc_name: str, feature: str, result: Any, content_hash: str):
        """Insert or replace a cached result."""
        with self._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO analysis_cache (doc_name, feature, result, content_hash) VALUES (?, ?, ?, ?)",
                (doc_name, feature, json.dumps(result, ensure_ascii=False), content_hash),
            )

    def delete_doc(self, doc_name: str):
        """Remove all cached results for a document."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM analysis_cache WHERE doc_name = ?", (doc_name,))

    def clear(self):
        """Clear entire cache."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM analysis_cache")
