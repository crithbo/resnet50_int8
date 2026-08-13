# Conv native-four-lane p7 formal return → p8f full-chain successor

## Scope and ownership

- Owner: `019fc783-1146-7901-9e40-64d0ed8e052d`
- Sole structured return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Family: frozen Conv node0004 native-four-lane performance candidate only.
- The serialized Conv correctness baseline, functional RTL, `.agents/plan.md`,
  public/special rules, and all other operator families were not modified.
- No server upload, run, lease, or server-side mutation was performed.

## Current rule receipts used

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/rules/生成前必读索引.md`:
  `bd04756ccab49e5a94843a8d9337eda35f818073ea9daa31244be1ae9903e547`
- `.agents/rules/服务器测试包生成规则.md`:
  `36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457`
- `.agents/rules/算子配置规则.md`:
  `30d0b20979e639d6bd9d0ec81f5e920da19733f0b2e3fe7ba751ef7e44b972d1`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`
- Current mutable plan provenance observed during analysis:
  `eb49193ba1a2d0b993e2a7ec7f358a904a520771f30f003f76c460f69a7b7997`.

## Formal p7 return receipt

Transport source:

`C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-08\r5_n4_0cc_p7_return.zip`

- bytes: `93,722`
- SHA256:
  `71e7feda390934afec933ddfbfded6d6bebfdb633a66fe3ab00dd1817293f05c`
- adjacent sidecar: absent, exempted only for external transport.

Exact frozen source:

`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p7.zip`

- bytes: `5,812,109`
- SHA256:
  `4ff473247a7356af3e6b960430b559e90113b774e27478dbcd41151d8507f8a4`

Internal receipt passed:

- single exact return root, CRC/path/symlink/duplicate checks;
- 19-file exact set;
- every record size/SHA;
- RETURN_MANIFEST ↔ RETURN_ALLOWLIST binding;
- returned source manifest ↔ exact local p7 source manifest binding;
- package/install/observer precompile gates;
- compile and feature-binding log SHA closure.

Machine analysis:

`outputs/conv_native_four_lane_0ccae916_p7_return_analysis/report.json`

- SHA256:
  `ead4ad1d029af18205040d242ec5607378fc1884f9d395f325f1435c57a0da92`
- status:
  `LONG_RUNNING_PROGRESSING_RUNNER_TIMEOUT_SUCCESSOR_REQUIRED`
- classification:
  `PACKAGE_WALLCLOCK_BUDGET_UNDERPROVISIONED_NOT_FUNCTIONAL_HANG`

## p7 execution and identity adjudication

- production compile exit: `0`;
- c0 run exit: `124`;
- external signal status: `NONE`;
- actual production identity collection: valid, 8/8 leaves;
- actual identity vs current cloud `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`:
  exact match;
- actual identity differs from local e1 provenance for the expected three
  changed leaves; the difference was recorded and did not block simulation.

p7 c0 dynamic trace:

- exact feature marker: 1;
- `EXEC_START`: 1;
- `SLICE_FINISH`: 0;
- heartbeats: 86;
- complete `STILL_PROGRESSING` windows: 28;
- later hang/zero-delta decisions: 0;
- last sample: DB cycle `31,946,266`;
- last qualified total: `44,827,079`;
- last Buffer4 write count: `14,942,175`;
- last Buffer5 read count: `14,942,202`;
- host-observed interval: `3,570 s`, with monotonically growing observer log.

Therefore:

- LPG reaches exact source/return, preflight, production compile, actual 0cc
  identity, simulator launch, feature binding, exec start, and sustained
  qualified progress well beyond the former 2,097,152-cycle plateau.
- FD is the package-enforced one-hour wallclock timeout before the first c0
  slice finish.
- `HANG_ROOT_CAUSE =
  NOT_A_PROVEN_FUNCTIONAL_HANG_RUNNER_TIMEOUT_WHILE_PROGRESSING`.
- p7 has no formal 320D payload by design. Missing natural terminal and absent
  formal D are not promoted to either a pass or a numeric failure.
