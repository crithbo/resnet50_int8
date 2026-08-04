# QLinearAdd node0007 v14 return adjudication and v15 D-buffer fix

Date: 2026-08-01  
Owner family: QLinearAdd  
Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

Input return:

```text
C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-08\r5_qadd_n7_cfgpreload_v14_return.zip
bytes=203770
SHA256=f342a2624da1cbaeeb97f8e8d41e0172f9e03573c20c0d1477a0195e1cb711cf
adjacent sidecar=false
```

The missing adjacent return sidecar is non-blocking under the user-attested
transport policy and
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.
This waiver covers only the external transport sidecar. ZIP CRC, safe paths,
single root, duplicate absence, internal `RETURN_MANIFEST` exact-set and
per-file hashes/sizes, source-package identity and returned package manifest
all pass.

Frozen source:

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cfgpreload_v14.zip
SHA256=78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282
```

Package/install preflight pass, preload count is 91, formal readback count is
28 and runtime D targets are absent before execution. Compile exits 0.
Simulation exits 125 with signal `INT`, without natural terminal. All 28
formal D files are missing and `mismatch=0` is unevaluable, so E3/E4/E5 are
all false.

Simulation wall time is `18236.802665323 s` (about 5.066 h). This is not an
unfinished normal run:

- `op_a_dequant` completes at `gconfig=52`;
- `op_b_dequant` completes at `gconfig=104`;
- `op_relocation_pad` starts at `gconfig=154`;
- its first and last stage-local qualified snapshots are identical for
  `40370176` active cycles, or `38.5` declared stall windows.

The v14 canonical parser is rejected for this adjudication because it compares
resetting active-cycle/counter epochs across three executions. A stale
dequant-target MSE input counter is not relocation progress.

## FIRST_DIVERGENCE / HANG_ROOT_CAUSE

Last good:

```text
six SCA config preloads are effective
op_a_dequant COMP_FINISH
op_b_dequant COMP_FINISH
op_relocation_pad EXEC_START
```

First bad stage-local snapshot:

```text
DEEP:
  addr_enqueue=36 req_hs=64 meta=36 consume=20
  buffer=16 ga=48 mse4_idx=3
SG:
  ga_input=48 ga_output=32
  mse4_req=(2,1)
  mse4_wdata=(1,0)
  mse4_outstanding=(1,1)
```

Those values remain unchanged through the final snapshot. The exact
configuration conservation equation is:

```text
WRITE_STREAM0 transaction bytes
  = product(idx_size[j] + 1), null => 1
  = 1 * 32 * 1
  = 32 bytes

v14 D-buffer supply
  = trip_count(GROUP2.ROW_LC) * stream2.buf_spatial_size
  = 1 * 16
  = 16 bytes
```

This is a deterministic configuration error, not an RTL or timeout-only
guess. It explains one accepted write-data beat, the peer write channel
remaining outstanding, the full MSE4 index queue and GA-output backpressure.
The same static undersupply exists in the not-yet-reached `op_tail_mul` and
`op_tail_round`.

Final root cause:

```text
QADD_D_BUFFER_TRANSACTION_SUPPLY_UNDERSUPPLY
```

## Minimal configuration fix and local closure

Only these two leaves change in each of:
`op_relocation_pad`, `op_tail_mul`, `op_tail_round`:

```text
buffer_loop_configs.GROUP2.ROW_LC.end: 1 -> 2
buffer_config.buffer5.buf_end_row_addr: 0 -> 1
```

All six final stages now satisfy D transaction/supply conservation:

```text
dequant A/B: 64B = 4 * 16B
relocation:  32B = 2 * 16B
FP32 add:    16B = 1 * 16B
tail mul:    32B = 2 * 16B
tail round:  32B = 2 * 16B
```

W3 order, all six qparams, exact UINT8 tail arithmetic, DRAM loops,
stream/address fields, occurrence, coverage, barriers, lifetime, tensor
payload, golden and functional RTL do not change. The frozen config-bound
numeric report is reused without recomputation.

All six mapping artifacts and the final execplan were rebuilt from empty
state. The independent native execplan validator is clean and the two native
runs are byte-deterministic excluding placement PNGs. The previously frozen
address/coverage/lifetime proof remains applicable because every DRAM loop,
stream leaf and base address is byte-identical; the only changed leaves are
the occurrence-internal D-buffer row supply.

The broad 37,352,448-request enumeration was stopped after it exceeded the
local command budget. It is not used to substitute for the targeted proof:
the frozen request/address set is unchanged, while the newly incorrect layer
is exactly the D-buffer supply equation above.

## PACKAGE_RELEASE

Unique successor:

```text
identity=r5_qadd_n7_dbuf_v15
status=PACKAGE_READY_NOT_RUN
claim=CONFIG_ONLY_CORRECTNESS_BASELINE
path=artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_v15.zip
bytes=38032365
SHA256=3beef62deeea914abff9120714f8a8fcbad13e9cc40cd0b2a6f68db74c0eac3a
sidecar=artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_v15.zip.sha256
sidecar_SHA256=ff21e3abbfa17e4d5edc5d621953a78fdd98793113a3f23ff7e0662572fc8f77
```

Server command:

```text
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return:

