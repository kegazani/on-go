from __future__ import annotations

import gzip

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from replay_service.config import Settings
from replay_service.errors import NotFoundError


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        addressing_style = "path" if settings.s3_force_path_style else "auto"
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=BotoConfig(signature_version="s3v4", s3={"addressing_style": addressing_style}),
        )

    def read_object(self, object_key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey"}:
                raise NotFoundError(
                    code="replay_object_missing",
                    message="Replay object is missing in object storage",
                    details={"object_key": object_key},
                ) from exc
            raise

        return response["Body"].read()

    def read_text(self, object_key: str) -> str:
        payload = self.read_object(object_key)
        if object_key.endswith(".gz") or payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
        return payload.decode("utf-8")
