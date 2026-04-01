# HTTP Contracts

Здесь должны храниться HTTP/API-контракты:

- OpenAPI спецификации;
- схемы запросов и ответов;
- версии API;
- правила генерации клиентских SDK.

Swift-клиент должен опираться на артефакты из этого каталога через CI/CD,
а не на ручное копирование моделей.

Текущие контракты для backend HTTP/API:

- `raw-session-ingest.openapi.yaml` — API загрузки raw session package (`C1`).
- `raw-session-replay.openapi.yaml` — API replay manifest и replay windows (`D1`).
- `live-inference-api.openapi.yaml` — WS live inference для capture-only `stream_batch`.
