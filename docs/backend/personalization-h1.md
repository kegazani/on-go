# H1 - Схема профиля пользователя

## Статус

- Step ID: `H1`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

Зафиксировать профиль пользователя для personalization-фазы, включая подробный контракт входов и research-grade артефакты, пригодные для последующих `H2/H3` и презентации.

## Что сделано

1. Создан канонический JSON Schema профиля пользователя:
   - `contracts/personalization/user-profile.schema.json` (`h1-v1`).
2. Создан контракт входов personalization pipeline:
   - `contracts/personalization/personalization-feature-contract.schema.json` (`h1-feature-contract-v1`).
3. Зафиксирован исследовательский документ со структурой профиля, leakage guards и candidate mapping из `G3.1/G3.2`:
   - `docs/research/personalization-user-profile-schema.md`.
4. Собран machine-readable и presentation-ready H1 пакет:
   - `data/artifacts/personalization/h1-profile-schema/evaluation-report.json`
   - `model-comparison.csv`
   - `per-subject-metrics.csv`
   - `research-report.md`
   - `plots/` (3 графика)

## Ключевой результат

`H1` формализовал personalization contract layer: теперь для каждого субъекта есть единый profile format, фиксированный calibration budget contract, правила качества/утечки и выбор глобальных кандидатов для запуска `H2`.

## Ограничения

1. На `H1` не выполнялся новый тренировочный personalization run; шаг фиксирует контракт и protocol layer.
2. Источники `EmoWear/DAPPER` с proxy labels остаются вспомогательными и не должны быть claim-grade основой в `H2/H3`.

## Следующий шаг

`H2 - Light personalization`
