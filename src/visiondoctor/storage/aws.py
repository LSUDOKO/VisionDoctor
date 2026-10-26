"""AWS backend: DynamoDB (one table per entity, pk/sk strings) + S3 (SSE, presigned URLs)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import boto3
from botocore.config import Config
from boto3.dynamodb.conditions import Key

from visiondoctor.config import Settings
from visiondoctor.storage.base import Storage


def _to_ddb(doc: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(doc, default=str), parse_float=Decimal)  # type: ignore[no-any-return]


def _from_ddb(item: dict[str, Any]) -> dict[str, Any]:
    def conv(v: Any) -> Any:
        if isinstance(v, Decimal):
            return int(v) if v == v.to_integral_value() else float(v)
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v

    out = conv(item)
    out.pop("pk", None)
    out.pop("sk", None)
    return out  # type: ignore[no-any-return]


class AwsStorage(Storage):
    def __init__(self, s: Settings) -> None:
        if not s.s3_bucket:
            raise ValueError("VD_S3_BUCKET is required for VD_BACKEND=aws")
        self.bucket = s.s3_bucket
        self.prefix = s.ddb_prefix
        self.ddb = boto3.resource("dynamodb", region_name=s.aws_region)
        # Regional endpoint + SigV4: presigned URLs for new buckets otherwise get a 307 redirect
        # to the regional host and the signature no longer matches (403).
        self.s3 = boto3.client(
            "s3", region_name=s.aws_region, endpoint_url=f"https://s3.{s.aws_region}.amazonaws.com",
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
        self._tables: dict[str, Any] = {}

    def _t(self, table: str) -> Any:
        if table not in self._tables:
            self._tables[table] = self.ddb.Table(f"{self.prefix}-{table}")
        return self._tables[table]

    def put(self, table: str, pk: str, doc: dict[str, Any], sk: str = "") -> None:
        item = _to_ddb(doc) | {"pk": pk, "sk": sk or "_"}
        if table == "health_reports":
            import time

            item["ttl"] = int(time.time()) + 30 * 86400
        self._t(table).put_item(Item=item)

    def get(self, table: str, pk: str, sk: str = "") -> dict[str, Any] | None:
        r = self._t(table).get_item(Key={"pk": pk, "sk": sk or "_"})
        return _from_ddb(r["Item"]) if "Item" in r else None

    def query(self, table: str, pk: str | None = None, limit: int = 1000, newest_first: bool = True) -> list[dict[str, Any]]:
        t = self._t(table)
        if pk is not None:
            r = t.query(KeyConditionExpression=Key("pk").eq(pk), ScanIndexForward=not newest_first, Limit=limit)
            items = r["Items"]
        else:
            items, kw = [], {}
            while True:
                r = t.scan(**kw)
                items.extend(r["Items"])
                if "LastEvaluatedKey" not in r or len(items) >= limit:
                    break
                kw = {"ExclusiveStartKey": r["LastEvaluatedKey"]}
            items.sort(key=lambda i: str(i.get("sk", "")), reverse=newest_first)
        return [_from_ddb(i) for i in items[:limit]]

    def delete(self, table: str, pk: str, sk: str = "") -> None:
        self._t(table).delete_item(Key={"pk": pk, "sk": sk or "_"})

    def put_blob(self, key: str, data: bytes, content_type: str = "image/jpeg") -> str:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type, ServerSideEncryption="AES256")
        return key

    def get_blob(self, key: str) -> bytes | None:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()  # type: ignore[no-any-return]
        except self.s3.exceptions.NoSuchKey:
            return None

    def blob_url(self, key: str, expires_s: int = 300) -> str:
        return self.s3.generate_presigned_url(  # type: ignore[no-any-return]
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_s
        )
