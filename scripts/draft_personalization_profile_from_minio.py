from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from typing import Any

try:
    import boto3
    from botocore.client import Config as BotoConfig
    from botocore.exceptions import ClientError
except ImportError:
    print("install boto3: pip install boto3", file=sys.stderr)
    raise

try:
    import psycopg
except ImportError:
    psycopg = None


def _s3_client():
    endpoint = os.environ.get("S3_ENDPOINT_URL") or os.environ.get("MINIO_ENDPOINT_URL") or os.environ.get(
        "INGEST_S3_ENDPOINT_URL"
    ) or "http://127.0.0.1:9000"
    region = os.environ.get("S3_REGION") or os.environ.get("AWS_REGION") or os.environ.get(
        "INGEST_S3_REGION"
    ) or "us-east-1"
    key = (
        os.environ.get("S3_ACCESS_KEY_ID")
        or os.environ.get("AWS_ACCESS_KEY_ID")
        or os.environ.get("INGEST_S3_ACCESS_KEY_ID")
        or "minioadmin"
    )
    secret = (
        os.environ.get("S3_SECRET_ACCESS_KEY")
        or os.environ.get("AWS_SECRET_ACCESS_KEY")
        or os.environ.get("INGEST_S3_SECRET_ACCESS_KEY")
        or "minioadmin"
    )
    force_path = os.environ.get("S3_FORCE_PATH_STYLE", os.environ.get("INGEST_S3_FORCE_PATH_STYLE", "true"))
    force_path = str(force_path).lower() in {"1", "true", "yes"}
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
    return (
        os.environ.get("S3_BUCKET")
        or os.environ.get("INGEST_S3_BUCKET")
        or "on-go-raw"
    )


def _get_bytes(client, bucket: str, key: str) -> bytes | None:
    try:
        r = client.get_object(Bucket=bucket, Key=key)
        return r["Body"].read()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchKey"}:
            return None
        raise


def _load_json_key(client, bucket: str, key: str) -> Any | None:
    raw = _get_bytes(client, bucket, key)
    if raw is None:
        return None
    return json.loads(raw.decode("utf-8"))


def _list_sample_keys(client, bucket: str, session_id: str, stream: str) -> list[str]:
    prefix = f"raw-sessions/{session_id}/streams/{stream}/"
    out: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            k = obj["Key"]
            lk = k.lower()
            if lk.endswith(".csv.gz") or lk.endswith(".csv"):
                if "sample" in lk:
                    out.append(k)
    return sorted(out)


def _hr_column(headers: list[str]) -> str | None:
    lower = [h.lower().strip() for h in headers]
    for want in ("hr_bpm", "bpm", "heart_rate", "heartrate"):
        for i, h in enumerate(lower):
            if h == want or h.replace("_", "") == want.replace("_", ""):
                return headers[i]
    return None


def _parse_hr_values(payload: bytes, name: str) -> list[float]:
    if name.endswith(".gz") or payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    text = payload.decode("utf-8", errors="replace")
    r = csv.reader(io.StringIO(text))
    rows = list(r)
    if not rows:
        return []
    headers = rows[0]
    col = _hr_column(headers)
    if col is None:
        return []
    idx = headers.index(col)
    vals: list[float] = []
    for row in rows[1:]:
        if idx >= len(row):
            continue
        try:
            vals.append(float(row[idx]))
        except ValueError:
            continue
    return vals


def _range_stat(values: list[float]) -> dict[str, Any] | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)

    def pct(p: float) -> float:
        if n == 1:
            return float(s[0])
        i = (n - 1) * p
        lo = int(i)
        hi = min(lo + 1, n - 1)
        if lo == hi:
            return float(s[lo])
        return float(s[lo] + (s[hi] - s[lo]) * (i - lo))

    return {
        "median": float(statistics.median(s)),
        "p10": pct(0.10),
        "p90": pct(0.90),
        "sample_count": n,
    }


def _hr_baseline_from_stream(client, bucket: str, session_id: str, stream: str) -> dict[str, Any] | None:
    keys = _list_sample_keys(client, bucket, session_id, stream)
    all_vals: list[float] = []
    for key in keys:
        raw = _get_bytes(client, bucket, key)
        if raw is None:
            continue
        all_vals.extend(_parse_hr_values(raw, key))
    st = _range_stat(all_vals)
    return st


