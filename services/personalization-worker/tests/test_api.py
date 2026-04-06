from __future__ import annotations

from fastapi.testclient import TestClient

from personalization_worker.api import create_app
from personalization_worker.config import Settings
from personalization_worker.store import InMemoryProfileStore


def test_health() -> None:
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "store": "memory", "db": "n/a"}


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


def test_profile_put_accepts_l2_calibration() -> None:
    client = TestClient(create_app())
    payload = {
        "subject_id": "sub-l2",
        "physiology_baseline": {"resting_hr_bpm": 60},
        "adaptation_state": {
            "active_personalization_level": "light",
            "global_model_reference": "bundle-a",
            "l2_calibration": {
                "output_label_maps": {"arousal_coarse": {"low": "medium"}},
            },
        },
    }
    r = client.put("/v1/profile", json=payload)
    assert r.status_code == 200
    got = r.json()["adaptation_state"]["l2_calibration"]["output_label_maps"]["arousal_coarse"]
    assert got["low"] == "medium"


def test_patch_l2_calibration_404() -> None:
    client = TestClient(create_app())
    r = client.patch(
        "/v1/profile/missing/l2-calibration",
        json={"output_label_maps": {"arousal_coarse": {"low": "medium"}}},
    )
    assert r.status_code == 404


def test_patch_l2_calibration_creates_when_profile_has_no_l2() -> None:
    client = TestClient(create_app())
    client.put(
        "/v1/profile",
        json={"subject_id": "sub-new-l2", "physiology_baseline": {"x": 1}},
    )
    r = client.patch(
        "/v1/profile/sub-new-l2/l2-calibration",
        json={"output_label_maps": {"valence_coarse": {"neutral": "positive"}}},
    )
    assert r.status_code == 200
    l2 = r.json()["adaptation_state"]["l2_calibration"]
    assert l2["output_label_maps"]["valence_coarse"]["neutral"] == "positive"


def test_patch_l2_calibration_merges_maps() -> None:
    client = TestClient(create_app())
    client.put(
        "/v1/profile",
        json={
            "subject_id": "sub-patch",
            "physiology_baseline": {"x": 1},
            "adaptation_state": {
                "active_personalization_level": "light",
                "l2_calibration": {
                    "output_label_maps": {"arousal_coarse": {"low": "medium"}},
                },
            },
        },
    )
    r = client.patch(
        "/v1/profile/sub-patch/l2-calibration",
        json={
            "output_label_maps": {
                "arousal_coarse": {"high": "low"},
                "activity": {"rest": "light_motion"},
            },
        },
    )
    assert r.status_code == 200
    maps = r.json()["adaptation_state"]["l2_calibration"]["output_label_maps"]
    assert maps["arousal_coarse"] == {"low": "medium", "high": "low"}
    assert maps["activity"] == {"rest": "light_motion"}


def test_patch_l2_calibration_updates_adaptation_without_maps() -> None:
    client = TestClient(create_app())
    client.put(
        "/v1/profile",
        json={"subject_id": "sub-adapt", "physiology_baseline": {"x": 1}},
    )
    r = client.patch(
        "/v1/profile/sub-adapt/l2-calibration",
        json={
            "active_personalization_level": "full",
            "global_model_reference": "bundle-x",
            "last_calibrated_at_utc": "2026-04-05T12:00:00Z",
        },
    )
    assert r.status_code == 200
    a = r.json()["adaptation_state"]
    assert a["active_personalization_level"] == "full"
    assert a["global_model_reference"] == "bundle-x"
    assert a["last_calibrated_at_utc"] == "2026-04-05T12:00:00Z"


def test_create_app_accepts_injected_store() -> None:
    store = InMemoryProfileStore()
    client = TestClient(create_app(Settings(database_dsn=None), store=store))
    r = client.put(
        "/v1/profile",
        json={"subject_id": "inj", "physiology_baseline": {"x": 1}},
    )
    assert r.status_code == 200
    assert store.get("inj") is not None
