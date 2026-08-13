# QLinearAdd slow-composite strict JSON materialization

Date: 2026-08-06

Owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`

Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

Status: `COMPLETE_LOCAL_STRICT_JSON_17_OF_17`

## Result

The Requant dependency gate was consumed at report SHA
`9b426c6731be52e5a68eec300d6765cc1589cec2c1a3decea66fad107cdf9ddf`.
All 17 `QLinearAddUint8` lowering stages now have a local, relocatable strict
JSON candidate. Sixteen are same-shape residual adds and `hwop-0076-00` uses
16 hardware B replay invocations; no host-produced internal tensor is used.

Every candidate binds all six qparams, exact W3 operation order, the accepted
17×65,536 reachable-pair SFU DP table, the accepted nine-PE selector chain
`4,4,1,3,4,3,4,3`, `PE32 -> outport6/src1`, one-lane 4-byte transport,
paired A/B readiness, local addresses, accepted terminal, and lifetime.

Shared candidate validation is 17/17 PASS with 17,588 provenance leaves,
`UNRESOLVED=0`, `errors=0`, and `completion_blockers=0`. The exact family-set
audit is 17/17 PASS with no missing, unexpected, duplicate, type, or lowering
SHA errors. Seven focused negative controls all fail closed.

## First shared-gate correction

The first fresh generated tree was isolated at:

`artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1_failed_shared_gate_20260806`

The shared validator correctly rejected a Markdown derivation receipt and
non-leaf blocker pointers. The successor changes only these machine-contract
bindings. Numeric values, qparams, SFU tables, topology, workload, and claim
boundary did not change.

## Claim boundary

This closes local strict complete-JSON materialization only. It does not
generate or claim native backend registration, mapping, bitstream, execplan,
SCA, ZIP/package, server execution, natural terminal, formal D, E3, E4, or
E5. QAdd node0007 v36 remains an independent frozen pending dynamic asset.

No numeric/W3/qparam/tail/workload/golden analysis was repeated. Existing
proof assets and the Requant strict report were consumed byte-for-byte.

## Validation commands

```text
python tools/materialize_qlinearadd_slow_composite_strict_json_v1.py --proof-root <accepted-owner-proof-root> --output-root artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1
python tools/validate_qlinearadd_slow_composite_strict_json_v1.py --artifact-root artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1 --output artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1/validation.json
python tools/validate_complete_operator_json_candidate.py <each-of-17-candidate-contracts> --output <stage>/shared_candidate_validation.json
python tools/audit_complete_operator_json_family_set.py artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1/family_set.json --output artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1/shared_family_set_audit.json
python -m unittest tests.test_qlinearadd_slow_composite_strict_json_v1 -v
```

All exit codes are 0.

## BLOCKER_DELTA

Closed:

- `B_COMPLETE_JSON_QADD_SIX_QPARAM_TYPED_MATERIALIZATION`
- `B_COMPLETE_JSON_QADD_EXACT_DIVIDE_RNE_SLOW_COMPOSITE_CAPABILITY`
- `B_COMPLETE_JSON_QADD_NODE0076_HARDWARE_BROADCAST_REPLAY_CAPABILITY`

Open and unchanged:

- `B_QADD_BACKEND_AND_DYNAMIC_EXECUTION`
- `B_QADD_SERVER_E4_E5`

## RULE_CONFIRMATION

Existing rules were sufficient. In particular, complete-JSON leaf provenance,
handler capability, composition boundaries, exact-stage family scope,
QAdd W3 order, six-qparam transport, broadcast replay, readiness/lifetime,
and exact-tail dependency rejected the invalid first tree and admitted the
corrected 17/17 complete set without relaxation. No new rule is proposed.

## Machine report

`artifacts/operator_config_validation/r5_qlinearadd_slow_composite_strict_json_v1/report.json`

Machine report:

- bytes: `7,511`
- SHA256:
  `e8de92e06b605882414ac80e0acb0a99d4fc73bee74b12257e23bf52ec8c692f`
