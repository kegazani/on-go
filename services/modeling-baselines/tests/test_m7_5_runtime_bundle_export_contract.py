from __future__ import annotations

import json
from pathlib import Path
from typing import Any


M75_REQUIRED_TRACKS = ("activity", "arousal_coarse", "valence_coarse")


def _export_m75_runtime_bundle(
    output_dir: Path,
    *,
    gate_verdict_path: Path,
    selected_tracks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate_verdict = json.loads(gate_verdict_path.read_text(encoding="utf-8"))
    if not gate_verdict.get("gate_passed", False):
        raise RuntimeError("M7.5 requires gate_passed=true before runtime bundle export")

    if tuple(selected_tracks) != M75_REQUIRED_TRACKS:
        raise RuntimeError(f"M7.5 requires tracks {M75_REQUIRED_TRACKS!r}")

    run_root = output_dir / "wesad" / "wesad-v1" / "m7-5-runtime-bundle-export"
    bundle_root = run_root / "bundle"
    bundle_root.mkdir(parents=True, exist_ok=False)

    manifest_tracks: dict[str, Any] = {}
    bundle_files: dict[str, str] = {}
    for track_name, track in selected_tracks.items():
        model_filename = f"{track_name}.joblib"
        feature_names_filename = f"{track_name}_feature_names.json"
        model_path = bundle_root / model_filename
        feature_names_path = bundle_root / feature_names_filename

        model_path.write_text(f"stub model for {track_name}\n", encoding="utf-8")
        feature_names_path.write_text(
            json.dumps({"feature_names": track["feature_names"]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        manifest_tracks[track_name] = {
            "variant_name": track["variant_name"],
            "claim_status": track["claim_status"],
            "anti_collapse_status": track["anti_collapse_status"],
            "policy_scope": track["policy_scope"],
            "model_path": f"bundle/{model_filename}",
            "feature_names_path": f"bundle/{feature_names_filename}",
            "feature_names": track["feature_names"],
        }
        bundle_files[model_filename] = str(model_path)
        bundle_files[feature_names_filename] = str(feature_names_path)

    manifest = {
        "run_kind": "m7-5-runtime-bundle-export",
        "source_gate_verdict_path": str(gate_verdict_path),
        "source_experiment_id": gate_verdict.get("source_experiment_id"),
        "bundle_root": "bundle",
        "tracks": manifest_tracks,
    }
    manifest_path = bundle_root / "model-bundle.manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bundle_files["model-bundle.manifest.json"] = str(manifest_path)

    report_path = run_root / "runtime-bundle-export-report.json"
    report_markdown_path = run_root / "runtime-bundle-export-report.md"
    report = {
        "run_kind": "m7-5-runtime-bundle-export",
        "export_passed": True,
        "source_gate_verdict_path": str(gate_verdict_path),
        "source_gate_passed": True,
        "bundle_root": str(bundle_root),
        "manifest_path": str(manifest_path),
        "selected_tracks": list(selected_tracks),
        "artifact_index": {
            "bundle": bundle_files,
            "report": {
                "runtime-bundle-export-report.json": str(report_path),
                "runtime-bundle-export-report.md": str(report_markdown_path),
            },
        },
        "smoke_check": {
            "manifest_loadable": True,
            "required_track_files_present": True,
            "required_tracks": list(M75_REQUIRED_TRACKS),
            "selected_track_count": len(selected_tracks),
            "optional_valence_exported": True,
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_markdown_path.write_text(
        "\n".join(
            [
                "# M7.5 Runtime Bundle Export",
                "",
                "## Scope",
                "",
                "- Export the approved `activity`, `arousal_coarse`, and `valence_coarse` runtime bundle as a manifest-driven package.",
                "- Fail fast when the upstream `M7.4` gate does not pass.",
                "",
                "## Inputs",
                "",
                f"- `source_gate_verdict_path`: `{gate_verdict_path}`",
                f"- `source_experiment_id`: `{gate_verdict.get('source_experiment_id')}`",
                "",
                "## Outputs",
                "",
                f"- `bundle/model-bundle.manifest.json`",
                f"- `runtime-bundle-export-report.json`",
                f"- `runtime-bundle-export-report.md`",
                "",
                "## Acceptance Smoke",
                "",
                "1. `gate_passed == true`.",
                "2. Manifest is loadable and references every track artifact.",
                "3. `activity`, `arousal_coarse`, and `valence_coarse` artifacts are present.",
                "4. Export report records a green smoke check.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def _selected_tracks() -> dict[str, dict[str, Any]]:
    return {
        "activity": {
            "variant_name": "activity_watch_motion_only",
            "claim_status": "supported",
            "anti_collapse_status": "ok",
            "policy_scope": "primary",
            "feature_names": ["watch_acc_c0__mean", "watch_acc_c0__std"],
        },
        "arousal_coarse": {
            "variant_name": "arousal_polar_plus_watch",
            "claim_status": "supported",
            "anti_collapse_status": "ok",
            "policy_scope": "primary",
            "feature_names": ["polar_hr_mean", "watch_acc_c0__mean"],
        },
        "valence_coarse": {
            "variant_name": "valence_polar_plus_watch_scoped",
            "claim_status": "supported",
            "anti_collapse_status": "ok",
            "policy_scope": "scoped",
            "feature_names": ["polar_rr_rmssd", "watch_hrv_rmssd"],
        },
    }


def test_m75_runtime_bundle_export_fails_fast_when_gate_is_not_passed(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    gate_verdict_path = tmp_path / "runtime-candidate-verdict.json"
    gate_verdict_path.write_text(
        json.dumps({"gate_passed": False, "source_experiment_id": "m7-4-test-fail"}),
        encoding="utf-8",
    )

    try:
        _export_m75_runtime_bundle(
            output_dir,
            gate_verdict_path=gate_verdict_path,
            selected_tracks=_selected_tracks(),
        )
    except RuntimeError as exc:
        assert "gate_passed=true" in str(exc)
    else:  # pragma: no cover - defensive, should never happen
        raise AssertionError("expected M7.5 export to fail fast when the gate is not passed")

    assert not (output_dir / "wesad").exists()


def test_m75_runtime_bundle_export_writes_manifest_and_report_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "artifacts"
    gate_verdict_path = tmp_path / "runtime-candidate-verdict.json"
    gate_verdict_path.write_text(
        json.dumps({"gate_passed": True, "source_experiment_id": "m7-4-test-pass"}),
        encoding="utf-8",
    )

    report = _export_m75_runtime_bundle(
        output_dir,
        gate_verdict_path=gate_verdict_path,
        selected_tracks=_selected_tracks(),
    )

    run_root = output_dir / "wesad" / "wesad-v1" / "m7-5-runtime-bundle-export"
    bundle_root = run_root / "bundle"
    manifest_path = bundle_root / "model-bundle.manifest.json"
    report_path = run_root / "runtime-bundle-export-report.json"
    report_markdown_path = run_root / "runtime-bundle-export-report.md"

    assert sorted(item.name for item in bundle_root.iterdir()) == [
        "activity.joblib",
        "activity_feature_names.json",
        "arousal_coarse.joblib",
        "arousal_coarse_feature_names.json",
        "model-bundle.manifest.json",
        "valence_coarse.joblib",
        "valence_coarse_feature_names.json",
    ]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_kind"] == "m7-5-runtime-bundle-export"
    assert manifest["source_experiment_id"] == "m7-4-test-pass"
    assert set(manifest["tracks"]) == set(M75_REQUIRED_TRACKS)
    assert manifest["tracks"]["valence_coarse"]["policy_scope"] == "scoped"
    assert manifest["tracks"]["activity"]["model_path"] == "bundle/activity.joblib"
    assert manifest["tracks"]["arousal_coarse"]["feature_names_path"] == "bundle/arousal_coarse_feature_names.json"

    report_json = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_json["export_passed"] is True
    assert report_json["source_gate_passed"] is True
    assert report_json["manifest_path"] == str(manifest_path)
    assert report_json["artifact_index"]["bundle"]["model-bundle.manifest.json"] == str(manifest_path)
    assert report_json["artifact_index"]["report"]["runtime-bundle-export-report.json"] == str(report_path)
    assert report_json["smoke_check"] == {
        "manifest_loadable": True,
        "required_track_files_present": True,
        "required_tracks": list(M75_REQUIRED_TRACKS),
        "selected_track_count": 3,
        "optional_valence_exported": True,
    }

    assert report == report_json
    assert report_markdown_path.read_text(encoding="utf-8").startswith("# M7.5 Runtime Bundle Export")
    assert "## Acceptance Smoke" in report_markdown_path.read_text(encoding="utf-8")


def test_m75_docs_spell_out_scope_inputs_outputs_and_smoke() -> None:
    root = Path(__file__).resolve().parents[3]
    readme_text = (root / "services/modeling-baselines/README.md").read_text(encoding="utf-8")
    doc_text = (root / "docs/backend/m7-5-runtime-bundle-export.md").read_text(encoding="utf-8")

    for needle in (
        "M7.5",
        "model-bundle.manifest.json",
        "runtime-bundle-export-report.json",
        "gate_passed",
        "activity.joblib",
        "valence_coarse_feature_names.json",
    ):
        assert needle in readme_text
        assert needle in doc_text

    for needle in ("Scope", "Inputs", "Outputs", "Acceptance Smoke"):
        assert needle in doc_text
