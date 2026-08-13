# family.conv.native p46 native-flow successor

Date: 2026-08-13 (Asia/Shanghai)

## Ownership and dispatch

- role_id: `family.conv.native`
- owner: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- current mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- activation epoch: `runtime-preflight-native-flow-v1`
- status: `PACKAGE_READY_NOT_RUN`
- server actions performed: none; no upload, run, lease, connection, or server-side action occurred.

## Previous-version progress and current-version purpose

Previous-version progress: p41 passed production compile beyond the Datahub repair. p42 fixed the two-bit vector valid/ready scalar false-negative. p45 attempted broad observer-only localization, but production compile failed at unresolved `DW_ecc`, `DW_sync`, `DW_lod`, and `DW_fifo_s1_sf` before simulation.

Current-version purpose: run the corrected p42-equivalent MSE4 wdata/slice-finish diagnostic through the native production path without provider preflight and capture exact native-flow evidence. It also closes p45's package-local return defects by returning actual compile argv/source/cwd/environment, complete compile log plus bounded head/tail and first true compiler error, exact `COMPILE_CORE`, observer `SIM_EXIT`, and an exact core manifest.

## Fresh identity and frozen surface

- source: tested `r5_n4_0cc_p45_obswide`
  - bytes: `5974378`
  - SHA-256: `fda80c374db7f906abc9e0dcbed768d64e58ab1e8351e90867abdb79e8d99e5c`
- fresh package: `r5_n4_0cc_p46_nativeflow`
- exact pending ZIP:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p46_nativeflow.zip`
  - bytes: `5979948`
  - SHA-256: `6a648613492d66b244564a0acc8f7d59709a971cf2c84d47c4922fe040f61478`
- deterministic repeat: byte-equal, same byte count and SHA-256.
- frozen: config, numeric, workload, golden, functional RTL, and target diagnostic.
- retained diagnostic: p42 two-bit vector predicate and MSE4 wdata/slice-finish causal target.
- dump values: `DUMP_VCD=0`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`.

## Native-flow and return contract

- the runner contains exactly one `# CODEX_PRODUCTION_LAUNCH` marker;
- before the marker it only checks package-local argument syntax and arms the partial-return finalizer;
- after the marker it directly enters the supplied native root, installs the package namespace, invokes the actual native production compile, and then invokes simulation;
- no server-owned file/tool/library/RTL/provider inventory or preflight is performed: no `test`, `stat`, `find`, hash, git, `command -v`, `which`, Make dry-run, provider probe, or independent attestation;
- actual cwd, compile/sim argv, relevant environment, `SCA_CFG`, `SCA_CFG_D`, and `Repeat_Num` are returned;
- natural compile failure preserves the complete compile log, bounded head/tail, first true compiler error, all exits, `simulation_started`, exact `COMPILE_CORE`, and exact core manifest;
- the registered native ndp-sim differential runs only after a real failure; unresolved loader/start/wait/readback remains `SERVER_RUNTIME_UNKNOWN`;
- broad source-bound ordered four-state observer evidence is retained with decimal `100000000` bytes warning-only and no hard cap, sampling, truncation, head-tail-only substitution, or size deletion;
- repeat-safe cleanup, child subreaper/PGID/timeout/TERM-wait-KILL-reap, atomic unique return publication, and pre-archive observer flush/close remain enabled.

## Gate closure

The exact final ZIP passed the current conjunction:

- package-local HDL reserved declaration-name lexical scan over staging and independent exact ZIP;
- full HDL frontend/scope/state and negative controls;
- runtime-preflight noninterference, exactly one production marker;
- observer-only wide-causal exact-ZIP contract;
- source-bound actual-net catalog and candidate discrimination;
- post-sim return core;
- runner return resilience and definition-before-use;
- native compile-core evidence contract;
- runtime layout and synthetic failure/partial-exit harness;
- current-epoch first-fresh audit;
- final-ZIP deterministic/safety/manifest checks;
- aggregate build profile with complete prebuild coverage;
- corrected global package-storage audit.

First-fresh epoch is exactly `runtime-preflight-native-flow-v1`; all eight retained candidates are covered and pairwise distinguishable. The shared validator's mechanical `upload_authorized=true` result is only a local gate result and does not grant or exercise upload authority.

## Exact receipts

- final ZIP audit:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.final_zip_audit.json`
  - bytes: `6326`
  - SHA-256: `a801c8525f02e4313457aedfcd764efdff9d649410281cc4a76231208ae66fc0`
- first-fresh validation:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.first_fresh_validation.json`
  - bytes: `2514`
  - SHA-256: `3e81cbd0b4eb91d8cf9fb770593e234d6c228c240da401dcf0de5109c954f8e6`
- runtime-preflight noninterference:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.runtime_preflight_noninterference.json`
  - bytes: `2768`
  - SHA-256: `e673faf91f84aeafe5228233d44bd7d972a9bb98d775d16f6333f7bee0972d19`
- compile-core contract:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.compile_core_nativeflow.json`
  - bytes: `704`
  - SHA-256: `1ba69049c00701d429b8399e25d0c1ee99f0d2a9175b94bcb2bf9e63b1e5e149`
- build profile:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/r5_n4_0cc_p46_nativeflow.server_package_build_profile.json`
  - bytes: `25045`
  - SHA-256: `c7cbe588c0285ac07f504c822736976fa62527068fafe2865ead600ee487a87d`

## Storage publication

Publication used only `tools/manage_server_test_package_storage.py rotate`. Native had no pending package before publication, so no predecessor was moved. Tested p45 remains unchanged. The corrected independent global audit after publication reports:

- pass: `true`
- pending count: `3`
- tested count: `124`
- superseded count: `54`
- `pending_by_family.conv_native_four_lane = ["r5_n4_0cc_p46_nativeflow"]`

Storage index:

- path: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
- bytes: `531892`
- SHA-256: `fbac22bad96565be4e0cfde110cdd3313358921ca63da5996ba16b4582a12d04`

## Only future server command and expected return

This record does not authorize server action. If separately authorized later, the only package command is:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Expected formal return:

`/home/panqs/ndp/simresult/r5_n4_0cc_p46_nativeflow_r<epoch-ns>_<pid>_return.zip`

## Claim boundary

This closes only local construction, deterministic exact-ZIP validation, synthetic runtime plumbing, current-epoch first-fresh auditing, and storage publication. It does not claim upload, lease, connection, production compile, DUT simulation, observer dynamics, MSE4 localization, natural terminal, formal D, E3, E4, or E5.

Final status: `PACKAGE_READY_NOT_RUN`.
