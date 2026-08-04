# Conv/SA node0004 v19 return 与 v20 Buffer0/1 mode 修复

## Scope / receipts

- unique mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- plan receipt (mutable provenance):
  `0e3ec9d2346f9ff9561456cc1c9fb2653385214009a2eaeea46f731c85fc5183`
- `.agents/rules/生成前必读索引.md`:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`:
  `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/算子配置规则.md`:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

Final ZIP 生成后重新完整读取上述活动规则/入口，SHA 无漂移。

## RETURN_ANALYSIS

- return ZIP:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v19_buffer0_flow_diag_return.zip`
  - bytes: `77871`
  - SHA256:
    `aba139e405f894564ec105e5929a3b02e6d44c6aae1d004d898d6f6106e27205`
- directly adjacent return sidecar: absent
  - formal external-receipt gate remains fail-closed;
  - internal allowlisted dynamic evidence is independently consumable.
- bound source `r5_n4_hw_v19_buffer0_flow_diag.zip`:
  `0420907934a5a603ea40a127128664affe0182b7d6bc986107e0b0b04303adf3`
- CRC/single-root/exact-set/allowlist/package/install/observer preflight:
  `PASS`
- compile/elaboration `0`; run wrapper `0`; signal `NONE`
- simulation started; qualified deltas `[144,0,0,0,0]`; four zero-delta
  windows caused the controlled diagnostic terminal
- natural DUT terminal: `false`
- formal D members: `0`; E4/E5 and joint result gate remain fail-closed.

## BUFFER0_FLOW_BOUNDARY_V1

Qualified events:

- `ag_enq=2`, `ag_deq=2`
- `mse_req_accept=2`
- `arm_req_accept=1`

State-only snapshots:

- AG queue: `count=0`, `full=0`, `empty=1`
- MSE: `ready=1`, `req_valid=0`
- Buffer0: `row0_valid=0xffffffff`, `row1_valid=0`
- ARM: `counter0=1`, `counter1=0`, `addr=1`, `life=0`
- ARM request: `req_valid=0xff`, `ready=0`, `bank_ready=0`,
  `addr_update=0`, `data_valid=0`

Therefore:

1. `WR_Buffer_AG` generated and dequeued both row0 writes; the queue is not
   the blocker.
2. Buffer0 accepted one ARM read; row0 remains completely valid.
3. Immediately after that first read, ARM requests row1, but row1 was never
   populated, so every bank reports not-ready.

## FIRST_DIVERGENCE

- last good:
  `WR_Buffer_AG two enqueue/dequeue -> two Buffer0 writes -> first ARM read`
- first bad:
  `ARM address advances 0 -> 1 before the four-use row0 lifetime completes`
- exact boundary:
  `BUFFER0_FIRST_READ_TO_PREMATURE_ROW1_ADVANCE`

All progress conclusions use qualified handshake/edge counters. Level values
above only identify the state at the canonical decision.

## HANG_ROOT_CAUSE

`BUFFER0_1_MODE0_ADVANCES_ROW_BEFORE_LIFETIME`

The frozen v19 config set both `buffer0.mode` and `buffer1.mode` to `0`.
Active RTL proves:

- `Array_Request_Manager.sv:207-208`: mode chooses which counter end value is
  lifetime versus end-row;
- `Array_Request_Manager.sv:229-252`: accepted ARM request advances counter0,
  and counter1 advances only when counter0 ends;
- `Array_Request_Manager.sv:254-255`:
  - mode0: `array_req_addr=array_counter_0`,
    `array_life_cnt=array_counter_1`;
  - mode1: `array_req_addr=array_counter_1`,
    `array_life_cnt=array_counter_0`;
- `Buffer.sv:262,286-288`: an ARM read is ready only when the requested row is
  valid in all active banks.

With logical lifetime 4 and end-row 3:

- mode0 accepted-address prefix: `[0,1]`; it requests empty row1 after one
  read, matching v19 exactly;
