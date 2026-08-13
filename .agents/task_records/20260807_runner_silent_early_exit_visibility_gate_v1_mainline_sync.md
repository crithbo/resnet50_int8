# Runner silent early-exit visibility gate v1 — mainline sync

Date: 2026-08-07

## Result

Mainline accepted the rule-audit verdict as a narrow non-synonymous delta and
implemented `CDA-SERVER-RUNNER-NONZERO-EXIT-STDERR-VISIBILITY-001`.

The rule applies as a blocking gate only to next-fresh packages or runner
changed-surfaces. Every package-owned nonzero early exit must emit an exact-runner
stderr diagnostic binding package identity, numeric code, failed-gate description,
and recovery/evidence hint. The shared finalizer must emit a package/exit-bound
final status. Frozen byte-equal runners use `receipt_reuse`.

## Shared implementation

- validator:
  `tools/validate_server_package_runtime_layout.py`
  SHA256 `da579f2644c611b53871fa1f099559cacc5a2ea029a15d01bb6e8b105fa024c6`
- tests:
  `tests/test_server_package_runtime_layout.py`
  SHA256 `0884d6bf38490ae11bb134d7250e5776630af0df7473c447554aaa05a923bc78`
- fixtures:
  `fixtures/server_package_runtime_layout_v1/cases.json`
  SHA256 `48d8ae33fb4bcb9a51e7a0ef102b51a9aedf11f3b228a4ada2c1d8cf57e6a0e4`
- registry:
  `contracts/server_package_build_gate_registry_v1.json`
  SHA256 `cce3165956a181a16f9a113f44a6da549f1ea7c387b2895675a5afdc29409dbe`

These four files are byte-exact with the shared owner snapshot.

## Mainline rule receipts

- server rule:
  SHA256 `a8f628413367805d5fe9822233b39460e5386b1ecaf321ba050546a96cd843d8`
- generation index:
  SHA256 `bded239d169c4768ca0c54e93a90eeb0a9285955252995afaf098322a00bd688`
- convergence optimizer rule:
  SHA256 `e52ab12c78edca3ada0eabf26a323b3da7a9fb6dc0bb07dab594793eee8e87ff`

## Validation

- `py_compile`: PASS
- runtime-layout and pipeline tests: 17/17 PASS
- exact v62: expected FAIL_CLOSED, `runner_fail=0`, bare nonzero exits=16
- exact v63: PASS, `runner_fail=17`, bare nonzero exits=0
- `git diff --check`: PASS

The mainline v62/v63 receipts differ from the source-worktree receipt SHA only
because the report records the absolute local helper-reference path. Their
semantic results and all content hashes are identical.

Machine report:
`artifacts/operator_config_validation/r5-runner-early-exit-visibility-gate-v1/mainline_report.json`.

## Boundary

No current package was rebuilt or modified. No upload, server run, lease, RTL,
config, numeric, workload, production compile, simulation, natural-terminal,
formal-D, E4, or E5 action occurred.
