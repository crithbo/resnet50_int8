# GAP node0071 v20 return and v23 RD-data-valid-path successor

Date: 2026-08-03  
Owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## RETURN_ANALYSIS

- Formal return:
  `r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix_return.zip`
  (`113340` bytes,
  SHA256 `59cef2d1051f9f4d38f65c473b8ed2e421d4f603fcdee7faef9844a2b6e603e5`).
- The adjacent external sidecar was absent and was accepted only under
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`. ZIP CRC,
  single-root/path safety, duplicate/symlink rejection, internal identity,
  `RETURN_MANIFEST`, exact-set, allowlist and per-file receipts all passed.
- Frozen source ZIP:
  `r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix.zip`
  (`1810686` bytes,
  SHA256 `a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3`).
  Returned package manifest and SCA/SCA_D were byte-bound to it.
- Package/install preflight, runtime-D-absent, observer identity and actual
  compile/simulator argv bindings passed.
- Compile exited `0`; simulation and runner exited `125` after `INT`.
  There was no natural terminal. All 48 formal D targets were missing.
  `mismatch_byte_count=0` was unevaluable and the conjunction gate failed.
  E3/E4/E5 are all false.

## LAST_PROVEN_GOOD / FIRST_DIVERGENCE

- `LAST_PROVEN_GOOD`: during `sum_s1`, 32 qualified GA inputs and 32 GA
  outputs were accepted. MSE4 accepted 8 write-data beats on each channel,
  with one outstanding request on each.
- The factor equations are:
  `buf_ag_bp_pre = !buf_ag_ob_full && rd_data_chl_data_ready &&
  !nse2mse_req_barrier` and
  `rd_data_chl_data_ready = rd_data_chl_data_vld &&
  !rd_data_chl_ob_full`.
- Final MSE0/MSE3 state had output-full `0/0`, barrier `0/0`,
  RD-output-full `0/0`, ready `0/0`, data-valid `0/0`, and prepared count
  `0/0`. Stable levels were not counted as progress.
- `FIRST_DIVERGENCE`:
  `RD_DATA_CHANNEL_DATA_VLD_ABSENT_AFTER_INITIAL_SUM_S1_PROGRESS`.
- `HANG_ROOT_CAUSE`:
  `LONG_RUNNING_HANG_AT_MSE0_MSE3_RD_DATA_CHANNEL_DATA_VLD_LOW_PENDING_INGRESS_OR_PREPARED_WRITE_LEAF`.
  v20 cannot uniquely distinguish memory-return, RD inbuffer, queue pairing
  or prepared-data-write responsibility.

## Continuous successor closure

The fresh successor adds only a bounded, package-local, read-only MSE0/MSE3
`RD_DATA_VLD_PATH` observer around the unresolved interval. It does not drive
the DUT, change timeout, enable per-cycle logging, or change functional RTL.

- v21 ZIP SHA
  `898fc7ab72a062722c13fefa60a232e1bf361b6b799cd9cb1f8c248709b4bde2`
  is quarantined: the safe runner control found
  `rd_data_path_ok: unbound variable` in the common finalizer.
- v22 ZIP SHA
  `5e9bf8ae98833a967ae5c9c8a41fb06ac91b691afa34dc1cf795f86857d2e821`
  is quarantined: final-ZIP audit found the applicable
  `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001` ID absent from
  its manifest.
- The unique releasable identity is
  `r5_n71_gap_v23_rd_data_vld_path_rulefix`.

Frozen reuse receipts:

- 73 numeric/workload files are byte-identical to v20.
- 119 other out-of-scope files are byte-identical to v20.
- Numeric/sum/tail/workload/config/golden analysis was not repeated.
- Config semantics were not rebuilt.
- Functional RTL was not modified.

## PACKAGE_RELEASE

Status: `PACKAGE_READY_NOT_RUN`  
Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`  
Candidate release: `false`  
Evidence ceiling: `E2_LOCAL_ONLY`

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v23_rd_data_vld_path_rulefix.zip`
- ZIP bytes: `1810719`
- ZIP SHA256:
  `07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19`
- Sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v23_rd_data_vld_path_rulefix.zip.sha256`
- Sidecar SHA256:
  `af156dd25fc467ad9a21eb8cd9229b3194c37e2e5665b6a5460b9704765fb7bd`
- Single command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- Expected return:
  `r5_n71_gap_v23_rd_data_vld_path_rulefix_return.zip`
  and its generated `.sha256`.

Final-ZIP audit passed with `errors=0`: CRC, manifest exact-set/current rule
receipts, runtime-D-absent, return allowlist, two deterministic builds,
fresh-extract preflight, canonical self-test and bash syntax all passed.
The real runner reached the safe compile stub (`exit=86`); wrong identity
failed before compile (`exit=5`). Five runner controls and 39 feature controls
failed closed. The real fresh-extract runner also exercised `TERM` through the
common finalizer (`exit=125`) with empty stderr, one finalizer epoch, complete
declared partial artifacts, exact-set return, correct feature argv/receipt
binding, and no false natural-completion claim.

No upload, server execution, or lease occurred.

## Receipts

- Return analysis report:
  `artifacts/operator_config_validation/r5-gap-node0071-v20-return-analysis/report.json`,
  SHA256 `d14c7c2c07bd83cb09b723a6839978286d5e9fda2fded344a6e30d97c832bf94`.
- Continuous-closure machine report:
  `artifacts/operator_config_validation/r5-gap-node0071-v20-return-analysis/closure_report.json`,
  SHA256 `c9c4daa5a23dc365b526295be8af3d1cca3735f7edf0112f8925d24cbf97915f`.
- Build report SHA256:
  `e3d70738d544f5b0164c42fa5a6cbba9d5d1bc8299e4ac693e295ff88664741f`.
- Runner report SHA256:
  `7e87b9d6c2192f50f3c33bfa89da0de64bf953ec739661b73d6e700762f91822`.
- TERM signal report SHA256:
  `92f9f713df63352949a0d778d01a11f9da08216ad521b4fa875f7aa35d9e520c`.
- Final-ZIP audit SHA256:
  `193c7b0e1a42582185b3875b6e751c745e9d46a1022ff97027da25066cbb4a26`.
- Current rule receipts: index
  `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8`;
  server
  `7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141`;
  operator
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`;
  NDP
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`;
  GAP mac
  `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b`;
  GAP probe
  `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1`;
  exact tail
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`.
- Plan SHA at final audit:
  `4aecafb0bd4c76ad21fdf670a9774b4860a7efef23fb0ad8b73e47f2178f9b56`
  (mutable provenance only).

`BLOCKER_DELTA`: readiness/barrier ambiguity was narrowed to
`rd_data_chl_data_vld==0`; the leaf below that signal remains for v23.

`RULE_DELTA_PROPOSAL`: `NONE`.
