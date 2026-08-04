# Conv/SA node0004 v18 return 与 v19 Buffer0 flow 窄诊断

## Scope / receipts

- unique mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- plan receipt (mutable provenance): `523afbf1f98258940a7333754ea684b519fe51f6c3ac08c6a7ad985461c77f75`
- `.agents/rules/生成前必读索引.md`: `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`: `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
- `.agents/rules/INT8_SA点积专项规则.md`: `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/算子配置规则.md`: `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`: `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

Final-ZIP 生成后重新完整读取上述活动规则/入口，SHA 无漂移。

## RETURN_ANALYSIS

- return ZIP: `r5_n4_hw_v18_a_reuse_diag_return.zip`
  - bytes: `77452`
  - SHA256: `c064ea3a88bbba648f2d9fedb4cf8c1f833680711820014d62a2013bb3fa69c0`
- adjacent sidecar:
  - file SHA256: `e32f9cf32eae861ea041b983790e915f99355944c90e1c3e89368a390757d337`
  - declared name/hash exactly match: `true`
- bound source ZIP: `r5_n4_hw_v18_a_reuse_diag.zip`
  - SHA256: `aa12edc55f10e28133e843e3ddeff832831a8d8c71cef47c5bc69e7c48f73fc1`
- ZIP CRC, single root, exact-set, return allowlist, package/install/observer preflight: `PASS`
- compile/elaboration: exit `0`
- run wrapper: exit `0`
- signal: `NONE`
- simulation: started; diagnostic fatal after four qualified zero-delta windows
- natural DUT terminal: `false`
- formal D readback members: `0`; therefore E4/E5 and the joint result gate are `FAIL_CLOSED`
- `mismatch=0` with all D missing is not a numerical pass.

Canonical progress record remained the broad
`LONG_RUNNING_HANG_AT_BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS`.
The unique `A_REUSE_BOUNDARY_V1` record supplies the earlier, tighter boundary:

- MSE0 request/data accept Buffer0/1: `2/0`, `2/0`
- Buffer0/1 qualified read: `1/0`
- SA source0/source1 qualified accept: `1/0`
- ALU-to-outbuffer qualified cycles: `1`
- producer select: `mse0_req_sel=0x1`
- SA consumer select: `sa_src_sel=0`
- Buffer0 final read tag: `0x5` (last-index field present, no bank-valid bits)
- Buffer0/1 memory/array clear edges: all `0`

This proves two 16-byte MSE0 payloads formed the first 32-byte Buffer0 row, that
row was read once by SA source0, and all 64 ALUs accepted/wrote the first
product. It also proves the producer and consumer selectors agree on Buffer0,
so the previous selector-divergence hypothesis is excluded.

## FIRST_DIVERGENCE

- last good:
  `MSE0 two payload accepts -> Buffer0 first qualified read -> SA source0 first
  accept -> 64 ALU first outbuffer writes`
- first bad:
  after that read, neither Buffer0 nor Buffer1 produces a second qualified
  read/SA accept, while Buffer0 has no valid bank bits.
- exact interval:
  `BUFFER0_FIRST_READ_TO_BUFFER0_NEXT_ROW_VALID_OR_READ`

Level signals are used only as snapshots. The first-divergence decision above
is based on qualified request/data/read/accept/write events.

## HANG_ROOT_CAUSE

Classification:
`UNRESOLVED_BUFFER0_VALID_LIFETIME_SUBBOUNDARY`.

The return proves the failed interval but does not uniquely distinguish these
three internal causes:

1. MSE0 `WR_Buffer_AG` did not generate/enqueue/dequeue the next row;
2. Buffer0 row-valid/full/clear state prevented the next write/read;
3. Buffer0 `Array_Request_Manager` address/lifetime state did not advance to
   the next readable row.

No functional RTL defect and no configuration-semantic defect is claimed from
v18. The one missing runtime boundary justifies one narrower diagnostic
successor; it does not justify a functional repair.

Read-only source receipts:

- `Stream_Engine.sv`: `13d4f6c3aa023205a895345392bec26e067fa10be5ad3f0228dc5d12e8447d07`
- `Memory_RD_Stream_Engine.sv`: `bd1517259b2ca848d9b4923030030d18513b1ed75c7f5f0683e2cf8ffa794130`
- `WR_Buffer_AG.sv`: `8db8ad4af47a3ddf911ab18a178fdc5288d7daebe8694c5c7380d8bea4e98c2b`
- `Buffer.sv`: `461736f72dc25c79b0f12f310f00d90c1da0f1be0d89d3bcc0f8d4cf4a7ca690`
- `Array_Request_Manager.sv`: `112be21e7e1ec7e7c863086778d887cb09ac39a7f28d59f5e9b3e8c29ca71a49`

## v19 diagnostic successor

Identity:

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v19_buffer0_flow_diag.zip`
- ZIP SHA256: `0420907934a5a603ea40a127128664affe0182b7d6bc986107e0b0b04303adf3`
- bytes: `5819648`
- sidecar SHA256: `2b8583d81c91f98a3863bda35e9065600cab6059297057e19821cea67f4eab16`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- status: `PACKAGE_READY_NOT_RUN`

v19 preserves the frozen v18 workload/config/mapping/bitstream/execplan/SCA
and adds one unique `BUFFER0_FLOW_BOUNDARY_V1` record:

- qualified `WR_Buffer_AG` enqueue/dequeue;
- qualified MSE-to-Buffer request accept;
- qualified Buffer0 ARM request accept;
- ungated snapshots for AG queue/full/empty/current row/tag;
- Buffer0 row0/row1 bank-valid maps and MRM/ARM ready;
- ARM array counter/address/lifetime.

It contains no functional RTL change and no configuration change.

Final-ZIP self audit:

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- real runner -> safe compile stub positive control:
  expected/observed stub exit `73/73`, invocation count `1`
- semantic negatives, each expected/observed exit `1/1` and fail closed:
  missing observer source; missing `+incdir`; missing enable macro; missing
  runtime binding; missing flow record; diagnostic mislabeled as fix; compile
  stub not reached.

Server command:

`bash r5_n4_hw_v19_buffer0_flow_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`

Expected return:
`r5_n4_hw_v19_buffer0_flow_diag_return.zip`.

## BLOCKER_DELTA

- closed: v18 package identity, compile/elaboration, observer four-way binding,
  runtime start, producer/consumer selector divergence, first SA/ALU accept.
- open: Buffer0 post-first-read next-row valid/lifetime sub-boundary.
- E3: `PASS`
- E4: `FAIL_CLOSED`
- E5: `FAIL_CLOSED`

## RULE_DELTA_PROPOSAL

`NONE`.

## Claim boundary

- `numeric_analysis_repeated=false`
- `node0004_workload_rebuilt=false`
- `configuration_rebuilt=false`
- reuse consumed: frozen v18 package/config/mapping/bitstream/execplan/SCA and
  active read-only RTL only
- plan/rules/functional RTL modified: `false`
- server inspected/uploaded/run: `false`

