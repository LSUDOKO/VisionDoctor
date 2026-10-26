"""Local backend: SQLite documents + files under VD_STATE_DIR (no AWS needed)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from visiondoctor.storage.base import Storage


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(self.root / "visiondoctor.db", check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS docs (tbl TEXT, pk TEXT, sk TEXT, body TEXT, PRIMARY KEY (tbl, pk, sk))"
        )
        self.db.commit()

    def put(self, table: str, pk: str, doc: dict[str, Any], sk: str = "") -> None:
        with self._lock:
            self.db.execute(
                "INSERT OR REPLACE INTO docs VALUES (?,?,?,?)", (table, pk, sk, json.dumps(doc, default=str))
            )
            self.db.commit()

    def get(self, table: str, pk: str, sk: str = "") -> dict[str, Any] | None:
        with self._lock:
            row = self.db.execute("SELECT body FROM docs WHERE tbl=? AND pk=? AND sk=?", (table, pk, sk)).fetchone()
        return json.loads(row[0]) if row else None

    def query(self, table: str, pk: str | None = None, limit: int = 1000, newest_first: bool = True) -> list[dict[str, Any]]:
        order = "DESC" if newest_first else "ASC"
        with self._lock:
            if pk is None:
                rows = self.db.execute(
                    f"SELECT body FROM docs WHERE tbl=? ORDER BY sk {order}, pk LIMIT ?", (table, limit)
                ).fetchall()
            else:
                rows = self.db.execute(
                    f"SELECT body FROM docs WHERE tbl=? AND pk=? ORDER BY sk {order} LIMIT ?", (table, pk, limit)
                ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, table: str, pk: str, sk: str = "") -> None:
        with self._lock:
            self.db.execute("DELETE FROM docs WHERE tbl=? AND pk=? AND sk=?", (table, pk, sk))
            self.db.commit()

    def _path(self, key: str) -> Path:
        p = (self.root / "blobs" / key).resolve()
        if not str(p).startswith(str((self.root / "blobs").resolve())):
            raise ValueError("invalid blob key")
        return p

    def put_blob(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get_blob(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    def blob_url(self, key: str, expires_s: int = 300) -> str:
        return f"/api/blobs/{key}"
