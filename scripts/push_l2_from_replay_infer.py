from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx


def _load_draft_minio():
    path = Path(__file__).resolve().parent / "draft_personalization_profile_from_minio.py"
    spec = importlib.util.spec_from_file_location("draft_pf_minio", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("draft_personalization_profile_from_minio.py loader missing")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mode_from_windows(windows: list[dict], key: str) -> str | None:
    vals: list[str] = []
    for w in windows:
        if w.get("skipped"):
            continue
        raw = w.get(key)
        if raw is None:
            continue
        s = str(raw).strip()
        if s:
            vals.append(s)
    if not vals:
        return None
    return Counter(vals).most_common(1)[0][0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--subject-id", required=True)
    ap.add_argument("--live-inference-url", default="http://127.0.0.1:8120")
    ap.add_argument("--personalization-url", default="http://127.0.0.1:8110")
    ap.add_argument("--window-ms", type=int, default=None)
    ap.add_argument("--step-ms", type=int, default=None)
    ap.add_argument("--context", default="public_app")
    ap.add_argument("--replay-base-url", default=None)
    ap.add_argument("--stream-names", nargs="*", default=None)
    ap.add_argument("--global-model-reference", default="")
    ap.add_argument("--personalization-level", default="light")
    ap.add_argument("--self-report-key", default="annotations/self-report.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ensure-profile", action="store_true")
    ap.add_argument("--write-replay-json", default=None)
    args = ap.parse_args()

    dm = _load_draft_minio()
    live = args.live_inference_url.rstrip("/")
    pers = args.personalization_url.rstrip("/")

    body: dict = {
        "session_id": args.session_id.strip(),
        "context": args.context,
    }
    if args.window_ms is not None:
        body["window_ms"] = args.window_ms
    if args.step_ms is not None:
        body["step_ms"] = args.step_ms
    if args.replay_base_url:
        body["replay_base_url"] = args.replay_base_url.strip()
    if args.stream_names:
        body["stream_names"] = list(args.stream_names)

    with httpx.Client(timeout=httpx.Timeout(300.0)) as client:
        r = client.post(f"{live}/v1/replay/infer", json=body)
        if r.status_code >= 400:
            print(r.text, file=sys.stderr)
            return 1
        replay_payload = r.json()
        if args.write_replay_json:
            Path(args.write_replay_json).write_text(
                json.dumps(replay_payload, indent=2),
                encoding="utf-8",
            )

        if "error" in replay_payload:
            print(json.dumps(replay_payload["error"], indent=2), file=sys.stderr)
            return 1

        windows = replay_payload.get("windows")
        if not isinstance(windows, list):
            print("replay response missing windows list", file=sys.stderr)
            return 2

        model_pred: dict[str, str] = {}
        for key in ("activity", "arousal_coarse", "valence_coarse"):
            m = _mode_from_windows(windows, key)
            if m:
                model_pred[key] = m

        s3 = dm._s3_client()
        bucket = dm._bucket()
        prefix = f"raw-sessions/{args.session_id.strip()}/"
        self_report = dm._load_json_key(s3, bucket, prefix + args.self_report_key)
        labels = dm._iter_self_report_labels(self_report)
        anchor = dm._session_anchor_labels(labels)
        l2_maps = dm._build_l2_output_maps(model_pred, anchor)

        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        patch: dict = {
            "active_personalization_level": str(args.personalization_level),
            "last_calibrated_at_utc": now,
        }
        if args.global_model_reference:
            patch["global_model_reference"] = args.global_model_reference
            patch["global_model_reference_match"] = args.global_model_reference
        if l2_maps:
            patch["output_label_maps"] = l2_maps
            patch["version"] = "per-l2-v1"

        if not l2_maps:
            print(
                json.dumps(
                    {
                        "message": "no output_label_maps (anchors missing or model matches self-report)",
                        "model_pred": model_pred,
                        "anchor": anchor,
                    },
                    indent=2,
                )
            )
            return 3

        if args.dry_run:
            print(json.dumps(patch, indent=2))
            return 0

        subj = args.subject_id.strip()
        gr = client.get(f"{pers}/v1/profile/{subj}")
        if gr.status_code == 404 and args.ensure_profile:
            minimal = {
                "subject_id": subj,
                "physiology_baseline": {},
                "adaptation_state": {
                    "global_model_reference": args.global_model_reference or "",
                    "active_personalization_level": "none",
                    "last_calibrated_at_utc": None,
                },
                "notes": "push_l2_from_replay_infer ensure-profile",
            }
            pr = client.put(f"{pers}/v1/profile", json=minimal)
            if pr.status_code >= 400:
                print(pr.text, file=sys.stderr)
                return 1
        elif gr.status_code == 404:
            print(f"profile not found for subject_id={subj}; use --ensure-profile or PUT profile first", file=sys.stderr)
            return 1

        pr2 = client.patch(f"{pers}/v1/profile/{subj}/l2-calibration", json=patch)
        if pr2.status_code >= 400:
            print(pr2.text, file=sys.stderr)
            return 1
        print(pr2.text)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
