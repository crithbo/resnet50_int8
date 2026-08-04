# MaxPool node0002 exact-native JSON reuse v4 package

## Scope and authority

- Independent owner: MaxPool node0002 only.
- Source authority:
  `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`,
  SHA256 `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`.
- Target: `node-0002` / `r5:hwop-0002-00`,
  `uint8[16,64,112,112] -> uint8[16,64,56,56]`,
  kernel `3x3`, stride `2`, pads `1`, same qdomain.
- This task did not modify `.agents/plan.md`, public/specialized rules,
  functional RTL, or any other operator family.

## Source JSON and reuse boundary

- Reuse class: `EXACT_FULL_OPERATOR`.
- The active native JSON and packaged `.original` copy are byte-identical.
- Operator JSON diff count: `0`.
- Semantic/non-base diff count: `0`.
- Planner-owned base diff count: `0`.
- Only `sca_cfg.json` and `sca_cfg_D.json` payload paths receive the fresh
  install namespace prefix; config bitstream, execplan, addresses, lengths,
  input, and golden semantics remain unchanged.
- Existing full-node local E2 was consumed read-only:
  `artifacts/operator_config_validation/maxpool-node0002-config-only-e2-v1/validation_report.json`,
  SHA256 `5fb484e9c1bf40b86d68c21c8837e6a61978e63cac40e9e2f5b3b42ea3dd9a61`.
- Frozen W3 input and output tensors are reused directly.
  NumPy MaxPool and GeneralPEA numeric checks were not rerun.
- Dynamic package scope is two real ResNet channel tiles on slices 0 and 1.
  This tests whether the exact native configuration runs and localizes the
  known flow risk; it is not a full-node E4/E5 claim.

## Native materialization

The exact source JSON was freshly mapped from an empty cache at the locked
ndp-sim commit. The selected exact mapping had `penalty=0` and
`fallback=false`; semantic encoder outputs were reproduced in isolated runs.
The current toolchain then generated bitstream, serialized two-stage execplan,
SCA/SCA_D, input preload, formal readback targets, and golden payloads.
Runtime D targets are absent from the package and post-install preflight.

## Progress diagnostics

The package contains no functional RTL. It carries one package-local,
read-only observer selected by:

- compile include: `+incdir+$package_root/tb_probe`;
- compile enable: `+define+NATIVE_RETURN_OBSERVER_ENABLE`;
- runtime enable: `+RETURN_OBSERVER`.

The observer samples qualified MSE request/read/write events, GA pipeline0
capture, GA outbuffer write, and slice finish. Raw pipeline0 valid/backpressure
levels are returned only as state and never count as progress. Source counters
are owned by `clk_sg`; rate-limited snapshots and the canonical decision are
emitted by independent `clk_db`. Sampling is once per 262144 active cycles and
four consecutive zero-delta windows terminate with one canonical boundary.

This package deliberately does not bypass:

- `B_GA_INT8_MAX_NUMERIC`;
- `B_GA_INT8_MAX_FLOW`;
- `B_MAXPOOL_SERVER_E4_E5`.

## Pre-release defect caught locally

The first unpublished build exposed a direct observer syntax defect:
adjacent SystemVerilog string literals. It was removed before delivery.
A focused hierarchy test now compiles the exact observer under Icarus SV2012
with exit `0`. The unpublished ZIP was deleted and deterministically rebuilt
under the same never-delivered identity.

## Final ZIP audit

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_native_reuse_v4.zip`
- bytes: `1496952`
- SHA256:
  `f2df61c2edd9459f872dc930312fa3cecb30d72ecd284760fbbc534d5f5dd6a0`
- sidecar file SHA256:
  `65f66e7a389ec5a4d1c5c907c1b6f46e761913454abeec7d88cf1188286cd22d`
- final audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_native_reuse_v4.final_zip_rule_self_audit.json`
- final audit SHA256:
  `b42fb6b9d6bfcd2d5b19563223563826c92c4dc83bfb39cb7cd33950f4920307`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- all seven negative controls fail closed.
- fresh-extract preflight exit `0`; package tree unchanged.
- runner bash syntax exit `0`.
- real runner -> safe compile stub: expected/observed `86/86`,
  compile reached exactly once, actual compile argv saved.
- wrong payload identity: exit `5`, compile not reached.
- focused tests:
  `.venv\Scripts\python.exe -m unittest
  tests.test_maxpool_node0002_native_reuse_v4 -v`,
  `4/4 PASS`.

Machine report:
`artifacts/operator_config_validation/maxpool-node0002-native-reuse-v4/report.json`,
SHA256 `151db13579324d37a5ad9018af57df53806c4be6d3d9d6865cac2628e48b3a1b`.

## Package release

- Status: `PACKAGE_READY_NOT_RUN`.
- Claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.
- Candidate release: `false`.
- Server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`.
- Expected return:
  `r5_n2_maxpool_native_reuse_v4_return.zip`.
- No server upload, execution, lease, or server-source inspection occurred.

## Rule delta

`RULE_DELTA_PROPOSAL=NONE`. Current reuse-first, NDP field semantics, and
server-package rules are sufficient.
