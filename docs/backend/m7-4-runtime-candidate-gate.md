# M7.4 - Runtime Candidate Gate (Polar-first)

## Scope

`M7.4` converts `M7.3` training outputs into a machine-readable runtime promotion verdict.

Artifacts:

1. `runtime-candidate-verdict.json`
2. `runtime-candidate-report.md`

Source:

1. `M7.3` `evaluation-report.json`
2. `M7.3` `anti_collapse_summary`
3. `M7.3` `winner_by_track`

## Gate Rules (v1)

Per track (`activity`, `arousal_coarse`, `valence_coarse`):

1. winner exists;
2. `anti_collapse_status == ok`;
3. `claim_status == supported`.

Global:

1. `anti_collapse_summary.passed == true`;
2. `flagged_rows` must be empty.

Decision:

1. `pass` -> allow `P5 Runtime Bundle Export`;
2. `fail` -> stay in `P4` remediation loop.

## Executed Run

Run:

1. `run_kind = m7-4-runtime-candidate-gate`
2. `experiment_id = m7-4-runtime-candidate-gate-20260329T165340Z`

Input:

1. `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-3-polar-first-training-dataset-build/evaluation-report.json`

Output:

1. `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-4-runtime-candidate-gate/runtime-candidate-verdict.json`
2. `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-4-runtime-candidate-gate/runtime-candidate-report.md`

## Result

Verdict:

1. `gate_verdict = fail`
2. `gate_passed = false`

Observed issues:

1. `global_issues`: `anti_collapse_summary_failed`, `flagged_rows_present`
2. track failure: `arousal_coarse` -> `claim_not_supported`
3. `M7.3` flagged anti-collapse row remains (`polar_only/activity`, `near_constant`)

## Next

`M7.4.1` remediation loop is documented in [m7-4-1-remediation-loop.md](./m7-4-1-remediation-loop.md).

It should eliminate the anti-collapse issue on `polar_only/activity`, improve the `arousal_coarse` candidate to `claim_status=supported`, and rerun `M7.3` + `M7.4` until the gate verdict becomes `pass`.
