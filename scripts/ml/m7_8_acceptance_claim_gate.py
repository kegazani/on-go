#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

import websockets


DEFAULT_OUTPUT_DIR = Path(
    "/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-8-acceptance-claim-gate"
)
DEFAULT_WS_URL = "ws://127.0.0.1:8120/ws/live"
DEFAULT_HEALTH_URL = "http://127.0.0.1:8120/health"
DEFAULT_CONTEXT = "internal_dashboard"
DEFAULT_PHASES = ("rest", "movement", "recovery")
DEFAULT_BATCH_COUNT_PER_PHASE = 4
DEFAULT_BATCH_SPAN_MS = 5000
DEFAULT_SAMPLE_STEP_MS = 1000


@dataclass(frozen=True)
class BatchSpec:
    phase: str
    batch_index: int
    batch_start_ms: int
    batch_end_ms: int
    acc_samples: list[dict[str, Any]]
    hr_samples: list[dict[str, Any]]
    rr_samples: list[dict[str, Any]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_acc_sample(phase: str, batch_index: int, sample_index: int, offset_ms: int) -> dict[str, Any]:
    if phase == "rest":
        x = 0.015 + 0.004 * batch_index + 0.002 * sample_index
        y = -0.01 + 0.003 * sample_index
        z = 0.985 + 0.003 * ((batch_index + sample_index) % 2)
    elif phase == "movement":
        x = 0.34 + 0.06 * batch_index + 0.03 * sample_index
        y = -0.18 + 0.04 * ((batch_index + sample_index) % 3)
        z = 0.84 + 0.02 * ((sample_index + batch_index) % 4)
    elif phase == "recovery":
        x = 0.05 + 0.01 * batch_index + 0.003 * sample_index
        y = 0.01 + 0.002 * sample_index
        z = 0.992 + 0.002 * ((sample_index + batch_index) % 2)
    else:
        x = 0.1
        y = 0.0
        z = 1.0
    return {
        "offset_ms": offset_ms,
        "values": {
            "acc_x_g": round(x, 6),
            "acc_y_g": round(y, 6),
            "acc_z_g": round(z, 6),
        },
    }


def _build_hr_sample(phase: str, batch_index: int, sample_index: int, offset_ms: int) -> dict[str, Any]:
    if phase == "rest":
        hr = 64 + batch_index + (sample_index % 2)
    elif phase == "movement":
        hr = 94 + 2 * batch_index + (sample_index % 3)
    elif phase == "recovery":
        hr = 82 - 3 * batch_index - (sample_index % 2)
    else:
        hr = 72
    return {
        "offset_ms": offset_ms,
        "values": {
            "hr_bpm": round(float(hr), 3),
        },
    }


def _build_rr_sample(phase: str, batch_index: int, sample_index: int, offset_ms: int) -> dict[str, Any]:
    if phase == "rest":
        rr_ms = 940 - 4 * batch_index - 2 * (sample_index % 2)
    elif phase == "movement":
        rr_ms = 690 - 6 * batch_index - 3 * (sample_index % 2)
    elif phase == "recovery":
        rr_ms = 820 - 3 * batch_index - (sample_index % 2)
    else:
        rr_ms = 830
    return {
        "offset_ms": offset_ms,
        "values": {
            "rr_ms": round(float(rr_ms), 3),
        },
    }


def _generate_batches(phases: tuple[str, ...], batch_count_per_phase: int) -> list[BatchSpec]:
    batches: list[BatchSpec] = []
    phase_span_ms = batch_count_per_phase * DEFAULT_BATCH_SPAN_MS
    for phase_index, phase in enumerate(phases):
        phase_start_ms = phase_index * phase_span_ms
        for batch_index in range(batch_count_per_phase):
            batch_start_ms = phase_start_ms + batch_index * DEFAULT_BATCH_SPAN_MS
            batch_end_ms = batch_start_ms + DEFAULT_BATCH_SPAN_MS
            acc_samples = [
                _build_acc_sample(
                    phase=phase,
                    batch_index=batch_index,
                    sample_index=sample_index,
                    offset_ms=batch_start_ms + sample_index * DEFAULT_SAMPLE_STEP_MS,
                )
                for sample_index in range(DEFAULT_BATCH_SPAN_MS // DEFAULT_SAMPLE_STEP_MS)
            ]
            hr_samples = [
                _build_hr_sample(
                    phase=phase,
                    batch_index=batch_index,
                    sample_index=sample_index,
                    offset_ms=batch_start_ms + sample_index * DEFAULT_SAMPLE_STEP_MS,
                )
                for sample_index in range(DEFAULT_BATCH_SPAN_MS // DEFAULT_SAMPLE_STEP_MS)
            ]
            rr_samples = [
                _build_rr_sample(
                    phase=phase,
                    batch_index=batch_index,
                    sample_index=sample_index,
                    offset_ms=batch_start_ms + sample_index * DEFAULT_SAMPLE_STEP_MS,
                )
                for sample_index in range(DEFAULT_BATCH_SPAN_MS // DEFAULT_SAMPLE_STEP_MS)
            ]
            batches.append(
                BatchSpec(
                    phase=phase,
                    batch_index=batch_index,
                    batch_start_ms=batch_start_ms,
                    batch_end_ms=batch_end_ms,
                    acc_samples=acc_samples,
                    hr_samples=hr_samples,
                    rr_samples=rr_samples,
                )
            )
    return batches


def _load_health(health_url: str) -> dict[str, Any]:
    try:
        with urlopen(health_url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return {"status": "unreachable", "error": f"{type(exc).__name__}: {exc}"}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _safe_number(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _extract_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "heart_source": payload.get("heart_source"),
        "heart_source_fallback_active": payload.get("heart_source_fallback_active"),
        "feature_count": payload.get("feature_count"),
        "feature_count_total": payload.get("feature_count_total"),
        "feature_count_nonzero": payload.get("feature_count_nonzero"),
        "feature_coverage_by_track": payload.get("feature_coverage_by_track"),
    }


async def _run_capture(args: argparse.Namespace) -> dict[str, Any]:
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    health = _load_health(args.health_url)
    batches = _generate_batches(args.phases, args.batch_count_per_phase)
    trace_rows: list[dict[str, Any]] = []
    jsonl_rows: list[dict[str, Any]] = []
    protocol_events: list[dict[str, Any]] = []

    sent_batches = 0
    received_messages = 0
    inference_count = 0
    error_count = 0
    pong_count = 0
    heart_source_counts: dict[str, int] = {}
    phase_inference_counts: dict[str, int] = {phase: 0 for phase in args.phases}
    feature_count_total_values: list[int] = []
    feature_count_nonzero_values: list[int] = []
    confidence_scores: list[float] = []
    window_starts: list[int] = []
    window_ends: list[int] = []
    activity_classes: dict[str, int] = {}
    derived_states: dict[str, int] = {}
    claim_levels: dict[str, int] = {}
    telemetry_presence = {
        "feature_count_total": 0,
        "feature_count_nonzero": 0,
        "feature_coverage_by_track": 0,
    }
    streams_to_send = (
        ("watch_accelerometer", "acc_samples"),
        ("polar_hr", "hr_samples"),
        ("polar_rr", "rr_samples"),
    ) if args.include_polar_rr else (
        ("watch_accelerometer", "acc_samples"),
        ("polar_hr", "hr_samples"),
    )

    async with websockets.connect(args.ws_url, open_timeout=10, close_timeout=10) as ws:
        for batch in batches:
            sent_batches += 1
            for stream_name, sample_attr in streams_to_send:
                samples = getattr(batch, sample_attr)
                request = {
                    "type": "stream_batch",
                    "stream_name": stream_name,
                    "source_mode": "live",
                    "context": args.context,
                    "samples": samples,
                }
                await ws.send(json.dumps(request))
                sent_at = _utc_now()
                trace_rows.append(
                    {
                        "record_type": "send_batch",
                        "sequence": len(trace_rows) + 1,
                        "phase": batch.phase,
                        "stream_name": stream_name,
                        "batch_index": batch.batch_index,
                        "batch_start_ms": batch.batch_start_ms,
                        "batch_end_ms": batch.batch_end_ms,
                        "sample_count": len(samples),
                        "source_mode": "live",
                        "context": args.context,
                        "message_type": "stream_batch",
                        "received_type": "",
                        "received_code": "",
                        "window_start_ms": "",
                        "window_end_ms": "",
                        "heart_source": "",
                        "heart_source_fallback_active": "",
                        "activity_class": "",
                        "arousal_coarse": "",
                        "valence_coarse": "",
                        "derived_state": "",
                        "claim_level": "",
                        "confidence_score": "",
                        "confidence_band": "",
                        "feature_count": "",
                        "feature_count_total": "",
                        "feature_count_nonzero": "",
                        "sent_at_utc": sent_at,
                        "received_at_utc": "",
                    }
                )
                protocol_events.append(
                    {
                        "event_type": "send_batch",
                        "timestamp_utc": sent_at,
                        "phase": batch.phase,
                        "stream_name": stream_name,
                        "batch_index": batch.batch_index,
                        "batch_start_ms": batch.batch_start_ms,
                        "batch_end_ms": batch.batch_end_ms,
                        "sample_count": len(samples),
                        "source_mode": "live",
                        "context": args.context,
                        "sample_preview": samples[:2],
                    }
                )

                while True:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=args.recv_timeout_sec)
                    except asyncio.TimeoutError:
                        break
                    received_at = _utc_now()
                    received_messages += 1
                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        payload = {"type": "invalid_json", "raw": raw}
                    payload_type = str(payload.get("type", ""))
                    row = {
                        "record_type": "recv_message",
                        "sequence": len(trace_rows) + 1,
                        "phase": batch.phase,
                        "stream_name": stream_name,
                        "batch_index": batch.batch_index,
                        "batch_start_ms": batch.batch_start_ms,
                        "batch_end_ms": batch.batch_end_ms,
                        "sample_count": len(samples),
                        "source_mode": "live",
                        "context": args.context,
                        "message_type": payload_type,
                        "received_type": payload_type,
                        "received_code": payload.get("code", ""),
                        "window_start_ms": payload.get("window_start_ms", ""),
                        "window_end_ms": payload.get("window_end_ms", ""),
                        "heart_source": payload.get("heart_source", ""),
                        "heart_source_fallback_active": payload.get("heart_source_fallback_active", ""),
                        "activity_class": payload.get("activity_class", ""),
                        "arousal_coarse": payload.get("arousal_coarse", ""),
                        "valence_coarse": payload.get("valence_coarse", ""),
                        "derived_state": payload.get("derived_state", ""),
                        "claim_level": payload.get("claim_level", ""),
                        "confidence_score": "",
                        "confidence_band": "",
                        "feature_count": payload.get("feature_count", ""),
                        "feature_count_total": payload.get("feature_count_total", ""),
                        "feature_count_nonzero": payload.get("feature_count_nonzero", ""),
                        "sent_at_utc": "",
                        "received_at_utc": received_at,
                    }
                    if payload_type == "inference":
                        inference_count += 1
                        phase_inference_counts[batch.phase] += 1
                        heart_source = str(payload.get("heart_source", ""))
                        if heart_source:
                            heart_source_counts[heart_source] = heart_source_counts.get(heart_source, 0) + 1
                        window_starts.append(int(payload.get("window_start_ms", 0)))
                        window_ends.append(int(payload.get("window_end_ms", 0)))
                        activity_class = str(payload.get("activity_class", ""))
                        derived_state = str(payload.get("derived_state", ""))
                        claim_level = str(payload.get("claim_level", ""))
                        activity_classes[activity_class] = activity_classes.get(activity_class, 0) + 1
                        derived_states[derived_state] = derived_states.get(derived_state, 0) + 1
                        claim_levels[claim_level] = claim_levels.get(claim_level, 0) + 1
                        confidence = payload.get("confidence", {})
                        if isinstance(confidence, dict):
                            score = confidence.get("score")
                            if isinstance(score, (int, float)):
                                confidence_scores.append(float(score))
                                row["confidence_score"] = float(score)
                            band = confidence.get("band")
                            if isinstance(band, str):
                                row["confidence_band"] = band
                        telemetry = _extract_telemetry(payload)
                        if telemetry["feature_count_total"] is not None:
                            telemetry_presence["feature_count_total"] += 1
                            try:
                                feature_count_total_values.append(int(telemetry["feature_count_total"]))
                            except (TypeError, ValueError):
                                pass
                        if telemetry["feature_count_nonzero"] is not None:
                            telemetry_presence["feature_count_nonzero"] += 1
                            try:
                                feature_count_nonzero_values.append(int(telemetry["feature_count_nonzero"]))
                            except (TypeError, ValueError):
                                pass
                        if telemetry["feature_coverage_by_track"] is not None:
                            telemetry_presence["feature_coverage_by_track"] += 1
                        jsonl_rows.append(
                            {
                                "record_type": "inference",
                                "timestamp_utc": received_at,
                                "phase": batch.phase,
                                "stream_name": stream_name,
                                "batch_index": batch.batch_index,
                                "batch_start_ms": batch.batch_start_ms,
                                "batch_end_ms": batch.batch_end_ms,
                                "payload": payload,
                                "telemetry": telemetry,
                            }
                        )
                    elif payload_type == "error":
                        error_count += 1
                        jsonl_rows.append(
                            {
                                "record_type": "error",
                                "timestamp_utc": received_at,
                                "phase": batch.phase,
                                "stream_name": stream_name,
                                "batch_index": batch.batch_index,
                                "batch_start_ms": batch.batch_start_ms,
                                "batch_end_ms": batch.batch_end_ms,
                                "payload": payload,
                            }
                        )
                    elif payload_type == "pong":
                        pong_count += 1
                        jsonl_rows.append(
                            {
                                "record_type": "pong",
                                "timestamp_utc": received_at,
                                "phase": batch.phase,
                                "stream_name": stream_name,
                                "batch_index": batch.batch_index,
                                "batch_start_ms": batch.batch_start_ms,
                                "batch_end_ms": batch.batch_end_ms,
                                "payload": payload,
                            }
                        )
                    else:
                        jsonl_rows.append(
                            {
                                "record_type": "message",
                                "timestamp_utc": received_at,
                                "phase": batch.phase,
                                "stream_name": stream_name,
                                "batch_index": batch.batch_index,
                                "batch_start_ms": batch.batch_start_ms,
                                "batch_end_ms": batch.batch_end_ms,
                                "payload": payload,
                            }
                        )
                    trace_rows.append(row)
                    protocol_events.append(
                        {
                            "event_type": "recv_message",
                            "timestamp_utc": received_at,
                            "phase": batch.phase,
                            "stream_name": stream_name,
                            "batch_index": batch.batch_index,
                            "batch_start_ms": batch.batch_start_ms,
                            "batch_end_ms": batch.batch_end_ms,
                            "payload": payload,
                        }
                    )

        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=args.final_drain_timeout_sec)
                received_at = _utc_now()
                received_messages += 1
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {"type": "invalid_json", "raw": raw}
                payload_type = str(payload.get("type", ""))
                row = {
                    "record_type": "recv_message",
                    "sequence": len(trace_rows) + 1,
                    "phase": "drain",
                    "stream_name": "",
                    "batch_index": "",
                    "batch_start_ms": "",
                    "batch_end_ms": "",
                    "sample_count": "",
                    "source_mode": "",
                    "context": args.context,
                    "message_type": payload_type,
                    "received_type": payload_type,
                    "received_code": payload.get("code", ""),
                    "window_start_ms": payload.get("window_start_ms", ""),
                    "window_end_ms": payload.get("window_end_ms", ""),
                    "heart_source": payload.get("heart_source", ""),
                    "heart_source_fallback_active": payload.get("heart_source_fallback_active", ""),
                    "activity_class": payload.get("activity_class", ""),
                    "arousal_coarse": payload.get("arousal_coarse", ""),
                    "valence_coarse": payload.get("valence_coarse", ""),
                    "derived_state": payload.get("derived_state", ""),
                    "claim_level": payload.get("claim_level", ""),
                    "confidence_score": "",
                    "confidence_band": "",
                    "feature_count": payload.get("feature_count", ""),
                    "feature_count_total": payload.get("feature_count_total", ""),
                    "feature_count_nonzero": payload.get("feature_count_nonzero", ""),
                    "sent_at_utc": "",
                    "received_at_utc": received_at,
                }
                if payload_type == "inference":
                    inference_count += 1
                    heart_source = str(payload.get("heart_source", ""))
                    if heart_source:
                        heart_source_counts[heart_source] = heart_source_counts.get(heart_source, 0) + 1
                    window_starts.append(int(payload.get("window_start_ms", 0)))
                    window_ends.append(int(payload.get("window_end_ms", 0)))
                    activity_class = str(payload.get("activity_class", ""))
                    derived_state = str(payload.get("derived_state", ""))
                    claim_level = str(payload.get("claim_level", ""))
                    activity_classes[activity_class] = activity_classes.get(activity_class, 0) + 1
                    derived_states[derived_state] = derived_states.get(derived_state, 0) + 1
                    claim_levels[claim_level] = claim_levels.get(claim_level, 0) + 1
                    confidence = payload.get("confidence", {})
                    if isinstance(confidence, dict):
                        score = confidence.get("score")
                        if isinstance(score, (int, float)):
                            confidence_scores.append(float(score))
                            row["confidence_score"] = float(score)
                        band = confidence.get("band")
                        if isinstance(band, str):
                            row["confidence_band"] = band
                    telemetry = _extract_telemetry(payload)
                    if telemetry["feature_count_total"] is not None:
                        telemetry_presence["feature_count_total"] += 1
                        try:
                            feature_count_total_values.append(int(telemetry["feature_count_total"]))
                        except (TypeError, ValueError):
                            pass
                    if telemetry["feature_count_nonzero"] is not None:
                        telemetry_presence["feature_count_nonzero"] += 1
                        try:
                            feature_count_nonzero_values.append(int(telemetry["feature_count_nonzero"]))
                        except (TypeError, ValueError):
                            pass
                    if telemetry["feature_coverage_by_track"] is not None:
                        telemetry_presence["feature_coverage_by_track"] += 1
                    jsonl_rows.append(
                        {
                            "record_type": "inference",
                            "timestamp_utc": received_at,
                            "phase": "drain",
                            "stream_name": "",
                            "batch_index": None,
                            "batch_start_ms": None,
                            "batch_end_ms": None,
                            "payload": payload,
                            "telemetry": telemetry,
                        }
                    )
                elif payload_type == "error":
                    error_count += 1
                    jsonl_rows.append(
                        {
                            "record_type": "error",
                            "timestamp_utc": received_at,
                            "phase": "drain",
                            "stream_name": "",
                            "batch_index": None,
                            "batch_start_ms": None,
                            "batch_end_ms": None,
                            "payload": payload,
                        }
                    )
                elif payload_type == "pong":
                    pong_count += 1
                    jsonl_rows.append(
                        {
                            "record_type": "pong",
                            "timestamp_utc": received_at,
                            "phase": "drain",
                            "stream_name": "",
                            "batch_index": None,
                            "batch_start_ms": None,
                            "batch_end_ms": None,
                            "payload": payload,
                        }
                    )
                else:
                    jsonl_rows.append(
                        {
                            "record_type": "message",
                            "timestamp_utc": received_at,
                            "phase": "drain",
                            "stream_name": "",
                            "batch_index": None,
                            "batch_start_ms": None,
                            "batch_end_ms": None,
                            "payload": payload,
                        }
                    )
                trace_rows.append(row)
                protocol_events.append(
                    {
                        "event_type": "recv_message",
                        "timestamp_utc": received_at,
                        "phase": "drain",
                        "stream_name": "",
                        "batch_index": None,
                        "batch_start_ms": None,
                        "batch_end_ms": None,
                        "payload": payload,
                    }
                )
        except asyncio.TimeoutError:
            pass

    if not window_starts:
        window_span = None
    else:
        window_span = {
            "first_window_start_ms": min(window_starts),
            "last_window_end_ms": max(window_ends),
            "window_count": len(window_starts),
            "window_span_ms": max(window_ends) - min(window_starts),
        }

    real_device_evidence_present = bool(args.real_device_evidence and args.real_device_evidence.exists())
    activity_canary_present = bool(activity_classes)
    arousal_canary_present = bool(
        inference_count > 0
        and any(
            row.get("payload", {}).get("arousal_coarse")
            for row in jsonl_rows
            if row.get("record_type") == "inference"
        )
    )
    gate_decision = "blocked"
    device_protocol_validated = False
    if real_device_evidence_present and inference_count > 0 and activity_canary_present and arousal_canary_present:
        gate_decision = "pass"
        device_protocol_validated = True

    if not real_device_evidence_present:
        decision_reason = "No real physical-device evidence was present in this run."
    elif inference_count == 0:
        decision_reason = "No inference responses were captured."
    elif not activity_canary_present or not arousal_canary_present:
        decision_reason = "Live inference was captured, but activity/arousal canary evidence is incomplete."
    else:
        decision_reason = "Physical-device evidence and activity/arousal live canary evidence were captured."

    report = {
        "experiment_id": f"{args.experiment_prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at_utc": _utc_now(),
        "ws_url": args.ws_url,
        "health_url": args.health_url,
        "health_check": health,
        "source_mode": "live",
        "context": args.context,
        "phases": list(args.phases),
        "batch_count_per_phase": args.batch_count_per_phase,
        "batch_span_ms": DEFAULT_BATCH_SPAN_MS,
        "sample_step_ms": DEFAULT_SAMPLE_STEP_MS,
        "streams_sent": [stream_name for stream_name, _ in streams_to_send],
        "sent_batches": sent_batches,
        "received_messages": received_messages,
        "inference_count": inference_count,
        "error_count": error_count,
        "pong_count": pong_count,
        "gate_decision": gate_decision,
        "device_protocol_validated": device_protocol_validated,
        "real_device_evidence_present": real_device_evidence_present,
        "decision_reason": decision_reason,
        "canary_summary": {
            "activity_canary_present": activity_canary_present,
            "arousal_canary_present": arousal_canary_present,
            "activity_class_count": len(activity_classes),
            "arousal_labels_observed": sorted(
                {
                    str(row.get("payload", {}).get("arousal_coarse", ""))
                    for row in jsonl_rows
                    if row.get("record_type") == "inference" and row.get("payload", {}).get("arousal_coarse")
                }
            ),
        },
        "protocol_summary": {
            "phase_order": list(args.phases),
            "phase_batch_counts": {phase: args.batch_count_per_phase for phase in args.phases},
            "phase_inference_counts": phase_inference_counts,
            "heart_source_counts": heart_source_counts,
            "activity_class_counts": activity_classes,
            "derived_state_counts": derived_states,
            "claim_level_counts": claim_levels,
            "confidence_score_mean": round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else None,
            "window_span": window_span,
            "telemetry_presence": telemetry_presence,
            "feature_count_total_values": feature_count_total_values[:20],
            "feature_count_nonzero_values": feature_count_nonzero_values[:20],
        },
        "artifact_files": {
            "acceptance-gate-report.json": str(output_dir / "acceptance-gate-report.json"),
            "acceptance-gate-report.md": str(output_dir / "acceptance-gate-report.md"),
            "protocol-phase-trace.csv": str(output_dir / "protocol-phase-trace.csv"),
            "websocket-inference-log.jsonl": str(output_dir / "websocket-inference-log.jsonl"),
        },
    }

    _write_json(output_dir / "acceptance-gate-report.json", report)
    _write_csv(output_dir / "protocol-phase-trace.csv", trace_rows)
    _write_jsonl(output_dir / "websocket-inference-log.jsonl", jsonl_rows)

    md_lines = [
        "# Acceptance Claim Gate",
        "",
        f"- Decision: `{gate_decision}`",
        f"- Device protocol validated: `{str(device_protocol_validated).lower()}`",
        f"- Real device evidence present: `{str(real_device_evidence_present).lower()}`",
        f"- Source mode: `live`",
        f"- Context: `{args.context}`",
        f"- Streams sent: `{json.dumps([stream_name for stream_name, _ in streams_to_send], ensure_ascii=False)}`",
        f"- WS URL: `{args.ws_url}`",
        f"- Health: `{json.dumps(health, ensure_ascii=False)}`",
        f"- Batches sent: `{sent_batches}`",
        f"- Messages received: `{received_messages}`",
        f"- Inferences: `{inference_count}`",
        f"- Errors: `{error_count}`",
        f"- Pong messages: `{pong_count}`",
        f"- Heart sources: `{json.dumps(heart_source_counts, ensure_ascii=False)}`",
        f"- Activity classes: `{json.dumps(activity_classes, ensure_ascii=False)}`",
        f"- Derived states: `{json.dumps(derived_states, ensure_ascii=False)}`",
        f"- Claim levels: `{json.dumps(claim_levels, ensure_ascii=False)}`",
        f"- Canary summary: `{json.dumps(report['canary_summary'], ensure_ascii=False)}`",
        f"- Telemetry presence: `{json.dumps(telemetry_presence, ensure_ascii=False)}`",
        "",
        "## Decision",
        "",
        decision_reason,
    ]
    (output_dir / "acceptance-gate-report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="M7.8 acceptance claim gate rerun")
    parser.add_argument("--ws-url", type=str, default=DEFAULT_WS_URL)
    parser.add_argument("--health-url", type=str, default=DEFAULT_HEALTH_URL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--context", type=str, default=DEFAULT_CONTEXT)
    parser.add_argument("--phases", nargs="+", default=list(DEFAULT_PHASES))
    parser.add_argument("--batch-count-per-phase", type=int, default=DEFAULT_BATCH_COUNT_PER_PHASE)
    parser.add_argument("--recv-timeout-sec", type=float, default=0.15)
    parser.add_argument("--final-drain-timeout-sec", type=float, default=0.5)
    parser.add_argument("--include-polar-rr", action="store_true")
    parser.add_argument("--experiment-prefix", type=str, default="m7-8-acceptance-claim-gate")
    parser.add_argument(
        "--real-device-evidence",
        type=Path,
        default=None,
        help="Optional path to a concrete physical-device evidence file. If omitted, the gate remains blocked.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(_run_capture(args))


if __name__ == "__main__":
    main()
