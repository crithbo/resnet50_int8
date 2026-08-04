# QLinearAdd node0007 v18 column-pair release

Date: 2026-08-02

## Scope and reuse

- Reused the frozen 17-instance/W3/six-qparam/exact-tail/workload/golden assets.
- Reused the already rebuilt v18 empty-state mapping/bitstream/execplan/SCA chain.
- `numeric_analysis_repeated=false`
- `workload_analysis_repeated=false`
- `config_numeric_analysis_repeated=false`
- `functional_rtl_modified=false`
- No server inspection, upload, lease, or run was performed.

## Current rule receipts

- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025`
- `.agents/rules/QLinearAdd算子配置规则.md`
  `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- `.agents/rules/精确UINT8量化尾专项规则.md`
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

The post-generation full reread matched the generation receipts. The decisive
family rule is
`CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`.

## D-buffer window proof

For each of `op_relocation_pad`, `op_tail_mul`, and `op_tail_round`:

```text
buffer_row_bytes = BUFFER_BANK_NUM * BUFFER_BANK_DATA_NUM
                 = 8 * 4 = 32 bytes
mse_read_bytes   = MSE_BUF_REQ_NUM * MSE_BUF_REQ_DATA_WIDTH / 8
                 = 16 * 8 / 8 = 16 bytes
accepted ROW/COL pairs = (0,0), (0,16)
windows = [0,16), [16,32)
disjoint union = [0,32) = one complete write transaction
actual max physical row = 0
buffer5.buf_end_row_addr = 0
```

The final address-bound JSON and decoded bitstream agree on:

- `GROUP2.ROW_LC.end=1`
- `GROUP2.COL_LC.end=32`
- `GROUP2.COL_LC.stride=16`
- `buffer5.buf_end_row_addr=0`

The active RTL proves that Buffer_AG accepts ROW/COL as one paired FIFO word
only when all index inputs match and `mse_enable` is true. `RD_Buffer_AG`
splits that same word and expands byte-addressed columns; the buffer request
manager uses the low column bits as byte offset and the high bits as bank.

Local report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-column-pair-v18/targeted_validation_report.json`
SHA256
`a0cb21fd6213692d0921aee3bc19e539ddd29a5f8606ee4a63188527cf59159f`.

All seven local rule negatives fail closed: deleted window, overlap/gap,
restored stride 2, unused second row, MSE width tamper, transaction-length
tamper, and `buf_spatial_size`-only change.

## Fresh server package

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_colpair_v18.zip`
- bytes: `38035285`
- SHA256:
  `570abd6f483f47f144ae9cb9320418e4acd423e2cf011e1f44a0f5b2537edd1a`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_colpair_v18.zip.sha256`
- sidecar SHA256:
  `05c36c5722c11e4e320852ba40b774a42e211ab0c004626e7dd5ac56b741b635`
- source v16 SHA256:
  `a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5`
- deterministic second build:
  package tree equal and ZIP SHA equal.

The only payload changes outside the three fresh bitstreams/unchanged
execplan namespace are package identity/manifest/README and a package-local
diagnostic parser correction: an `active_cycles` decrease is treated as a
stage transition reset, while a negative qualified-counter delta inside a
stage remains a diagnostic failure. This changes no DUT input, configuration,
ready/backpressure, timeout, formal D, golden, or functional RTL.

## Final ZIP audit and commands

Local v18:

```text
.venv\Scripts\python.exe tools/validate_qlinearadd_node0007_d_buffer_column_pair_v18.py
exit=0
```

Final ZIP:

```text
.venv\Scripts\python.exe tools/validate_qlinearadd_node0007_d_buffer_column_pair_v18_server_package.py
exit=0
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
all_required_negative_controls_fail_closed=true
```

Final report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-column-pair-v18/final_zip_self_audit.json`
SHA256
`9b562b6e0c11b696f1c0a53abff4fd9800ba8b010c3a79b5ec72e4e1b193ecaa`.

Runner positive/negative controls:

- fresh-extract package bootstrap: exit `0`, tree unchanged;
- real runner to safe compile stub: exit `86`, compile stub reached;
- wrong payload identity: exit `5`, compile stub not reached;
- each of eight final D-buffer contract negatives: exit `1`;
- each of two stage-scoped canonical parser negatives: exit `1`;
- inherited observer/config-preload/canonical/runtime-feature negatives also
  all fail closed.

Directed tests:

```text
.venv\Scripts\python.exe -m unittest \
  tests.test_qlinearadd_node0007_d_buffer_column_pair_v18 \
  tests.test_qlinearadd_node0007_d_buffer_column_pair_v18_artifacts \
  tests.test_qlinearadd_node0007_d_buffer_column_pair_v18_server_package -v
exit=0
9 tests passed
```

## Release state

```text
PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN
candidate_release=false
evidence_level=E2_LOCAL_ONLY
```

Server command:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return:
`r5_qadd_n7_dbuf_colpair_v18_return.zip`.
The server-generated return sidecar remains locally self-checked; user upload
is optional under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.

Open blocker: E3/E4/E5 remain open until this exact package identity runs to a
natural terminal and returns all 28 formal D targets with `missing=0` and
`mismatch=0`.
