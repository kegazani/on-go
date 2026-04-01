# src

Исходный код `dataset-registry`:

1. `models.py` — schema dataset registry и unified dataset artifacts;
2. `registry.py` — JSONL-backed registry storage;
3. `catalog.py` — каталог внешних датасетов, source-validation и deep inspection rules;
4. `wesad.py` — adapter первого импорта `WESAD` в unified schema;
5. `main.py` — CLI (`register`, `list`, `dataset-catalog`, `validate-source`, `inspect-source`, `import-wesad`).
