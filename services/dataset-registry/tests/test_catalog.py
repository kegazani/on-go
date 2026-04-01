from __future__ import annotations

from pathlib import Path

from dataset_registry.catalog import list_catalog, validate_source


def test_catalog_contains_all_prioritized_datasets() -> None:
    ids = {item["dataset_id"] for item in list_catalog()}
    assert ids == {"wesad", "emowear", "grex", "dapper"}


def test_validate_wesad_source_passes_with_expected_layout(tmp_path: Path) -> None:
    (tmp_path / "S2").mkdir(parents=True)
    (tmp_path / "S2" / "labels.csv").write_text("1\n2\n", encoding="utf-8")

    result = validate_source("wesad", tmp_path)
    assert result.status == "passed"


def test_validate_unknown_dataset_fails(tmp_path: Path) -> None:
    result = validate_source("unknown", tmp_path)
    assert result.status == "failed"
