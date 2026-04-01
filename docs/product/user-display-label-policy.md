# Политика `user_display_label` (live-inference-api)

## Назначение

Поле **`user_display_label`** в ответе WebSocket (`type: inference`) и в **`POST .../replay/infer`** — короткая русскоязычная подпись для UI. Оно вычисляется на хосте **`live-inference-api`** из уже выданных полей семантики, **без второго вызова модели** и без изменения `inference-api` (`POST /v1/predict`).

Источник правды по смыслу аффекта для исследований по-прежнему задаётся в `docs/research/label-specification.md` (self-report). Подпись — **UX-слой**, а не клинический диагноз.

## Приоритет разрешения

1. Если **`derived_state`** один из: `calm_rest`, `active_movement`, `physical_load`, `possible_stress`, `positive_activation`, `negative_activation` — используется фиксированная формулировка (см. реализацию `compute_user_display_label` в `services/live-inference-api/src/live_inference_api/user_display_label.py`), с уточнениями по `valence` / `arousal` где задано.
2. Если **`activity_class`** или **`arousal_coarse`** равны `unknown` — подпись: «Мало сигнала для подписи».
3. Если **`derived_state` == `uncertain_state`** — таблица-матрица по сочетанию `activity_class` × `arousal` × `valence` (функция `_matrix_label`).
4. Если **`valence_coarse` == `unknown`** (valence отключён политикой или моделью) — упрощённые строки без валентности (`_without_valence`).
5. Иначе — детализация по **`rest`/`recovery`**, **`movement`**, **`physical_load`**, **`cognitive`**, **`mixed`**.

## Сводная матрица (для `uncertain_state` и fallback)

| activity_class | arousal | valence   | Пример подписи        |
| -------------- | ------- | --------- | --------------------- |
| rest/recovery  | low     | negative  | Покой, негативный фон |
| rest/recovery  | low     | neutral   | Покой                 |
| rest/recovery  | low     | positive  | Покой, позитивный фон |
| movement       | *       | negative  | Движение, негатив   |
| movement       | *       | positive  | Движение, позитив   |
| movement       | *       | neutral   | Движение            |
| physical_load  | *       | *         | Нагрузка            |
| cognitive      | *       | *         | Когнитивная активность |

Точные строки могут слегка отличаться по веткам `derived_state`; при смене копирайта править **`user_display_label.py`** и этот документ согласованно.

## Изменение политики

1. Обновить `compute_user_display_label` и unit-тесты в `services/live-inference-api/tests/test_user_display_label.py`.
2. При необходимости синхронизировать `contracts/http/live-inference-api.openapi.yaml` (поле уже в схеме).
3. Клиентам (on-go-ios): читать **`user_display_label`** из JSON inference; при отсутствии ключа — fallback на локальную таблицу или скрытие подписи.
