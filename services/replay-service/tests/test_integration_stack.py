from __future__ import annotations

import os

from stack_e2e import StackE2EConfig, run_stack_e2e


def test_replay_stack_e2e() -> None:
    config = StackE2EConfig(
        ingest_base_url=os.getenv("INGEST_BASE_URL", "http://localhost:8080"),
        replay_base_url=os.getenv("REPLAY_BASE_URL", "http://localhost:8090"),
        timeout_seconds=float(os.getenv("STACK_E2E_TIMEOUT_SECONDS", "20")),
    )

    result = run_stack_e2e(config)
    assert result["manifest_stream_count"] == 1
    assert result["window_sample_count"] == 2
