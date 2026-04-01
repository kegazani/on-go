from __future__ import annotations

from replay_service.run_registry import ReplayRunRegistry


def test_create_and_complete_run() -> None:
    registry = ReplayRunRegistry()

    created = registry.create_run(
        session_id="session-001",
        orchestration_mode="full_session",
        window_request={"mode": "realtime", "window_ms": 5000, "from_offset_ms": 0, "speed_multiplier": 1.0},
    )

    assert created["status"] == "created"
    assert created["session_id"] == "session-001"

    running = registry.mark_running(created["run_id"])
    assert running["status"] == "running"
    assert running["started_at_utc"] is not None

    completed = registry.mark_completed(
        created["run_id"],
        window_count=3,
        sample_count=42,
        event_count=5,
    )
    assert completed["status"] == "completed"
    assert completed["window_count"] == 3
    assert completed["sample_count"] == 42
    assert completed["event_count"] == 5


def test_list_runs_can_filter_by_session() -> None:
    registry = ReplayRunRegistry()
    run1 = registry.create_run("session-a", "single_window", {"mode": "realtime", "window_ms": 1000, "from_offset_ms": 0, "speed_multiplier": 1.0})
    run2 = registry.create_run("session-b", "full_session", {"mode": "realtime", "window_ms": 1000, "from_offset_ms": 0, "speed_multiplier": 1.0})

    all_runs = registry.list_runs()
    assert {run["run_id"] for run in all_runs} == {run1["run_id"], run2["run_id"]}

    filtered = registry.list_runs(session_id="session-a")
    assert len(filtered) == 1
    assert filtered[0]["run_id"] == run1["run_id"]
