from __future__ import annotations

import json
import os
from urllib import request

from stack_e2e import StackE2EConfig, StackE2EError, _json_request, run_stack_e2e


def run_stream_stack_e2e(config: StackE2EConfig | None = None) -> dict[str, str]:
    cfg = config or StackE2EConfig()
    base_result = run_stack_e2e(cfg)
    session_id = base_result["session_id"]

    status, run_body = _json_request(
        "POST",
        f"{cfg.replay_base_url}/v1/replay/sessions/{session_id}/runs",
        payload={
            "orchestration_mode": "single_window",
            "window_request": {
                "mode": "accelerated",
                "speed_multiplier": 2.0,
                "from_offset_ms": 500,
                "window_ms": 2000,
                "stream_names": ["watch_heart_rate"],
                "include_events": False,
                "max_samples_per_stream": 10,
            },
        },
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 200:
        raise StackE2EError(f"create run failed: status={status}, body={run_body}")

    run_id = run_body["run_id"]

    stream_url = f"{cfg.replay_base_url}/v1/replay/runs/{run_id}/events"
    req = request.Request(stream_url, headers={"Accept": "text/event-stream"}, method="GET")

    got_window = False
    got_completed = False
    with request.urlopen(req, timeout=cfg.timeout_seconds) as resp:
        while True:
            line = resp.readline()
            if not line:
                break

            text = line.decode("utf-8").strip()
            if text.startswith("event: "):
                event_name = text.split(": ", 1)[1]
                data_line = resp.readline().decode("utf-8").strip()
                if not data_line.startswith("data: "):
                    continue
                payload = json.loads(data_line.split(": ", 1)[1])

                if event_name == "replay_window":
                    got_window = True
                if event_name == "run_completed":
                    got_completed = True
                    break
                if event_name == "run_failed":
                    raise StackE2EError(f"stream returned run_failed: {payload}")

    if not got_window or not got_completed:
        raise StackE2EError(
            f"missing expected SSE events: got_window={got_window}, got_completed={got_completed}"
        )

    status, run_state = _json_request(
        "GET",
        f"{cfg.replay_base_url}/v1/replay/runs/{run_id}",
        timeout_seconds=cfg.timeout_seconds,
    )
    if status != 200:
        raise StackE2EError(f"get run failed: status={status}, body={run_state}")
    if run_state.get("status") != "completed":
        raise StackE2EError(f"run status mismatch: {run_state}")

    return {"session_id": session_id, "run_id": run_id}


def main() -> int:
    config = StackE2EConfig(
        ingest_base_url=os.getenv("INGEST_BASE_URL", "http://localhost:8080"),
        replay_base_url=os.getenv("REPLAY_BASE_URL", "http://localhost:8090"),
        timeout_seconds=float(os.getenv("STACK_E2E_TIMEOUT_SECONDS", "20")),
    )
    try:
        result = run_stream_stack_e2e(config)
    except Exception as exc:  # noqa: BLE001
        print(f"[stack-stream-e2e] FAILED: {exc}")
        return 1

    print("[stack-stream-e2e] OK")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
