# Personalization Contracts

Контракты personalization-контура:

1. `user-profile.schema.json` - канонический профиль пользователя для H1/H2/H3.
2. `personalization-feature-contract.schema.json` - контракт входов personalization pipeline.
3. `valence-scoped-policy.schema.json` - контракт operational policy для scoped режима `valence` (E2.10).

Контракты нужны для:

1. единообразного сохранения calibration статистик;
2. проверки допустимости personalization budget;
3. воспроизводимого сравнения `global` vs `personalized` run-ов.
