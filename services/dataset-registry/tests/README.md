# Tests

Базовые unit-тесты шага `F2`:

1. upsert/list behavior JSONL-backed `dataset registry`;
2. `WESAD` import: генерация unified artifacts и manifest-файлов;
3. негативный сценарий: пустая source-папка без `S*` субъектов.
4. dataset catalog coverage и source-validation rules для `wesad/emowear/grex/dapper`.
5. `inspect-source`: проверка headers/layout/parseability для `WESAD`, `EmoWear`, `DAPPER`, `G-REx`.
