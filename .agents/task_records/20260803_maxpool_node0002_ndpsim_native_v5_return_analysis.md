# MaxPool node0002 ndp-sim native v5 return analysis

## Provenance

- analysis owner thread: `019fbe9f-3f2d-7071-806c-1ae72ae96391`
- return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- mode: `RECEIPT_ONLY_NATIVE_NDPSIM_USER_OVERRIDE`
- numeric / NumPy / GeneralPEA / W3 repeated: `false`
- RTL analysis repeated: `false`
- mapping, workload, config, bitstream, execplan or SCA rebuilt: `false`
- plan / public rules / functional RTL / other family modified: `false`
- server inspected, uploaded, run, or leased: `false`
- dispatch plan SHA: `ff9a254262b66cde100c1b8d13fc4539f2e10d9a137203ab6c20d8a4c0ca134d` (mutable provenance only)
- analysis-observed plan SHA: `1fcefd012f3771003954cd8a64c9856c4fc557a502618d1dac95485bd7a6df7c` (mutable provenance only)

## Frozen identity

- return: `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n2_maxpool_ndpsim_native_v5_return.zip`
- return bytes: `35166`
- return SHA256: `68265ded27f981d3ac448848baae2658ee15710c947155c8ed69dd9fa78fb1dc`
- adjacent return sidecar: absent; accepted only as user-attested external transport, without relaxing any ZIP-internal gate
- source ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_ndpsim_native_v5.zip`
- source bytes: `14718654`
- source SHA256: `9a193d8f97d7b43d7e43886a2bc42dffee74e585832f5360a13a8ead2fa7269e`
- authoritative source JSON: `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`
- source JSON SHA256: `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- install / run / return: `r5_n2_maxpool_ndpsim_native_v5` / `run_r5_n2_maxpool_ndpsim_native_v5` / `r5_n2_maxpool_ndpsim_native_v5_return`

## RETURN_ANALYSIS

- ZIP CRC, single root, path safety, duplicate and symlink checks: PASS.
- ZIP members: 16; `RETURN_MANIFEST` records: 15; exact-set PASS.
- `required_missing=[]`; every recorded size and SHA256 matches.
- returned `TEST_PACKAGE_MANIFEST.json` is byte-identical to the frozen source package manifest.
- returned SCA and SCA_D are byte-identical to the source package copies.
- package and installed preflights are valid; source JSON is not rewritten; only the two frozen planner-owned base-address leaves differ in the materialized config.
- package and installed runtime-D preflight: initially absent.
- actual compile and simulator argv are present and bind the exact run/install/SCA/SCA_D identities.
- generic observer source / `+incdir` / macro / time-zero marker / runtime enable are explicitly N/A under the preserved user native-path override; no observer or canonical diagnostic is packaged or relied upon.
- EXIT/INT finalizer PASS: finalizer entered, original status 130, analysis status 0, signal `INT`, partial return complete.
- compile exit: 0; VCS `Compilation completed!`.
- simulation exit: 125; runner exit: 130; signal: `INT`.
- simulation loaded all 30 native matrices, accepted `Exec_Base=0x0003d800`, `Exec_Length=29`, printed `Reg Started.` and entered `INFO: slice start`.
- slice start simulation time: `2424336000 ps`.
- interrupt simulation time: `36611175625 ps`.
- post-start simulation time advanced `34186839625 ps`.
- no wall-clock receipt or qualified post-start progress record exists in the deliberately native-only package.
- no native slice-complete or simulation-complete terminal was observed.

## Formal D and evidence levels

- formal D expected / present / missing / invalid: `28 / 0 / 28 / 0`.
- mismatch bytes: `null`; all-missing is not evaluable and is not a numeric pass.
- result conjunction: FAIL.
- E3: false.
- E4: false.
- E5: false.
- the user's previously established MaxPool reuse authority is not treated as this run's E4 or E5 evidence.

## LAST_PROVEN_GOOD

`COMPILE_PASS_TO_30_NATIVE_MATRICES_LOADED_TO_REG_STARTED_TO_SLICE_START`

## FIRST_DIVERGENCE

`SLICE_START_TO_NO_NATIVE_SLICE_COMPLETION_OR_FORMAL_D_BEFORE_EXTERNAL_INT`

## HANG_ROOT_CAUSE / terminal adjudication

- terminal disposition: `DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE`
- execution state: `NATIVE_EXECUTION_INTERRUPTED_AFTER_SLICE_START_WITHOUT_NATURAL_TERMINAL`
- package infrastructure failure: false.
- unique configuration or RTL root cause proven: false.
- hang proven: false.
- merely slow or incomplete proven: false.

The return proves that native execution started and was interrupted before terminal/readback. Because the user override deliberately excludes the generic progress observer and the return has no wall-clock or qualified post-start progress evidence, it cannot distinguish continued work from a stall or identify a config/RTL leaf. The user explicitly forbade reopening the generic MaxPool diagnostic route.

## BLOCKER_DELTA

Closed:

- `V5_RETURN_INTERNAL_RECEIPT_AND_IDENTITY`
- `V5_PACKAGE_INSTALL_PREFLIGHT`
- `V5_COMPILE_AND_NATIVE_EXECUTION_START`
- `V5_EXIT_INT_FINALIZER_AND_PARTIAL_RETURN`

Open but terminally deferred by the user native-reuse override:

- `V5_NATIVE_NATURAL_TERMINAL_ABSENT`
- `V5_FORMAL_D_28_OF_28_MISSING`
- `V5_SERVER_SOURCE_IDENTITY_UNBOUND_FOR_E4_E5`

## RULE_DELTA_PROPOSAL

`NONE`

## PACKAGE_RELEASE_OR_NONE

- successor generated: false
- package release: `NONE`
- reason: no package-local runner/collector/native namespace/manifest defect was found. The remaining dynamic boundary is explicitly outside the authorized analysis scope, so no generic observer/canonical successor is allowed.

## Evidence

- analyzer: `tools/analyze_maxpool_node0002_ndpsim_native_v5_return.py`
- analyzer bytes: `21712`
- analyzer SHA256: `73abae0f0e061b0b4289b5554edd90e9540e204d699868c22c8c4d8f8c20a39b`
- analyzer standalone exit: `0`
- machine report: `artifacts/operator_config_validation/r5-maxpool-node0002-ndpsim-native-v5-return-analysis/report.json`
- machine report bytes: `8238`
- machine report SHA256: `81fc472a64827b4974ffb4cd235d12536de079793ec5c96c10934e4ed29e3d29`
- machine report JSON parse and `valid_internal_receipt_analysis=true`, `errors=[]`: PASS
