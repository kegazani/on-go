# Live Streaming Integration (Option A)

Как подключить фронт (on-go-ios) к live-inference-api для отображения параметров и состояния в реальном времени.

## Архитектура

```
[iPhone + Watch + Polar] → stream batches → live-inference-api (WebSocket)
                                    ↓
                            feature extraction
                                    ↓
                            inference (activity, arousal, valence)
                                    ↓
                            push to client → [UI]
```

## Требования

1. Backend: `live-inference-api` запущен (порт 8120)
2. Model bundle в `/models` (тот же, что для inference-api)
3. on-go-ios: WebSocket-клиент + отправка stream batches во время записи

## WebSocket endpoint

- **Backend-only smoke checks:** `ws://localhost:8120/ws/live`
- **Real-device capture:** `ws://<MAC_IP>:8120/ws/live`

## Формат сообщений

### Отправка сэмплов (client → server)

При получении stream batch из real-device capture (Polar HR, Watch sensors) отправлять:

```json
{
  "type": "stream_batch",
  "stream_name": "watch_heart_rate",
  "source_mode": "live",
  "samples": [
    {"offset_ms": 0, "values": {"hr_bpm": 72}},
    {"offset_ms": 5000, "values": {"hr_bpm": 74}}
  ]
}
```

`watch_accelerometer`:

```json
{
  "type": "stream_batch",
  "stream_name": "watch_accelerometer",
  "source_mode": "live",
  "samples": [
    {"offset_ms": 0, "values": {"acc_x_g": 0.1, "acc_y_g": 0.0, "acc_z_g": 1.0}}
  ]
}
```

`offset_ms` — смещение от начала сессии в миллисекундах.
`source_mode` обязателен для `live-inference-api`; `live` проходит gate, `simulated`/`unknown`/`replay` отклоняются. Для raw session replay используй `replay-service`.

### Получение inference (server → client)

```json
{
  "type": "inference",
  "window_start_ms": 0,
  "window_end_ms": 15000,
  "activity": "baseline",
  "arousal_coarse": "low",
  "valence_coarse": "",
  "feature_count": 25
}
```

`valence_coarse` пустой, пока модель valence не загружена в bundle.

## Интеграция в on-go-ios

1. При старте real-device сессии: открыть WebSocket к `ws://<host>:8120/ws/live`
2. В callback `StreamBatch` (Polar/Watch): сериализовать samples и отправить `stream_batch`
3. Обработчик входящих сообщений: при `type == "inference"` обновить UI (activity, arousal_coarse, valence_coarse)
4. При остановке сессии: закрыть WebSocket

## Переменные окружения

В `project.yml` (OnGoCapture scheme) уже добавлено:

| Переменная | Значение (устройство) |
|------------|------------------------|
| ON_GO_LIVE_INFERENCE_WS_URL | ws://192.168.1.109:8120/ws/live |

Для backend-only smoke checks можно использовать `ws://localhost:8120/ws/live`, но поддерживаемый capture-путь требует физическое устройство.

## Ограничения

- Нужны оба stream: `watch_heart_rate` и `watch_accelerometer` для inference
- Окно по умолчанию: 15 с, шаг 5 с
- Модель обучена на WESAD (watch_acc, watch_bvp, watch_eda, watch_temp). EDA/TEMP из наших устройств нет — заполняются нулями. Качество может отличаться от batch-результатов
