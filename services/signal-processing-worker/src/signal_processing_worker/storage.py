from __future__ import annotations

import gzip
import json

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from signal_processing_worker.config import Settings
from signal_processing_worker.errors import NotFoundError


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._raw_bucket = settings.s3_raw_bucket
        self._clean_bucket = settings.s3_clean_bucket
        addressing_style = "path" if settings.s3_force_path_style else "auto"
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": addressing_style}),
        )

    def ensure_clean_bucket(self) -> None:
        self._ensure_bucket(self._clean_bucket)

    def read_raw_text(self, object_key: str) -> str:
        payload = self._read_object(bucket=self._raw_bucket, object_key=object_key)
        if object_key.endswith(".gz") or payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
        return payload.decode("utf-8")

    def write_clean_text(self, object_key: str, text: str, content_type: str, gzip_compress: bool = False) -> None:
        payload = text.encode("utf-8")
        if gzip_compress:
            payload = gzip.compress(payload)
            if "gzip" not in content_type:
                content_type = f"{content_type}; charset=utf-8"
        self.write_clean_bytes(object_key=object_key, payload=payload, content_type=content_type)

    def write_clean_json(self, object_key: str, payload: dict) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        self.write_clean_text(
            object_key=object_key,
            text=serialized,
            content_type="application/json",
            gzip_compress=False,
        )

    def write_clean_bytes(self, object_key: str, payload: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._clean_bucket,
            Key=object_key,
            Body=payload,
            ContentType=content_type,
        )

    def _read_object(self, bucket: str, object_key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=bucket, Key=object_key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey"}:
                raise NotFoundError(
                    code="processing_object_missing",
                    message="Object is missing in object storage",
                    details={"bucket": bucket, "object_key": object_key},
                ) from exc
            raise

        return response["Body"].read()

    def _ensure_bucket(self, bucket_name: str) -> None:
        try:
            self._client.head_bucket(Bucket=bucket_name)
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"404", "NoSuchBucket"}:
                raise

        self._client.create_bucket(Bucket=bucket_name)
