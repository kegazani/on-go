from __future__ import annotations

import pickle
from pathlib import Path

from dataset_registry.wesad import import_wesad_dataset


def _write_labels(path: Path, labels: list[int]) -> None:
    path.write_text("\n".join(str(item) for item in labels) + "\n", encoding="utf-8")


def test_import_wesad_creates_unified_artifacts_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "wesad"
    output = tmp_path / "out"

    (source / "S2").mkdir(parents=True)
    (source / "S3").mkdir(parents=True)

    _write_labels(source / "S2" / "labels.csv", [1, 1, 1, 2])
    _write_labels(source / "S3" / "labels.csv", [2, 2, 2, 3])

    result = import_wesad_dataset(
        source_dir=source,
        output_dir=output,
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        source_uri="https://example.org/wesad",
        source_license="research-only",
    )

    assert result.record.dataset_id == "wesad"
    assert result.record.subject_count == 2
    assert result.record.session_count == 2
    assert result.record.row_count == 2

    dataset_root = output / "wesad" / "wesad-v1"
    assert (dataset_root / "unified" / "subjects.jsonl").exists()
    assert (dataset_root / "unified" / "sessions.jsonl").exists()
    assert (dataset_root / "unified" / "segment-labels.jsonl").exists()
    assert (dataset_root / "manifest" / "dataset-metadata.json").exists()
    assert (dataset_root / "manifest" / "split-manifest.json").exists()


def test_import_wesad_fails_without_subjects(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir(parents=True)

    try:
        import_wesad_dataset(
            source_dir=source,
            output_dir=tmp_path / "out",
            dataset_version="wesad-v1",
            preprocessing_version="e2-v1",
            source_uri=None,
            source_license=None,
        )
    except ValueError as exc:
        assert "No subject directories" in str(exc)
        return

    raise AssertionError("import_wesad_dataset should fail when source has no S* directories")


def test_import_wesad_from_pickle_preserves_contiguous_segments(tmp_path: Path) -> None:
    source = tmp_path / "wesad"
    output = tmp_path / "out"
    subject_dir = source / "S2"
    subject_dir.mkdir(parents=True)

    payload = {
        "subject": "S2",
        "label": [0, 0, 1, 1, 0, 2, 2, 2, 6, 6, 0, 4, 4],
        "signal": {},
    }
    with (subject_dir / "S2.pkl").open("wb") as handle:
        pickle.dump(payload, handle, protocol=2)

    result = import_wesad_dataset(
        source_dir=source,
        output_dir=output,
        dataset_version="wesad-v1",
        preprocessing_version="e2-v1",
        source_uri=None,
        source_license=None,
    )

    assert result.record.row_count == 4
    assert [item.source_label_value for item in result.segment_labels] == ["1", "2", "6", "4"]
    assert [item.source_segment_start_index for item in result.segment_labels] == [2, 5, 8, 11]
    assert [item.source_segment_end_index for item in result.segment_labels] == [3, 7, 9, 12]
    assert [item.source_sample_count for item in result.segment_labels] == [2, 3, 2, 2]
    assert result.segment_labels[2].activity_label == "unknown"
    assert result.segment_labels[2].confidence == 0.3
    assert result.segment_labels[0].activity_label == "seated_rest"
    assert any("unmapped source labels [6]" in warning for warning in result.warnings)
