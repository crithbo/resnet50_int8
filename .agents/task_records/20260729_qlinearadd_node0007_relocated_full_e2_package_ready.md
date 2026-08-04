# QLinearAdd node0007 relocated full E2 and package-ready record

- status: `LOCAL_PACKAGE_IDENTITY_SUPERSEDED_NOT_FOR_RELEASE`
- claim: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- candidate_release: `false`
- evidence_level: `E2_LOCAL_ONLY`
- numeric_analysis_repeated: `false`
- consumed_reuse_assets: `true`
- server_action: `false`
- server_source_inspected: `false`
- functional_rtl_modified: `false`
- server_rtl_entries: `0`

The complete FP32 SUM scratch is relocated to each slice's
`[0x00800000,0x00a4c000)`. The final native request proof contains
37,352,448 requests and every request row is below 6144. Static-to-final
configuration differs only in 13 allocator-owned `base_addr` string leaves;
non-base leaf differences are zero. Config-bound physical, logical and padding
mismatch counts are all zero.

The noncomputational relocation stage consumes a frozen FP32 zero input and
produces an unused hardware output. It does not preload or host-compute a
QLinearAdd internal tensor, and it does not change the six qparams, W3
operation order, input replay, SUM arithmetic or exact UINT8 tail.

Superseded local self-check package:

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_relocated_v1.zip`
- SHA256: `2c796e1a2b676bc2a1413552c85f0bbd93e6fa0a94d0afed2d1c84456a4462d4`
- repeated deterministic build: `true`
- runtime formal D targets in ZIP: `0`
- formal readback count: `28`
- result gate: compile0 AND run0 AND natural terminal AND loader exact AND
  readback exact-set AND missing0 AND mismatch0
- return collection: manifest explicit allowlist only

This v1 identity is not releasable because its manifest declared return
budgets but omitted the upload ZIP/extracted-size exception required for the
large formal SCA_D exact-set. A fresh v2 identity must carry the corrected
upload and return budgets and repeat the deterministic package build.

This record is not E4/E5 evidence and is not bound to a final
`Trassic2.0_RTL` commit. No upload or server run was performed.
