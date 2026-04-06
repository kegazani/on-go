from __future__ import annotations

from typing import Any

_L2_TRACK_KEYS = ("activity", "arousal_coarse", "valence_coarse")


def apply_adaptation_l2(
    pred: dict[str, str],
    adaptation_state: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    out = dict(pred)
    meta: dict[str, Any] = {"applied": False}
    if not adaptation_state or not isinstance(adaptation_state, dict):
        meta["reason"] = "no_adaptation_state"
        return out, meta
    level = str(adaptation_state.get("active_personalization_level") or "none").strip().lower()
    if level not in ("light", "full"):
        meta["reason"] = "level_skips_l2"
        meta["active_personalization_level"] = level
        return out, meta
    raw_l2 = adaptation_state.get("l2_calibration")
    if not isinstance(raw_l2, dict) or not raw_l2:
        meta["reason"] = "no_l2_calibration"
        return out, meta
    match_req = raw_l2.get("global_model_reference_match")
    if match_req is not None and str(match_req).strip():
        gref = str(adaptation_state.get("global_model_reference") or "").strip()
        if gref != str(match_req).strip():
            meta["reason"] = "global_model_reference_mismatch"
            meta["expected"] = str(match_req).strip()
            meta["actual"] = gref
            return out, meta
    maps = raw_l2.get("output_label_maps")
    if not isinstance(maps, dict) or not maps:
        meta["reason"] = "no_output_label_maps"
        return out, meta
    changed: dict[str, dict[str, str]] = {}
    for track in _L2_TRACK_KEYS:
        if track not in out:
            continue
        track_map = maps.get(track)
        if not isinstance(track_map, dict):
            continue
        before = str(out[track])
        mapped = track_map.get(before)
        if mapped is None:
            continue
        after = str(mapped)
        if after != before:
            out[track] = after
            changed[track] = {"from": before, "to": after}
    if not changed:
        meta["reason"] = "maps_no_effect"
        meta["applied"] = False
        return out, meta
    meta["applied"] = True
    meta["version"] = raw_l2.get("version", "per-l2-v1")
    meta["changed"] = changed
    meta["active_personalization_level"] = level
    return out, meta