- p7 proves neither c0 terminal nor E3/E4/E5.

Blocker delta:

- closed:
  `B_P6_ACTUAL_PRODUCTION_RTL_IDENTITY_MISMATCH_3_OF_8`,
  old 2,097,152-cycle progress plateau, and simulator-launch uncertainty;
- converted to package-local repair:
  `B_P7_ONE_HOUR_RUNNER_WALLCLOCK_UNDERPROVISIONED`;
- preserved until formal successor return:
  c0 slice finish, 27 natural terminals, 320/320 D, and E3/E4/E5.

## Unique successor decision

The failure is package/runner-local and within this owner's authority. To avoid
another c0-only leaf, the unique successor advances directly to the full
27-run chain and formal 320D gate, restoring the frozen p4 12-hour per-run
budget.

Fresh identity: `r5_n4_0cc_p8f`

Exact p4 source retained:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_df23e4d_p4.zip`
- SHA256:
  `c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e`

The p8f workload relation to p4 is content-neutral:

- 503 runtime workload files;
- 449 byte-identical;
- 54 differ only by normalized install-name strings in SCA JSON;
- missing/extra/semantic changes: `0/0/0`;
- 183 address/config/mapping/bitstream/execplan direct consumers:
  zero normalized mismatch;
- observer bytes: exact p4 byte identity;
- 320 golden D files: exact p4 byte identity;
- numeric/W3/golden was not recomputed.

Changed surface:

- fresh outer/install/run/return identity;
- actual/local/cloud post-compile identity collector;
- identity difference is nonblocking for simulator launch;
- 12-hour per-run wallclock retained/restored;
- package provenance and current release-gate matrix.

Unchanged surface:

- typed request and W3;
- all numeric/config/mapping/bitstream/execplan/SCA/SCA_D payload semantics;
- addresses and lifetime;
- native four-lane observer/parser/canonical semantics;
- all 320 golden D payloads;
- no functional RTL.

## p8f package release

ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f.zip`

- bytes: `66,231,520`
- SHA256:
  `1e214ba277992d4ab08795dd35f4db3082ccad4e17bebc2aaf6e473b1bc7c224`

Sidecar:

`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f.zip.sha256`

- bytes: `84`
- SHA256:
  `2e6ce2939087f637db4dd0e9da46c8e1c8a28fc0bcf19ca8e75adeaf686d03c2`

Build receipt:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f.validation.json`
- SHA256:
  `b2863bcb99c7674d2ef388b5dd923b36ddf4db200441fb31df056fe65e0270c3`
- deterministic dual build: byte-equal.

Final audit:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f.final_zip_audit.json`
- SHA256:
  `a50c72f28d1bb1f66d891756fa35b59bee824b791e4e82f911933b9581bb7b43`
- status: `PACKAGE_READY_NOT_RUN`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- blocking failures: none.

Manifest:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f/package_manifest.json`
- SHA256:
  `1b21911a61d5dd19ca2860da5cd48d890bf11f599c8da343ab6a3d81f61989a3`

## Final release-gate matrix

- `core_package_bootstrap_path_runtime_d`:
  `blocking_applicable / PASS`
- `runner_compile_finalizer`:
  `blocking_applicable / PASS`
- `package_local_hdl`:
  `blocking_applicable / PASS`
- `materialized_config`:
  `receipt_reuse / PASS`
- `observer_parser_canonical`:
  `receipt_reuse / PASS`
- `return_result_joint`:
  `blocking_applicable / PASS`, formal server result still pending
- `numeric_w3_golden`:
  `record_only / PASS`, not repeated

Specific evidence:

- package exact-set, CRC, sidecar, current rule receipts, deterministic replay:
  pass;
- projected path:
  `226 <= 240` chars at the declared 96-char server root;
- path negatives for deep member, repeated outer identity, and stale consumer:
  all fail closed;
- SCA closure:
  54 SCA files, 846 consumer paths, 320 D consumers, 128 dynamic tail
  consumers;
- runtime D preloaded count: 0;
- golden D present count: 320;
- package-local observer focused Icarus syntax/scope and three negative controls:
  pass;
- package exact-set, observer deletion, preloaded D, observer SHA, runner macro,
  include path, and return-target negatives:
  all fail closed;
- immutable 0cc raw Git blobs were used for the identity positive fixture;
- exact final runner proved that three actual/cloud leaf SHAs differing from
  local e1 provenance still reach the simulator stub;
- signal-safe finalizer emitted an exact allowlist return with the production
  identity receipt.

The Windows checkout represents some 0cc source files with CRLF. Their LF
normalization equals the immutable 0cc Git blobs; the validator binds raw Git
blob SHA for the cloud fixture and treats working-tree byte representation as
record-only local provenance. No functional RTL was changed.

## Server command and expected formal return

After verifying the ZIP SHA and extracting into a new empty parent:

```bash
cd r5_n4_0cc_p8f
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected returned files:

