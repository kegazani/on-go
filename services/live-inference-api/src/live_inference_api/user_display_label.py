from __future__ import annotations


def compute_user_display_label(
    *,
    activity_class: str,
    arousal_coarse: str,
    valence_coarse: str,
    derived_state: str,
) -> str:
    ds = str(derived_state or "").strip().lower()
    ac = str(activity_class or "").strip().lower()
    ar = str(arousal_coarse or "").strip().lower()
    va = str(valence_coarse or "").strip().lower()

    if ds == "calm_rest":
        if va == "negative":
            return "Спокойствие, настроение ниже нейтраля"
        if va == "positive":
            return "Спокойствие, комфортное состояние"
        return "Спокойный отдых"

    if ds == "active_movement":
        if ar == "high":
            return "Активность с высокой активацией"
        if va == "negative":
            return "Движение на негативном фоне"
        if va == "positive":
            return "Лёгкая активность, позитив"
        return "Лёгкая активность"

    if ds == "physical_load":
        return "Физическая нагрузка"

    if ds == "possible_stress":
        return "Возможное напряжение"

    if ds == "positive_activation":
        return "Позитивное возбуждение"

    if ds == "negative_activation":
        return "Негативное напряжение"

    if ac == "unknown" or ar == "unknown":
        return "Мало сигнала для подписи"

    if ds == "uncertain_state":
        return _matrix_label(ac, ar, va)

    if va == "unknown":
        return _without_valence(ac, ar)

    if ac in {"rest", "recovery"}:
        if ar == "low" and va == "negative":
            return "Расслабление, неприятный фон"
        if ar == "low" and va == "positive":
            return "Расслабление, приятный фон"
        if ar == "low":
            return "Низкая активация, нейтрально"
        if ar == "medium":
            return "Умеренная активация в покое"
        if ar == "high":
            return "Высокая активация в покое"

    if ac == "movement":
        if ar == "low" and va == "negative":
            return "Движение, спокойный негатив"
        if ar == "low" and va == "positive":
            return "Движение, лёгкий позитив"
        if ar == "low":
            return "Движение, низкая активация"
        if ar == "medium":
            return "Движение, средняя активация"
        if ar == "high":
            return "Движение, высокая активация"

    if ac == "physical_load":
        if ar in {"medium", "high"}:
            return "Интенсивная нагрузка"
        return "Физическая активность"

    if ac == "cognitive":
        if ar == "high" and va == "negative":
            return "Напряжённая когнитивная задача"
        if ar == "high":
            return "Сильная когнитивная активация"
        return "Когнитивная задача"

    if ac == "mixed":
        return "Смешанное состояние"

    return _matrix_label(ac, ar, va)


def _without_valence(ac: str, ar: str) -> str:
    if ac == "rest" or ac == "recovery":
        if ar == "low":
            return "Покой"
        if ar == "medium":
            return "Покой, средняя активация"
        return "Покой, активация неясна"
    if ac == "movement":
        if ar == "medium":
            return "Движение, умеренная активация"
        if ar == "high":
            return "Движение, высокая активация"
        return "Движение"
    if ac == "physical_load":
        return "Нагрузка"
    if ac == "cognitive":
        if ar == "high":
            return "Когнитивная нагрузка"
        return "Когнитивная задача"
    if ac == "recovery":
        return "Восстановление"
    if ac == "mixed":
        return "Переход между состояниями"
    return "Нейтрально"


def _matrix_label(ac: str, ar: str, va: str) -> str:
    if ac in {"rest", "recovery"}:
        if ar == "low" and va == "negative":
            return "Покой, негативный фон"
        if ar == "low" and va == "positive":
            return "Покой, позитивный фон"
        if ar == "low":
            return "Покой"
        if ar == "medium":
            return "Умеренная активация, покой"
        if ar == "high":
            return "Высокая активация в покое"
    if ac == "movement":
        if va == "negative":
            return "Движение, негатив"
        if va == "positive":
            return "Движение, позитив"
        return "Движение"
    if ac == "physical_load":
        return "Нагрузка"
    if ac == "cognitive":
        return "Когнитивная активность"
    if ac == "mixed":
        return "Смешанное состояние"
    return "Состояние неясно"
