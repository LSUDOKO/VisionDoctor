"""Storage behind one interface: local (SQLite + filesystem) or AWS (DynamoDB + S3)."""

from __future__ import annotations

from functools import lru_cache

from visiondoctor.config import get_settings
from visiondoctor.storage.base import Storage


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    s = get_settings()
    if s.backend == "aws":
        from visiondoctor.storage.aws import AwsStorage

        return AwsStorage(s)
    from visiondoctor.storage.local import LocalStorage

    return LocalStorage(s.state_dir)