```text
r5_qadd_n7_dbuf_v15_return.zip
```

The runner still creates and locally validates the server-side return
sidecar, but the user need not upload it under the current transport rule.

Post-generation current-rule receipts:

```text
.agents/rules/生成前必读索引.md
  12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f
.agents/rules/服务器测试包生成规则.md
  fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025
.agents/rules/QLinearAdd算子配置规则.md
  c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b
```

Final ZIP self-audit:

```text
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
all_required_negative_controls_fail_closed=true
safe compile-stub positive: exit=86, compile reached=true
wrong identity negative: exit=5, compile reached=false
runtime feature four negatives: all exit=1/fail closed
D-buffer four negatives: all exit=1/fail closed
preload nine negatives: all exit=1/fail closed
```

The new
`CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001` is closed:
actual simulator argv contains `+RETURN_OBSERVER`, the package-local observer
banner is checked into `observer_binding.txt`, compile incdir/macro are bound,
feature receipt/log/canonical decision are allowlisted, signal traps collect
partial evidence, and delete-runtime-enable/delete-time0/delete-receipt/
delete-return-target controls each fail closed.

## BLOCKER_DELTA

- Closed: six SCA config preloads omitted.
- Closed: ambiguity between unfinished computation and hang.
- Closed: exact stage boundary; hang is in `op_relocation_pad`.
- Closed locally: 32-byte D transaction supplied by only one 16-byte row.
- Open: v15 has not been run on the server.
- Open: E3/E4/E5 and final bound server RTL identity.

## RULE_DELTA_PROPOSAL

Propose mainline-only rule:
`CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`.

For every QLinearAdd write stage, require:

```text
transaction_bytes = product(idx_size[j] + 1)
transaction_bytes =
  trip_count(GROUP2.ROW_LC) * stream2.buf_spatial_size
buffer5.buf_end_row_addr = trip_count(GROUP2.ROW_LC) - 1
```

The validator must evaluate this on final materialized JSON, and negative
controls must cover row undersupply and end-row mismatch. DRAM occurrence
loops must not be substituted for occurrence-internal D-buffer row supply.

## Reproduction receipts

```text
python tools/analyze_qlinearadd_node0007_cfgpreload_v14_return.py
exit=0

python tools/validate_qlinearadd_node0007_d_buffer_supply_v15_server_package.py
exit=0

python -m unittest \
  tests.test_qlinearadd_node0007_cfgpreload_v14_return_analysis \
  tests.test_qlinearadd_node0007_d_buffer_supply_v15 \
  tests.test_qlinearadd_node0007_d_buffer_supply_v15_server_package -v
exit=0
tests=10/10 PASS
```

Machine reports:

```text
artifacts/operator_config_validation/r5-qlinearadd-node0007-cfgpreload-v14-return-analysis/report.json
SHA256=e53abec98ab167d36b5e1b26ee89e2c6fda452ba9762a478a2a4b49973df2a99

artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-supply-v15/final_zip_self_audit.json
SHA256=dcef51ab309bf5288d5c5fc4de460a542efcd8c8308af329bfa7c6a97db6bf37
```

No 17-instance/W3/qparam/tail/golden/workload numeric analysis was repeated.
No server inspection, upload, execution or lease was performed. No plan,
public rule or functional RTL file was modified.
