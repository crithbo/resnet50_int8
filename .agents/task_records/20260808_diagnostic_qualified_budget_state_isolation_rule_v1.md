# Diagnostic qualified-budget / state-budget isolation v1

Owner task: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Adjudication

`RULE_DELTA_PROPOSAL`
`CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001`
is accepted as a non-synonymous public-rule gap.

Current rules already required qualified transaction predicates, prohibited
level-as-progress, and required bounded ring/log storage. They did not require
heartbeat/state-transition retention to use an independent counter and budget.
Therefore GAP v50 could satisfy the existing event-qualification wording while
still consuming all 256 emitted records on slice0 state-only edges before the
first later-slice qualified GA output.

Classification:
`PACKAGE_LOCAL_DIAGNOSTIC_COVERAGE_BUDGET_ESCAPE /
EVIDENCE_INCOMPLETE_NOT_FUNCTIONAL_PROOF`.

This is not a config, numeric, hardware, or functional-RTL finding.

## Current-rule read receipts

Final source was read from the main workspace:

| path | SHA-256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/rules/生成前必读索引.md` | `d4ff32f162538574a0dd48402e299fa25a11fb95074352c19fcfb007ebb77603` |
| `.agents/rules/整网测试收敛优化专项规则.md` | `e52ab12c78edca3ada0eabf26a323b3da7a9fb6dc0bb07dab594793eee8e87ff` |
| `.agents/plan.md` | `4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13` |
| `.agents/rules/服务器测试包生成规则.md` | `7cf2cb4511cba04cb8a14d06473d67061deae64f602988d27053d8289c964b13` |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |

## Direct evidence

- GAP v50 source ZIP SHA-256:
  `96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d`;
- return SHA-256:
  `af493115127b0040d8bec83815d0e00d2fc90a7a9c559b11758ddb42982adfc2`;
- return analysis:
  `artifacts/operator_config_validation/r5-gap-node0071-v50-return-analysis/report.json`,
  SHA-256=`241ea0f4d823011433ca949a22c64093b99004eeb810122ca6a902d7297125b3`;
- exact observed failure: record `n=256` at `704646000 ps`; first
  later-slice GA output only at `739638000 ps`.

The v50 zero masks for later slices are therefore not functional evidence.

## Rule contract

Multi-stage/slice/lane observers must declare:

- `accounting_mode=SEPARATE_QUALIFIED_AND_NON_PROGRESS`;
- positive `qualified_event_budget`;
- positive `non_progress_state_budget`;
- `state_activity_consumes_qualified_budget=false`;
- `state_overflow_policy=COALESCE_OR_DROP_STATE_ONLY`;
- `late_qualified_event_policy=REMAINS_ELIGIBLE_AFTER_STATE_BUDGET_EXHAUSTION`.

State/heartbeat budget exhaustion may coalesce/drop only state records. It may
not disable the qualified emitter. This does not make state edges progress.

## Shared implementation receipts

| path | bytes | SHA-256 |
|---|---:|---|
| `.agents/rules/服务器测试包生成规则.md` | 101623 | `8d168ebd8dffa289d1898469d801c60671b3982a18776586af37e906c66e6652` |
| `.agents/rules/生成前必读索引.md` | 16216 | `d4d4de676c1b6fb864e2deadf9bd5bd3d8e34eb1955a399fb3f1ed3abe4f2da5` |
| `schemas/server_triggered_causal_observability_v1.schema.json` | 13577 | `b48e8c18fe756b8a7a58d256511039a861db9aebcb3603dbb30122c6ceaafbd1` |
| `schemas/server_diagnostic_budget_trace_v1.schema.json` | 2455 | `ab815aef99fc54b1e74d31b37800495ebd95525d4d900b12836660c0754d5ff2` |
| `contracts/server_triggered_causal_observability_registry_v1.json` | 6375 | `3675d33c0b48cd9fb0e709f4be64fde794db334aa8e2c74cd0253367b11cc01b` |
| `contracts/server_triggered_causal_observability_current_five_v1.json` | 58732 | `9a2f8494a2106a49a67bd8088a687289730270a205e7e1165fe8174f7d45b548` |
| `tools/validate_server_triggered_causal_observability.py` | 39216 | `add26164af7c1abd9347b1f92633e475cb98dfeab34d25480df35d5837fd9ace` |
| `tests/test_server_triggered_causal_observability.py` | 11758 | `b55c23f9adc74c4d2532728925fcf56ffdc1df3e200a960ab1d61570d1a08bda` |

Fixtures:

- positive state-oscillation fixture SHA-256
  `94c4ef5877930b5a639e72ce7dfc5dca0ca7f848f3a2ebadad94d369f0ae5ba2`;
- legacy shared-counter mutation SHA-256
  `576a60b3823bee7026b757550cedc060fcc5c4d4032af4819d274ce4a583623d`.

## Tests

- `python -m unittest tests.test_server_triggered_causal_observability -v`:
  19/19 PASS;
- `py_compile`: PASS;
- shared five-profile validation:
  SHA-256=`6a5b852369c5a7da7dcab386500f6c679dac436b9f437fef5b17f01338e9c867`,
  valid=true;
- positive trace: state seen=321, state budget=8, 313 state records
  coalesced/dropped, later `slice15.ga_output_accept` retained=true;
  report SHA-256=`88b3c1630e8a4b0c578cf7027c7e95fcc780551c834dfe66b2f8c85a15381c29`;
- shared-counter mutation: exit=1, later target retained=false,
  state consumed qualified budget=true;
  report SHA-256=`8be87be2becbcf7f5cd6c745b6946809cdab736d66ac6248753aafc05d202fea`;
- `git diff --check`: PASS.

Machine adjudication report:

`artifacts/operator_config_validation/r5-diagnostic-qualified-budget-state-isolation-v1/report.json`,
bytes=3273,
SHA-256=`5fd8799ffe52dc6df4d9e947585f3731249bce184760734963d6ca4b2fc5e5f7`.

## v51 disposition and claim boundary

GAP v51 already contains the family-local qualified-only fix. It was not
rebuilt, modified, revalidated, uploaded, or run by this adjudication.

No server package, server action, lease, RTL, config, numeric, hardware, ISA,
or active ndp-sim change occurred. Shared static contracts and synthetic budget
accounting do not prove exact v51 final-HDL binding, natural terminal, formal D,
E3, E4, or E5.
