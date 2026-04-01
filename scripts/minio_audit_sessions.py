from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict

try:
    import boto3
    from botocore.client import Config as BotoConfig
except ImportError:
    print("install boto3: pip install boto3", file=sys.stderr)
    raise

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _client():
    endpoint = os.environ.get("S3_ENDPOINT_URL") or os.environ.get("MINIO_ENDPOINT_URL") or "http://127.0.0.1:9000"
    region = os.environ.get("S3_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
    key = os.environ.get("S3_ACCESS_KEY_ID") or os.environ.get("AWS_ACCESS_KEY_ID") or "minioadmin"
    secret = os.environ.get("S3_SECRET_ACCESS_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY") or "minioadmin"
    force_path = os.environ.get("S3_FORCE_PATH_STYLE", "true").lower() in {"1", "true", "yes"}
    addressing = "path" if force_path else "auto"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": addressing}),
    )


def _bucket() -> str:
    return os.environ.get("S3_BUCKET") or os.environ.get("INGEST_S3_BUCKET") or "on-go-raw"


def _group_keys_by_session(client, bucket: str, prefix_root: str) -> dict[str, set[str]]:
    paginator = client.get_paginator("list_objects_v2")
    by_session: dict[str, set[str]] = defaultdict(set)
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_root):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/", 2)
            if len(parts) < 2 or parts[0] != "raw-sessions":
                continue
            sid = parts[1]
            if not UUID_RE.match(sid):
                continue
            by_session[sid].add(key)
    return by_session


def _has_stream_samples(keys: set[str], session_id: str, stream: str) -> bool:
    p = f"raw-sessions/{session_id}/streams/{stream}/"
    for k in keys:
        if not k.startswith(p):
            continue
        base = k.rsplit("/", 1)[-1].lower()
        if "sample" in base and (base.endswith(".csv") or base.endswith(".gz") or base.endswith(".parquet")):
            return True
    return False


def _has_checksums(keys: set[str], session_id: str) -> bool:
    for suffix in ("checksums/SHA256SUMS", "checksums/sha256sums"):
        if f"raw-sessions/{session_id}/{suffix}" in keys:
            return True
    return any(k.startswith(f"raw-sessions/{session_id}/checksums/") and "sha256" in k.lower() for k in keys)


def _delete_prefix(client, bucket: str, prefix: str) -> int:
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        batch = [{"Key": o["Key"]} for o in page.get("Contents", [])]
        if not batch:
            continue
        for i in range(0, len(batch), 1000):
            chunk = batch[i : i + 1000]
            client.delete_objects(Bucket=bucket, Delete={"Objects": chunk, "Quiet": True})
            deleted += len(chunk)
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser(description="List raw-sessions in MinIO/S3 and filter by required streams.")
    ap.add_argument(
        "--required-streams",
        default=os.environ.get("MINIO_AUDIT_REQUIRED_STREAMS", "watch_accelerometer,polar_hr,polar_rr"),
        help="Comma-separated stream names that must have sample files",
    )
    ap.add_argument("--require-checksums", action="store_true", help="Require checksums manifest under checksums/")
    ap.add_argument("--complete-only", action="store_true", help="Print only session ids that pass all checks")
    ap.add_argument("--json", action="store_true", help="One JSON object per line (session_id, complete, missing)")
    ap.add_argument(
        "--delete-incomplete",
        action="store_true",
        help="Delete all objects under raw-sessions/<id>/ for incomplete sessions (requires --i-am-sure)",
    )
    ap.add_argument("--i-am-sure", action="store_true", help="Confirm destructive delete")
    args = ap.parse_args()
    required = [s.strip() for s in args.required_streams.split(",") if s.strip()]

    client = _client()
    bucket = _bucket()
    by_session = _group_keys_by_session(client, bucket, "raw-sessions/")

    complete_ids: list[str] = []
    incomplete: list[tuple[str, list[str]]] = []

    for sid in sorted(by_session.keys()):
        keys = by_session[sid]
        missing = [s for s in required if not _has_stream_samples(keys, sid, s)]
        if args.require_checksums and not _has_checksums(keys, sid):
            missing.append("__checksums__")
        if missing:
            incomplete.append((sid, missing))
        else:
            complete_ids.append(sid)

    if args.json:
        import json

        for sid in sorted(by_session.keys()):
            keys = by_session[sid]
            missing = [s for s in required if not _has_stream_samples(keys, sid, s)]
            if args.require_checksums and not _has_checksums(keys, sid):
                missing.append("__checksums__")
            print(json.dumps({"session_id": sid, "complete": not missing, "missing": missing}))
    elif args.complete_only:
        for sid in complete_ids:
            print(sid)
    else:
        print(f"bucket={bucket} sessions={len(by_session)} complete={len(complete_ids)} incomplete={len(incomplete)}")
        print("complete:")
        for sid in complete_ids:
            print(f"  {sid}")
        print("incomplete:")
        for sid, miss in incomplete:
            print(f"  {sid}  missing={miss}")

    if args.delete_incomplete:
        if not args.i_am_sure:
            print("refusing --delete-incomplete without --i-am-sure", file=sys.stderr)
            return 2
        total = 0
        for sid, _ in incomplete:
            prefix = f"raw-sessions/{sid}/"
            n = _delete_prefix(client, bucket, prefix)
            total += n
            print(f"deleted_objects session_id={sid} count={n}", file=sys.stderr)
        print(f"deleted_total_objects={total}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
