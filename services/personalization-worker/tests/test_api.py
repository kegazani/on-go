from __future__ import annotations

from fastapi.testclient import TestClient

from personalization_worker.api import create_app


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_profile_put_get() -> None:
    client = TestClient(create_app())
    payload = {
        "subject_id": "sub-1",
        "physiology_baseline": {
            "resting_hr_bpm": {"median": 65, "p10": 60, "p90": 72, "sample_count": 10},
            "hrv_rmssd_ms": {"median": 45, "p10": 35, "p90": 55, "sample_count": 10},
            "hrv_sdnn_ms": {"median": 50, "p10": 40, "p90": 60, "sample_count": 10},
            "resp_rate_bpm": {"median": 14, "p10": 12, "p90": 16, "sample_count": 10},
            "eda_scl_uS": {"median": 2.5, "p10": 2.0, "p90": 3.0, "sample_count": 10},
        },
    }
    r = client.put("/v1/profile", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["subject_id"] == "sub-1"
    assert "created_at_utc" in data
    assert "updated_at_utc" in data

    r2 = client.get("/v1/profile/sub-1")
    assert r2.status_code == 200
    assert r2.json()["subject_id"] == "sub-1"


def test_profile_get_404() -> None:
    client = TestClient(create_app())
    r = client.get("/v1/profile/nonexistent")
    assert r.status_code == 404
