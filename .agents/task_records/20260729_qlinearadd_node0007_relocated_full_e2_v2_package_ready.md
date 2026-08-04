# QLinearAdd node0007 relocated full E2 v2 package-ready record

- status: `PACKAGE_READY_NOT_RUN`
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
37,352,448 requests and all request rows are in `0..6143`. Static-to-final
configuration differs only in 13 allocator-owned `base_addr` formatting
leaves; non-base leaf differences are zero. Config-bound physical, logical and
padding mismatch counts are all zero.

The noncomputational relocation stage consumes a frozen FP32 zero input and
produces an unused hardware output. It does not preload or host-compute a
QLinearAdd internal tensor, and it does not change the six qparams, W3
operation order, input replay, SUM arithmetic or exact UINT8 tail.

Package:

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_relocated_v2.zip`
- SHA256: `60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc`
- sidecar: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_relocated_v2.zip.sha256`
- repeated deterministic package tree and ZIP: `true`
- runtime formal D targets in ZIP: `0`
- formal SCA_D exact-set: `28`
- formal logical readback bytes: `16,859,136`
- upload budget: ZIP `64 MiB`, extracted `512 MiB`
- return budget: ZIP `64 MiB`, extracted `256 MiB`
- result gate: compile0 AND run0 AND natural terminal AND loader exact AND
  readback exact-set AND missing0 AND mismatch0
- return collection: manifest explicit allowlist only
- current contract SHA256:
  `91779715b40ad37b42c00a7dd50977d6081a1e9eacf41fa881d0d0d1d2505658`

The package manifest binds the reconstructable pre-build contract snapshot
`b917fe89b9cec690ce2bb758fbf92c454665a29e524cd071544fdb8ebbabf499`,
whose package-release leaf names the superseded v1 local identity. The current
post-build contract binds the v2 ZIP above. This directed relationship avoids
a recursive ZIP/contract hash cycle and is checked by the ZIP audit.

The earlier v1 local identity is superseded and not releasable because it
omitted upload-side large-readback budgets. This v2 identity is the sole
delivery candidate.

This record is not E4/E5 evidence and is not bound to a final
`Trassic2.0_RTL` commit. No upload, server inspection or server run was
performed.
