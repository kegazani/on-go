from __future__ import annotations

import json
from pathlib import Path

from dataset_registry.models import DatasetRecord


class DatasetRegistry:
    def __init__(self, registry_path: Path) -> None:
        self._registry_path = registry_path

    def upsert(self, record: DatasetRecord) -> None:
        existing = self.list_records()
        filtered = [
            item
            for item in existing
            if not (item.dataset_id == record.dataset_id and item.dataset_version == record.dataset_version)
        ]
        filtered.append(record)

        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        with self._registry_path.open("w", encoding="utf-8") as output:
            for item in sorted(filtered, key=lambda item: (item.dataset_id, item.dataset_version)):
                output.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def list_records(self) -> list[DatasetRecord]:
        if not self._registry_path.exists():
            return []

        records: list[DatasetRecord] = []
        for raw_line in self._registry_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            records.append(DatasetRecord.model_validate(payload))

        return records
