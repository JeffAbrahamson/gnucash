"""
Sidecar cache management for gcg.

Provides an optional denormalized cache database for faster searches.
The cache is stored separately from the GnuCash book and can be
rebuilt at any time.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class CacheManager:
    """
    Manages the optional sidecar cache database.

    The cache contains denormalized split data for faster searching:
    - Pre-joined split + transaction + account data
    - Precomputed lowercase search fields
    - Optional FTS5 index for fast text search
    """

    SCHEMA_VERSION = 1

    def __init__(self, cache_path: Path, book_path: Path):
        """
        Initialize cache manager.

        Args:
            cache_path: Path to the cache SQLite file
            book_path: Path to the GnuCash book (for tracking changes)
        """
        self.cache_path = Path(cache_path)
        self.book_path = Path(book_path)

    def status(self) -> dict[str, Any]:
        """
        Get cache status information.

        Returns:
            Dictionary with cache status details
        """
        result = {
            "exists": self.cache_path.exists(),
            "path": str(self.cache_path),
        }

        if not self.cache_path.exists():
            return result

        try:
            stat = self.cache_path.stat()
            result["size_bytes"] = stat.st_size
            result["modified"] = datetime.fromtimestamp(
                stat.st_mtime
            ).isoformat()

            # Query cache metadata
            conn = sqlite3.connect(str(self.cache_path))
            cursor = conn.cursor()

            # Get split count
            cursor.execute("SELECT COUNT(*) FROM splits")
            result["split_count"] = cursor.fetchone()[0]

            # Get schema version
            cursor.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            )
            row = cursor.fetchone()
            result["schema_version"] = int(row[0]) if row else None

            # Get source book path
            cursor.execute(
                "SELECT value FROM metadata WHERE key = 'book_path'"
            )
            row = cursor.fetchone()
            result["source_book"] = row[0] if row else None

            # Get build timestamp
            cursor.execute(
                "SELECT value FROM metadata WHERE key = 'build_time'"
            )
            row = cursor.fetchone()
            result["build_time"] = row[0] if row else None

            conn.close()

        except (sqlite3.Error, OSError) as e:
            result["error"] = str(e)

        return result

    def build(self, book, book_info, force: bool = False) -> None:
        """
        Build or rebuild the cache from the GnuCash book.

        Args:
            book: Open piecash Book object
            book_info: BookInfo object with schema information
            force: Force rebuild even if cache exists
        """
        if self.cache_path.exists():
            if not force:
                raise ValueError(
                    f"Cache already exists at {self.cache_path}. "
                    f"Use --force to rebuild."
                )
            self.drop()

        # Create cache directory
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.cache_path))
        cursor = conn.cursor()

        try:
            # Create schema
            self._create_schema(cursor)

            # Populate metadata
            cursor.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                ("schema_version", str(self.SCHEMA_VERSION)),
            )
            cursor.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                ("book_path", str(self.book_path)),
            )
            cursor.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?)",
                ("build_time", datetime.now().isoformat()),
            )

            # Populate splits
            split_count = 0
            for acc in book.accounts:
                if acc.type in ("ROOT", "TRADING"):
                    continue

                for split in acc.splits:
                    tx = split.transaction
                    cursor.execute(
                        """
                        INSERT INTO splits (
                            split_guid, tx_guid, account_guid,
                            tx_date, description, description_lower,
                            account_name, account_name_lower,
                            memo, memo_lower,
                            amount, currency
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            split.guid,
                            tx.guid,
                            acc.guid,
                            tx.post_date.isoformat(),
                            tx.description,
                            tx.description.lower(),
                            acc.fullname,
                            acc.fullname.lower(),
                            split.memo or "",
                            (split.memo or "").lower(),
                            str(split.value),
                            acc.commodity.mnemonic if acc.commodity else "",
                        ),
                    )
                    split_count += 1

            # Create FTS index
            cursor.execute("""
                INSERT INTO splits_fts (
                    split_guid, description, account_name, memo
                )
                SELECT split_guid, description, account_name, memo
                FROM splits
                """)

            conn.commit()

        finally:
            conn.close()

    def drop(self) -> bool:
        """
        Delete the cache file.

        Returns:
            True if cache was deleted, False if it didn't exist
        """
        if self.cache_path.exists():
            os.remove(self.cache_path)
            return True
        return False

    def search(
        self,
        text: str,
        use_fts: bool = True,
        limit: Optional[int] = None,
    ) -> list[dict]:
        """
        Search the cache for matching splits.

        Args:
            text: Search text
            use_fts: Use FTS5 full-text search if available
            limit: Maximum results to return

        Returns:
            List of matching split dictionaries
        """
        if not self.cache_path.exists():
            raise ValueError("Cache does not exist. Run 'gcg cache build'.")

        conn = sqlite3.connect(str(self.cache_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            if use_fts:
                # Use FTS5 for fast search
                query = """
                    SELECT s.*
                    FROM splits s
                    JOIN splits_fts fts ON s.split_guid = fts.split_guid
                    WHERE splits_fts MATCH ?
                    ORDER BY s.tx_date DESC
                """
                params: list = [text]
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                cursor.execute(query, params)
            else:
                # Fall back to LIKE search
                pattern = f"%{text.lower()}%"
                query = """
                    SELECT *
                    FROM splits
                    WHERE description_lower LIKE ?
                       OR memo_lower LIKE ?
                       OR account_name_lower LIKE ?
                    ORDER BY tx_date DESC
                """
                params = [pattern, pattern, pattern]
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def _create_schema(self, cursor: sqlite3.Cursor) -> None:
        """Create the cache database schema."""
        cursor.execute("""
            CREATE TABLE metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """)

        cursor.execute("""
            CREATE TABLE splits (
                split_guid TEXT PRIMARY KEY,
                tx_guid TEXT NOT NULL,
                account_guid TEXT NOT NULL,
                tx_date TEXT NOT NULL,
                description TEXT NOT NULL,
                description_lower TEXT NOT NULL,
                account_name TEXT NOT NULL,
                account_name_lower TEXT NOT NULL,
                memo TEXT,
                memo_lower TEXT,
                amount TEXT NOT NULL,
                currency TEXT
            )
            """)

        # Indexes for common queries
        cursor.execute("CREATE INDEX idx_splits_tx_date ON splits(tx_date)")
        cursor.execute("CREATE INDEX idx_splits_tx_guid ON splits(tx_guid)")
        cursor.execute(
            "CREATE INDEX idx_splits_account ON splits(account_name_lower)"
        )

        # FTS5 virtual table for fast text search
        cursor.execute("""
            CREATE VIRTUAL TABLE splits_fts USING fts5(
                split_guid,
                description,
                account_name,
                memo,
                content='splits',
                content_rowid='rowid'
            )
            """)