def _iter_self_report_labels(doc: Any) -> list[dict[str, Any]]:
    if doc is None:
        return []
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        if isinstance(doc.get("labels"), list):
            return [x for x in doc["labels"] if isinstance(x, dict)]
        if "target_name" in doc:
            return [doc]
    return []


def _score_to_arousal_coarse(score: int) -> str:
    if score <= 3:
        return "low"
    if score <= 6:
        return "medium"
    return "high"


def _score_to_valence_coarse(score: int) -> str:
    if score <= 3:
        return "negative"
    if score <= 6:
        return "neutral"
    return "positive"


def _session_anchor_labels(labels: list[dict[str, Any]]) -> dict[str, str]:
    arousal: list[int] = []
    valence: list[int] = []
    activity: str | None = None
    for lb in labels:
        if str(lb.get("source", "")) != "participant_self_report":
            continue
        if str(lb.get("scope", "")) != "session":
            continue
        tn = str(lb.get("target_name", ""))
        val = lb.get("value")
        if tn == "arousal_score" and isinstance(val, int):
            arousal.append(val)
        if tn == "valence_score" and isinstance(val, int):
            valence.append(val)
        if tn in ("activity_label", "activity_group", "dominant_activity") and isinstance(val, str) and val.strip():
            activity = val.strip()
    out: dict[str, str] = {}
    if arousal:
        med = sorted(arousal)[len(arousal) // 2]
        out["arousal_coarse"] = _score_to_arousal_coarse(med)
    if valence:
        med = sorted(valence)[len(valence) // 2]
        out["valence_coarse"] = _score_to_valence_coarse(med)
    if activity:
        out["activity"] = activity
    return out


def _build_l2_output_maps(
    model_pred: dict[str, str],
    anchor: dict[str, str],
) -> dict[str, dict[str, str]]:
    maps: dict[str, dict[str, str]] = {}
    for t in ("activity", "arousal_coarse", "valence_coarse"):
        mp = str(model_pred.get(t, "")).strip()
        ap = str(anchor.get(t, "")).strip()
        if mp and ap and mp != ap:
            maps[t] = {mp: ap}
    return maps


def _self_report_hints(labels: list[dict[str, Any]]) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    session_arousal: list[int] = []
    session_valence: list[int] = []
    for lb in labels:
        if str(lb.get("source", "")) != "participant_self_report":
            continue
        scope = str(lb.get("scope", ""))
        tn = str(lb.get("target_name", ""))
        val = lb.get("value")
        if tn == "arousal_score" and isinstance(val, int):
            if scope == "session":
                session_arousal.append(val)
        if tn == "valence_score" and isinstance(val, int):
            if scope == "session":
                session_valence.append(val)
    if session_arousal:
        med = sorted(session_arousal)[len(session_arousal) // 2]
        hints["session_arousal_score_median"] = med
        hints["session_arousal_coarse_from_self_report"] = _score_to_arousal_coarse(med)
    if session_valence:
        med = sorted(session_valence)[len(session_valence) // 2]
        hints["session_valence_score_median"] = med
        hints["session_valence_coarse_from_self_report"] = _score_to_valence_coarse(med)
    return hints


def _latest_ingested_session_for_subject(dsn: str, subject_id: str) -> str | None:
    if psycopg is None:
        raise RuntimeError("psycopg required for --subject-id")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_id
                FROM ingest.raw_sessions
                WHERE subject_id = %s AND ingest_status = 'ingested'
                ORDER BY COALESCE(ingested_at_utc, updated_at_utc) DESC
                LIMIT 1
                """,
                (subject_id,),
            )
            row = cur.fetchone()
    return str(row[0]) if row else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build personalization-worker profile draft from ingested raw session objects in MinIO/S3.",
    )
    ap.add_argument("--session-id", help="UUID raw session under raw-sessions/<id>/")
    ap.add_argument("--subject-id", help="Resolve latest ingested session via INGEST_DATABASE_DSN")
    ap.add_argument(
        "--self-report-key",
        default="annotations/self-report.json",
        help="Path under raw-sessions/<session_id>/",
    )
    ap.add_argument(
        "--manifest-key",
        default="manifest/session.json",
        help="Path under raw-sessions/<session_id>/ (subject_id)",
    )
    ap.add_argument("--global-model-reference", default="", help="Stored in adaptation_state.global_model_reference")
    ap.add_argument(
        "--l2-model-predictions-json",
        help="JSON file with activity, arousal_coarse, valence_coarse from global model for this session",
    )
    ap.add_argument(
        "--l2-personalization-level",
        default="light",
        help="active_personalization_level when L2 maps are non-empty",
    )
    ap.add_argument(
        "--include-hr-baseline",
        action="store_true",
        help="Median HR from polar_hr then watch_heart_rate sample files in MinIO",
    )
    args = ap.parse_args()

    session_id = args.session_id
    if args.subject_id:
        dsn = os.environ.get("INGEST_DATABASE_DSN")
        if not dsn:
            print("set INGEST_DATABASE_DSN for --subject-id", file=sys.stderr)
            return 2
        session_id = _latest_ingested_session_for_subject(dsn, args.subject_id)
        if not session_id:
            print(f"no ingested session for subject_id={args.subject_id}", file=sys.stderr)
            return 1

    if not session_id:
        print("need --session-id or --subject-id", file=sys.stderr)
        return 2

    client = _s3_client()
    bucket = _bucket()
    prefix = f"raw-sessions/{session_id}/"

    manifest = _load_json_key(client, bucket, prefix + args.manifest_key)
    subject_from_manifest = None
    if isinstance(manifest, dict):
        subject_from_manifest = manifest.get("subject_id")

    self_report = _load_json_key(client, bucket, prefix + args.self_report_key)
    labels = _iter_self_report_labels(self_report)
    hints = _self_report_hints(labels)
    anchor = _session_anchor_labels(labels)

    profile_subject = args.subject_id or subject_from_manifest
    if not profile_subject:
        print("subject_id: pass --subject-id or ensure manifest/session.json contains subject_id", file=sys.stderr)
        return 1

    physiology: dict[str, Any] = {}
    if args.include_hr_baseline:
        for stream in ("polar_hr", "watch_heart_rate"):
            st = _hr_baseline_from_stream(client, bucket, session_id, stream)
            if st is not None:
                physiology["resting_hr_bpm"] = st
                physiology["l1_hr_stream"] = stream
                break

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    notes_parts = [
        f"draft_from_minio session_id={session_id}",
        f"generated_at_utc={now}",
    ]
    if hints:
        notes_parts.append("self_report_hints=" + json.dumps(hints, separators=(",", ":")))
    if anchor:
        notes_parts.append("session_anchor_labels=" + json.dumps(anchor, separators=(",", ":")))

    adaptation_state: dict[str, Any] = {
        "global_model_reference": args.global_model_reference or "",
        "active_personalization_level": "none",
        "last_calibrated_at_utc": None,
    }

    l2_maps: dict[str, dict[str, str]] = {}
    if args.l2_model_predictions_json:
        with open(args.l2_model_predictions_json, encoding="utf-8") as f:
            raw_pred = json.load(f)
        if not isinstance(raw_pred, dict):
            print("l2 model predictions JSON must be an object", file=sys.stderr)
            return 2
        model_pred: dict[str, str] = {}
        for k, v in raw_pred.items():
            if isinstance(v, (str, int, float)):
                model_pred[str(k)] = str(v).strip()
        l2_maps = _build_l2_output_maps(model_pred, anchor)
        notes_parts.append("l2_output_label_maps=" + json.dumps(l2_maps, separators=(",", ":")))
        if l2_maps:
            l2_block: dict[str, Any] = {
                "version": "per-l2-v1",
                "output_label_maps": l2_maps,
            }
            if args.global_model_reference:
                l2_block["global_model_reference_match"] = args.global_model_reference
            adaptation_state["l2_calibration"] = l2_block
            adaptation_state["active_personalization_level"] = str(args.l2_personalization_level)
            adaptation_state["last_calibrated_at_utc"] = now

    profile = {
        "subject_id": str(profile_subject),
        "physiology_baseline": physiology,
        "adaptation_state": adaptation_state,
        "notes": "\n".join(notes_parts),
    }

    print(json.dumps(profile, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
