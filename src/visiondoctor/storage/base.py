"""Document-store interface shared by local and AWS backends.

Tables mirror docs/02 §4: cameras(pk=camera_id), health_reports(pk=camera_id, sk=ts),
incidents(pk=incident_id), traces(pk=trace_id), approvals(pk=approval_id), profiles(pk=camera_id).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

TABLES = ("cameras", "health_reports", "incidents", "traces", "approvals", "profiles", "tickets")


class Storage(ABC):
    @abstractmethod
    def put(self, table: str, pk: str, doc: dict[str, Any], sk: str = "") -> None: ...

    @abstractmethod
    def get(self, table: str, pk: str, sk: str = "") -> dict[str, Any] | None: ...

    @abstractmethod
    def query(self, table: str, pk: str | None = None, limit: int = 1000, newest_first: bool = True) -> list[dict[str, Any]]:
        """All docs in ``table`` (optionally for one pk), ordered by sk."""

    @abstractmethod
    def delete(self, table: str, pk: str, sk: str = "") -> None: ...

    @abstractmethod
    def put_blob(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        """Store bytes; return the key."""

    @abstractmethod
    def get_blob(self, key: str) -> bytes | None: ...

    @abstractmethod
    def blob_url(self, key: str, expires_s: int = 300) -> str: ...
