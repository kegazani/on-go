from __future__ import annotations

from datetime import datetime, timedelta, timezone

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from ingest_api.config import Settings
from ingest_api.errors import ConflictError


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._presign_ttl_seconds = settings.s3_presign_ttl_seconds
        self._presign_endpoint_url = settings.s3_presign_endpoint_url
        addressing_style = "path" if settings.s3_force_path_style else "auto"
        self._boto_config = BotoConfig(signature_version="s3v4", s3={"addressing_style": addressing_style})
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=self._boto_config,
        )
        self._presign_client = (
            boto3.client(
                "s3",
                endpoint_url=self._presign_endpoint_url,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
                config=self._boto_config,
            )
            if self._presign_endpoint_url
            else self._client
        )
        if settings.s3_presign_require_https:
            if not self._presign_endpoint_url or not self._presign_endpoint_url.startswith("https://"):
                raise ValueError(
                    "INGEST_S3_PRESIGN_REQUIRE_HTTPS requires INGEST_S3_PRESIGN_ENDPOINT_URL "
                    "with an https:// base URL"
                )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"404", "NoSuchBucket"}:
                raise

        self._client.create_bucket(Bucket=self._bucket)

    def create_put_target(
        self,
        object_key: str,
        content_type: str,
    ) -> tuple[str, datetime, dict[str, str]]:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._presign_ttl_seconds)
        client = self._presign_client
        url = client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=self._presign_ttl_seconds,
            HttpMethod="PUT",
        )
        return url, expires_at, {"Content-Type": content_type}

    def head_object(self, object_key: str) -> dict:
        try:
            return self._client.head_object(Bucket=self._bucket, Key=object_key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey"}:
                raise ConflictError(
                    code="artifact_object_missing",
                    message="Artifact object is missing in object storage",
                    details={"object_key": object_key},
                ) from exc
            raise

    def read_object(self, object_key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey"}:
                raise ConflictError(
                    code="artifact_object_missing",
                    message="Artifact object is missing in object storage",
                    details={"object_key": object_key},
                ) from exc
            raise

        return response["Body"].read()
