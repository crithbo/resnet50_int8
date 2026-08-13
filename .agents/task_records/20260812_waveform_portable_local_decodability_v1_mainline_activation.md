# 2026-08-12 — Portable local waveform decodability v1 mainline activation

## Ownership and scope

- Mainline role: `mainline.control`
- Mainline owner thread: `019ff027-e7db-72a3-b282-cfad8708da05`
- Registry epoch: `6`
- Shared-method owner: `optimizer.whole-network`
- Family signal interpretation remains owned by the corresponding family owner.
- No current package, pending ZIP, RTL, config, numeric, workload, golden, lease or server state was changed.

## Required progress and purpose

Previous progress: `CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001`
proved that a full-hierarchy raw VPD can be generated, returned without a byte cap and bound to a runtime
receipt. The real serialized Conv v87b return then proved a non-synonymous gap: raw VPD transport passed,
but no local `vpd2vcd`, Verdi or DVE executable was available, so the VPD could not be semantically decoded.

Current purpose: make every next-fresh DUT-simulation package preserve authoritative raw VPD while also
implementing an identity-bound portable VCD or registered signal-query return path. Conversion failure must
preserve raw/core return and mark only the waveform diagnosis incomplete.

## Mainline adjudication

- Proposal accepted as non-synonymous stable semantics.
- Rule ID: `CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001`.
- Activation epoch: `waveform-portable-local-decodability-v1-b0a94cf60d6e`.
- Enforcement: `required_next_fresh`.
- Current pending/tested packages are not retrospectively held, rebuilt or rewritten.
- A historical formal return may produce an identity-bound conversion request without rerunning simulation,
  but that does not retroactively satisfy a next-fresh package gate.
- Raw VPD remains authoritative. A portable derivative never replaces raw waveform, compile/sim/signal/core
  receipts, natural terminal, formal D or family-owned root-cause adjudication.

## Activated semantics

1. A simulation-started next-fresh return with VPD must attempt either an identity-bound, unbounded
   `vpd2vcd` derivative or a registered and validated vendor signal-query receipt.
2. Converter identity, best-effort version, exact argv, exit/log, input/output identity, VCD header,
   timescale, signal catalog and time range are receipt-bound.
3. VCD/query evidence has no waveform byte, event, extraction or shard cap and may not be truncated,
   sampled or deleted because of size.
4. Missing/failed conversion cannot suppress raw VPD or core return; it fixes the diagnostic state to
   `DIAGNOSTIC_EVIDENCE_INCOMPLETE` without changing the simulator exit fact.
5. Complete/partial provenance is inherited from the source VPD. Partial waveform may not be upgraded.
6. Shared tooling owns conversion and fact extraction only. FIRST_DIVERGENCE, driver-cone and family
   classification remain family-owned.

## Public-rule and gate receipts

- `.agents/agent.md`: bytes `20428`, SHA-256 `6d0b68d9ef7e00bb135ca0bcbaeb57955350ae3d4bcbbca005b8f25d94f96f64`
- `.agents/rules/生成前必读索引.md`: bytes `8097`, SHA-256 `dad9b9b2557c5e495db7229bb775575b40a0a452de840529b3172716a88fc48b`
- `.agents/rules/服务器测试包生成规则.md`: bytes `158860`, SHA-256 `b0a94cf60d6ed50f063bb471d036bd553bfccab3306561bb65936713057f94fd`
- `contracts/server_package_build_gate_registry_v1.json`: bytes `14396`, SHA-256 `89750e1d0749a40d53673443548be17c8fd6ef9c9c750d14fc03252eab0bbffa`
- `contracts/active_rule_registry_v1.json`: SHA-256 `9a9eea4b8d60592849fb66f000d5a9abf81015b17bafdb0c20ac9c75a4b3f280`

The gate registry now contains `waveform_portable_local_decodability`, semantic version `1`, activation
`always`, enforcement `required_next_fresh`, non-reusable exact evidence and final-ZIP release-driver
execution. `first_fresh_extra_audit` remains independently active and is retriggered by the new epoch.

## Frozen shared implementation

- `tools/server_waveform_local_analysis.py`: bytes `24472`, SHA-256 `088e8d797f98f247f030e9331ca3c83e7b767b5958a8bf74d2732974850510af`
- `schemas/server_waveform_local_analysis_v1.schema.json`: bytes `687`, SHA-256 `88ee61884e42f574958bb810b6f82427e374afa315c1a31086e5d5043e916044`
- `contracts/server_waveform_local_analysis_dispatch_v1.json`: bytes `1568`, SHA-256 `e9a9078cb27dc202b62a75a9d23ce15a394430b4e1c58bbd18bf3c03a50f1931`
- `tests/test_server_waveform_local_analysis.py`: bytes `6173`, SHA-256 `d796576f0d527b33e567aa0eef0e15a7f34d46c466fb3b172810b08cf6005a1a`
- `fixtures/server_waveform_local_analysis_v1/small.vcd`: bytes `319`, SHA-256 `bca910f02fb8ab8519a3bc12213394d2042e6d0242ff49bafbdf6dfdd8cf7fb6`
- Optimizer proposal record: `.agents/task_records/20260812_waveform_portable_local_decodability_v1.md`,
  bytes `3702`, SHA-256 `b0bfc9f9891c180d324a9b3ded96cfeb021f83564586c76d7d46ec734a05675f`.

## Validation

- Shared local-analysis and existing mandatory-waveform suites: `20/20 PASS`.
- Shared method's focused suite: `8/8 PASS` within the aggregate above.
- New build-gate registry entry compiled as `blocking_applicable` and `required_next_fresh` through the
  underlying `compile_profile` path.
- `py_compile` for the local-analysis, active-rule audit and package-pipeline helpers: PASS.
- Active-rule registry audit: PASS, 14 registered/active rules, 160 unique rule definitions, no duplicate owner.
- Six activation JSON documents parsed successfully.
- Scoped `git diff --check`: PASS.
- The bundled Python lacks `jsonschema`, so `tests.test_server_package_pipeline` could not import. The same
  registry/compile-profile path was exercised directly without that optional schema dependency; no package
  or dependency was installed.

## Real v87b method consumption

Serialized Conv consumed the frozen shared method. Toolchain discovery and conversion failed closed with
`VPD_SEMANTIC_DECODER_EXECUTABLE_NOT_AVAILABLE`; conversion request passed and requires no simulation rerun.
No VCD was produced, so the globally earliest VPD transition and actual compiled driver cone remain unclaimed.
The family terminal remains `WAIT_RTL_FIX`; the execution-bound observer contradiction remains the first proven
divergence, not a decoded VPD conclusion.

## Current package boundary

The current pending exact set remains native Conv p42, GAP v57 and QAdd v58. Serialized Conv remains
`WAIT_RTL_FIX` with no package-only successor. The portable-local gate applies when any family creates its next
fresh successor after this activation; it does not authorize upload, server conversion, lease, run or RTL repair.
