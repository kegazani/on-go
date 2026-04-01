# M7.4.1 Remediation Loop

## Status

- Step ID: `M7.4.1`
- Status: `spec`
- Date: `2026-03-29`
- Scope: repair loop after an `M7.4` fail verdict.

## Goal

Close the loop between `M7.3` training and `M7.4` runtime promotion until the candidate is claim-safe.

## Inputs

1. `M7.3` `evaluation-report.json`
2. `M7.4` `runtime-candidate-verdict.json`
3. `M7.4` `runtime-candidate-report.md`

## Remediation Loop

1. Fix the flagged `polar_only/activity` anti-collapse issue first.
2. Raise `arousal_coarse` to a `supported` claim status.
3. Rerun `M7.3` to regenerate the ablation matrix and the source report.
4. Rerun `M7.4` against the fresh `M7.3` report.
5. Repeat until the gate passes.

## Completion Criteria

The loop is complete only when all of the following are true:

1. `gate_verdict == pass`
2. `gate_passed == true`
3. `track_failures == []`
4. `global_issues == []`
5. `anti_collapse_summary.passed == true`
6. `anti_collapse_summary.flagged_rows == []`
7. every row in `track_winners` has `variant_name`, `claim_status == supported`, and `anti_collapse_status == ok`
8. `remediation_actions == []`

## Exit Rules

1. If any track has `missing_winner`, `claim_not_supported`, or `anti_collapse_not_ok`, stay in `P4 remediation loop`.
2. If `flagged_rows_present` or `anti_collapse_summary_failed` is present, do not promote the runtime bundle.
3. Only after the criteria above are satisfied should the run proceed to `P5 Runtime Bundle Export`.

## Artifacts

The loop should converge on a clean pair of artifacts:

1. `runtime-candidate-verdict.json`
2. `runtime-candidate-report.md`

## Notes

1. `M7.4.1` is a rerun cycle, not a new model family.
2. The completion criteria should be checked before any runtime bundle export.
3. If the source `M7.3` report changes, rerun `M7.4` from scratch rather than patching the existing verdict.