- mode1 accepted-address prefix: `[0,0,0,0]`; the fourth accepted read clears
  row0, and the fifth address becomes row1.

This is a deterministic configuration-semantic error. No functional RTL
defect and no package/runtime defect is claimed.

## Minimal repair and local rebuild

Exactly two typed-materializer leaves changed:

- `buffer_config.buffer0.mode: 0 -> 1`
- `buffer_config.buffer1.mode: 0 -> 1`

Fresh config:

- `configs/native_ndp_sim/node0004_buffer_mode_fix_c0_v3/accumulate_waves/wave-0.json`
- SHA256:
  `e528e963ddd76d775dd648d54eaf8bf4114d0053e5035073b914d3e7625dd8e5`

Local closure:

- logical leaf diff: exactly the two leaves above
- mapping manifest:
  `a9fb3b358fd58ad27093235742fb7f1827152a58df25bf3063f48b3d61d5d540`
- bitstream:
  `1baf6986561eb9812d2c6e9adbe1c0c8ded0a1fade72a64b198d4f437bdd2388`
- execplan manifest:
  `e8b1f743b54cfb4bbc1553c78b2de07c0da3fb15e4cb1e00cb0bf4d1197ebba8`
- SCA:
  `4d0f27f395cf79340ea7c641d6f77185600a5a53e4ece4be128263e68cc59c22`
- frozen 84 A/B/C matrix payloads remain byte-identical.

Targeted test:

`.venv\Scripts\python.exe -m unittest tests.test_conv_sa_hardware_contract`

Exit `0`, `4/4 OK`.

The broader `tests.test_conv_instance` currently retains the already-known
legacy checked-in `conv_1x1_real.json` ping-pong mismatch and fails before this
new mode check; it is not used as v20 positive evidence.

## PACKAGE_RELEASE

- identity: `r5_n4_hw_v20_buffer_mode_fix.zip`
- classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`
- status: `PACKAGE_READY_NOT_RUN`
- ZIP bytes: `5819495`
- ZIP SHA256:
  `e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead`
- sidecar file SHA256:
  `6c2db91207f1638c8192ae0d9aa9fe6b67926a6957d4683b17d052ae848615e9`

Final-ZIP self audit:

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- safe compile stub positive control expected/observed `73/73`,
  invocation count `1`
- observer source/incdir/macro/runtime/flow record, classification, compile
  reachability, both mode leaves, fresh bitstream and rebuild declaration
  negative controls all exit `1` and fail closed.

Server command:

`bash r5_n4_hw_v20_buffer_mode_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`

Expected return:

`r5_n4_hw_v20_buffer_mode_fix_return.zip`

and adjacent `.sha256`.

## BLOCKER_DELTA

- closed:
  `WR_Buffer_AG` generation/queue, Buffer0 write, first ARM read, and exact
  mode0 premature row advance root cause.
- repair:
  Buffer0/1 row-stationary lifetime ordering is now materialized in config and
  physical assets.
- open:
  v20 server natural terminal and 320-item formal D readback.
- E3 for v19 diagnostic: `PASS`
- E4/E5 for node0004: `FAIL_CLOSED` pending v20 return.

## RULE_DELTA_PROPOSAL

Propose `CDA-BUFFER-MODE-INNER-COUNTER-OWNERSHIP-001`:

For every Buffer occurrence, the contract/validator must state whether row
address or lifetime is the inner counter. Under active RTL:

- `mode=0`: row address is inner; lifetime counts completed row sweeps;
- `mode=1`: lifetime is inner; the current row is reused for its full lifetime
  before row advance.

Any operator requiring per-row reuse must select mode1 and prove the accepted
address/clear sequence. Lifetime value alone does not prove reuse.

## Claim boundary

- `numeric_analysis_repeated=false`
- `node0004_workload_rebuilt=false`
- `configuration_rebuilt=true` only for the two mode leaves and their physical
  derivatives
- functional RTL modified: `false`
- plan/public rules modified: `false`
- server inspected/uploaded/run: `false`

