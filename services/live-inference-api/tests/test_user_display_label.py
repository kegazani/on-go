from __future__ import annotations

from live_inference_api.user_display_label import compute_user_display_label


def test_derived_calm_rest_default() -> None:
    assert (
        compute_user_display_label(
            activity_class="rest",
            arousal_coarse="low",
            valence_coarse="neutral",
            derived_state="calm_rest",
        )
        == "Спокойный отдых"
    )


def test_derived_active_movement() -> None:
    assert (
        compute_user_display_label(
            activity_class="movement",
            arousal_coarse="low",
            valence_coarse="neutral",
            derived_state="active_movement",
        )
        == "Лёгкая активность"
    )


def test_uncertain_matrix() -> None:
    out = compute_user_display_label(
        activity_class="movement",
        arousal_coarse="medium",
        valence_coarse="negative",
        derived_state="uncertain_state",
    )
    assert out == "Движение, негатив"


def test_unknown_activity() -> None:
    assert (
        compute_user_display_label(
            activity_class="unknown",
            arousal_coarse="low",
            valence_coarse="neutral",
            derived_state="uncertain_state",
        )
        == "Мало сигнала для подписи"
    )