- `/home/panqs/ndp/NDP_copy02/r5_n4_0cc_p8f_return.zip`
- `/home/panqs/ndp/NDP_copy02/r5_n4_0cc_p8f_return.zip.sha256`

Formal pass requires the conjunction:

- production compile exit `0`;
- run exit `0`;
- signal `NONE`;
- actual 8-leaf compile identity collected and returned;
- 27/27 natural terminals;
- formal D readback count `320`;
- missing D count `0`;
- mismatch byte count `0`;
- result status:
  `CONV_NATIVE_FOUR_LANE_0CCAE916_FULL_SERVER_PASS`.

Before that formal return, p8f claims no natural-terminal result, no formal
320D result, and no performance E3/E4/E5.

## Frozen occurrence and traffic inversion

These are final-config/occurrence-derived, not measured server performance:

- logical products: `205,520,896`;
- serialized occurrences: `205,520,896`;
- native occurrences: `51,380,224`;
- compute occurrence reduction: `4.0x`;
- serialized weight payload: `262,144 B`;
- native weight payload: `65,536 B`;
- weight reduction: `4.0x`;
- serialized single-B activation payload: `51,380,224 B`;
- native B per producer: `12,845,056 B`, `4.0x` reduction;
- native B′ per producer: `12,845,056 B`, `4.0x` reduction;
- native combined B+B′: `25,690,112 B`, `2.0x` physical reduction versus
  serialized single B;
- serialized maximum useful lane utilization: `25%`;
- native maximum useful lane utilization: `100%`.

## Tool receipts

- p7 analyzer:
  `tools/analyze_conv_native_four_lane_0ccae916_p7_return.py`
  SHA256
  `ad8d3ecc93d26e8306ac3dc53e743f98c392384880a364c8d39bde2392cbd35c`
- p8f builder:
  `tools/build_conv_native_four_lane_0ccae916_p8f_full_package.py`
  SHA256
  `aa2ae051ffd6fb7447ce7c5638e9b35fcc662d7659b28e2413a20b7d7b939664`
- p8f validator:
  `tools/validate_conv_native_four_lane_0ccae916_p8f_full_package.py`
  SHA256
  `b9594ce3cacd2bf1a4b7cd9c3d486dbd537834e3d564659bb436d9eaceee4b57`

## Rule feedback

`RULE_CONFIRMATION`

- Actual/local/cloud identity differences after a successful compile are
  returned evidence and do not block simulator launch.
- A timeout with monotonically increasing qualified trace is not a functional
  hang proof.
- Formal D omitted by a c0 diagnostic is neither a formal D pass nor failure.
- Changed runner/finalizer logic is blocking-applicable.
- Byte-equal numeric/W3/golden/config/address/observer semantics use receipt
  reuse or record-only applicability and are not recomputed.
- Formal native-four-lane acceptance remains conjunctive: actual identity
  receipt, natural terminal, 320/320 D, missing=0, mismatch=0.

`RULE_DELTA_PROPOSAL=[]`
