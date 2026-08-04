# Conv node0004 v26 return → v28 D-write path successor

Date: 2026-08-03  
Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`  
Target mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Scope and receipts

- Frozen numeric/W3/qparam/tail/workload/golden and functional RTL were
  reused read-only.
- No server upload/run/lease occurred.
- `.agents/agent.md` SHA256
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`.
- `.agents/plan.md` dispatch SHA256
  `dbd88421ff90e4f15bb919cbd1f8fdb7f88917e6af5de232253a20405162080b`;
  mutable provenance only.
- index SHA256
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`.
- server-package rule SHA256
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`.
- INT8-SA rule SHA256
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`.
- hardware README SHA256
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`.

## RETURN_ANALYSIS

Formal return:
`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v26_transout_threshold_fix_return.zip`,
96874 bytes, SHA256
`2a3e041737376a8afdfcb70d85e30c9f4c7fbc12d5bdad94c9ec2c9b7fa78d68`.
The missing adjacent return sidecar is content-neutral under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`; all internal
receipt, exact-set and source-binding gates remained enforced.

The return passed CRC/root/path/duplicate/symlink, RETURN_MANIFEST,
allowlist/per-file receipts, source-package identity, package/install
preflight, runtime-D-absent, observer identity, actual compile/runtime argv
and feature-time0 binding. Compile and run exits were zero, signal was
`NONE`, and simulation started.

The authorized `special_array.transout_last_index 2→5` fix was dynamically
crossed: 128 qualified terminal accepts were all `terminal_equal`, with
`terminal_ignore=0`; 28 D requests and 28 D write-data beats were accepted.
The old SA final-release blocker is therefore closed.

Natural terminal did not occur. Formal D was 0 present / 320 missing /
0 mismatch. `mismatch=0` is not a pass when all formal D is missing.
E3/E4/E5 remain false.

Qualified stall evidence was `qualified_progress=234`, then four consecutive
zero-delta windows, with `slice_finish=0`.

- LAST_PROVEN_GOOD:
  `D_WRITE_REQUEST_AND_WRITE_DATA_ACCEPTED_28_AFTER_TRANSOUT_TERMINAL_MATCH`.
- FIRST_DIVERGENCE:
  `D_WRITE_DATA_ACCEPT_TO_BUFFER5_NEXT_READ_OR_LAST_INDEX0_SLICE_FINISH`.
- Root cause is not yet unique. `slice_finish=0` is a consequence. The one
  still-missing boundary is MSE4 `RD_Buffer_AG` tag/read acceptance through
  `WR_Data_Channel` last propagation.
- The old occupancy blocker remains
  `INVALIDATED_NOT_RTL_BUG` and was not reopened.

Machine return report:
`outputs/conv_node0004_v26_return_analysis/report.json`, 15433 bytes,
SHA256 `cde5c8fb02f8e0b49d0f334eee585d26caebe101088112d96247f4c7f316b2d0`.

## Successor and audit escape

The first locally built successor v27 correctly added the narrow HDL
observer, but runner positive control exposed that its return collector still
enumerated only the old four diagnostic features. The actual argv included
`RETURN_OBS_DWRITE_PATH`, but the formal feature receipt could not bind it.
v27 SHA256
`9c6c2e18435a52817e68079ccfd8c965332bff83384049eef841a19713ec1778`
is quarantined as `FEATURE_RECEIPT_BINDING_INCOMPLETE`.

Fresh v28 changes only the collector feature contract and identity relative
to v27. Relative to frozen v26, the only normalized changes are:

1. `PREPARE_AND_RUN.sh`;
2. `README.md`;
3. `package_manifest.json`;
4. `package_tools/node0004_hang_localization_runtime.py`;
5. `tb_probe/native_return_observer.svh`.

All `workload/runtime/**`, including matrices, configuration, bitstream,
execplan and SCA, are byte-identical after identity normalization.

v28 narrow qualified counters cover:

- MSE4 buffer-AG tag accept, last and last-index0;
- Buffer5 read accept, last and last-index0;
- WR-data prepared-data accept and last;
- write-data outbuffer accept/last;
- memory write-data accept/last;
- slice finish.

Queue count/full/empty, current tag/index, prepared count and last-flag state
are corroboration only and do not count as progress.

## Commands and exits

1. v26 analyzer:
   `python tools/analyze_node0004_v26_return.py ...` → exit `0`.
2. v28 deterministic builder:
   `python tools/build_node0004_v27_feature_receipt_fix_package_v28.py`
   → exit `0`; two independent ZIP builds matched.
3. focused HDL/scope validator:
   `python tools/validate_node0004_v27_dwrite_observer_scope.py ...`
   → exit `0`; positive `0`, typo-leaf negative `1`,
   deleted-declaration negative `3`, missing-task-end negative `2`.
4. runner/signal/canonical validator:
   `python tools/validate_node0004_v28_runner_controls.py ...`
   → exit `0`; safe simulator exit `74`, TERM finalizer exit `143`,
   canonical negatives `5/5` fail closed.
5. final ZIP self-audit:
   `python tools/validate_node0004_v28_final_zip.py ...`
   → exit `0`; feature enable/limit/time0/return-target negatives `4/4`
   fail closed.

Audit assets:

- observer scope: 4244 bytes, SHA256
  `eec91fc9e65d000719c281def4251ccb590be9735ac6ffac18eece768957161b`;
- runner controls: 8544 bytes, SHA256
  `337ee4a6f1ae44802105001d097e024c3c9230e5201be9360777264ca41c3c48`;
- final audit: 23072 bytes, SHA256
  `9903460c76f176bf4816499c5d6483a1d746be660ef3ea9944a05e85a4d2e6d1`;
- successor release report: 5152 bytes, SHA256
  `e676d6fb621be340b92b6e4daf4bc76b81aaf10d5b08abf7763f1614ba425f12`.

## PACKAGE_RELEASE

`PACKAGE_READY_NOT_RUN`:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v28_dwrite_path_diag_bind.zip`,
  5832618 bytes, SHA256
  `a3b2be33d395356b06c96e8311c017544cbdcc7b3e553006ae582acea176101f`;
- sidecar: 105 bytes, SHA256
  `d5ac9edd25b06c8782460170a0c0adb8efadbdfb4ded3dfcb272820810b830f9`;
- command:
  `bash r5_n4_hw_v28_dwrite_path_diag_bind/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`;
- expected return:
  `r5_n4_hw_v28_dwrite_path_diag_bind_return.zip`;
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=0.

## BLOCKER_DELTA and rule feedback

Closed:

- `B_CONV_NODE0004_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL`;
- `B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED`.

Opened:

- `B_CONV_NODE0004_D_WRITE_TO_LAST_INDEX0_SLICE_FINISH_UNOBSERVED`.

Preserved:

- `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`;
- `B_CONV_NODE0004_FORMAL_D_320`.

RULE_CONFIRMATION:
`CONFIRMED_SUFFICIENT_NO_RULE_DELTA`. The current rules forced the final ZIP
direct audit, focused HDL syntax/scope controls, real runner-to-safe-compile
control, canonical fail-closed records and end-to-end feature
enable/limit/time0/return binding. Those gates caught v27's collector omission
locally and required a fresh v28 identity; no non-synonymous public rule gap
was found.
