# Conv node0004 v16 rule-drift content-neutral revalidation

## Scope and immutable package identity

- Package: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.zip`
- ZIP SHA-256 before: `e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1`
- ZIP SHA-256 after: `e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1`
- ZIP bytes changed: `false`
- Sidecar SHA-256: `b12b0313120e758966517f84ebc7ec70261f0f93cf3db936a9eddad419ba1d71`
- Old in-package server-rule receipt:
  `0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a`
- Current server rule:
  `.agents/rules/服务器测试包生成规则.md`
  SHA-256 `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
- New rule:
  `CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001`

No node0004 numeric analysis or workload rebuild was performed. The ZIP, sidecar,
runner, manifest, observer, return schema, and package-local negative-control
assets were not modified.

## Applicability adjudication

Status: `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`.

The new rule's gated-domain precondition does not apply to the v16 canonical
progress path:

1. The qualified external request/read-data/write-data counters used by
   `return_hang_diag_current_progress` are incremented in the
   `u_NDP_Top_new.clk_db` observer block.
2. The progress snapshot cadence, stall windows, heartbeat source, and all calls
   to `return_hang_diag_emit_decision` are also owned by the same `clk_db`
   block.
3. The only modulo print gate in the canonical path is
   `return_obs_active_cycles % return_hang_diag_sample_cycles`; both operands
   are owned by that same `clk_db` block.
4. No `return_obs_sg_*` counter enters the monotonic progress sum, modulo/equality
   gate, or canonical decision record. The SG-domain counters are bounded,
   auxiliary event context only.
5. The active RTLSIM clock generator proves both `clk_db_out` and `clk_sg_out`
   are free-running `forever` loops. The top binds those outputs directly to
   `clk_db` and `clk_sg`.
6. The observer is read-only and does not drive DUT clock, ready/backpressure,
   timeout, or qualified counter semantics.

Therefore the new rule requires no package payload, runner behavior, manifest
machine-contract, negative-control asset, or return-schema change. The external
receipt is the authorized content-neutral bridge; it does not rewrite the
historical in-package receipt.

## Machine receipt and validator

- Receipt:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.rule_drift_507ca909.json`
- Receipt SHA-256:
  `cfc12f55e51eed1e4deb865a13d58170720bddc56007298caf4acccad659a23b`
- Validator:
  `tools/validate_node0004_v16_rule_drift_507ca909.py`
- Validator SHA-256:
  `baffa5dc658a251dedf21de0434351542cfcd5e0702bbe4834dda60c0efe3964`
- Command:
  `.venv\Scripts\python.exe tools/validate_node0004_v16_rule_drift_507ca909.py --output artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.rule_drift_507ca909.json`
- Exit code: `0`
- Deterministic repeat: receipt SHA matched on two consecutive executions.

Source-current-match evidence:

- `NDP_copy01/rtl/clk_freq.sv` SHA-256
  `c95d81934c9adadb1a2a9762c0c3b2dcf8e09021b4df69f4ef4a212a30a78cdd`
- `NDP_copy01/rtl/NDP_Top_phy.sv` SHA-256
  `0ef2f75c0b04462c9fe4054130b515ff11caa8e97d2c8d89cb9a9307cfa0d277`

## Negative controls

All negative controls failed closed:

| Negative control | Validator exit |
| --- | ---: |
| Cross-domain SG counter used as the unique modulo emitter | 1 |
| SG-domain counter injected into canonical monotonic progress | 1 |
| Canonical emitter moved from `clk_db` to `clk_sg` | 1 |
| Free-running `clk_db` proof removed | 1 |

## Release boundary

- `PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`
- Original v16 identity remains the only runnable candidate.
- No server action was performed.
- E3/E4/E5 remain unchanged and require a formal dynamic return.
