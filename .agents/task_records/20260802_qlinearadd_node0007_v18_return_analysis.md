# QLinearAdd node0007 v18 return analysis

Date: 2026-08-02

## Scope and immutable inputs

This record analyzes only the formal v18 return:

`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_dbuf_colpair_v18_return(1).zip`

- bytes: `278142`
- SHA256:
  `ee21c207e9e3244eaea4993ab0b05bc3907af6dbe633f904ad0a1088118cd7aa`
- `(1)` is a local download collision suffix and has no package identity effect.
- The adjacent return sidecar is absent. This is accepted only at the external
  transport layer under the user's attestation and
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.
- Internal CRC/path/root/identity/manifest/allowlist/result gates were not
  relaxed.

Frozen source package:

`artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_colpair_v18.zip`

- bytes: `38035285`
- SHA256:
  `570abd6f483f47f144ae9cb9320418e4acd423e2cf011e1f44a0f5b2537edd1a`
- source sidecar SHA256:
  `05c36c5722c11e4e320852ba40b774a42e211ab0c004626e7dd5ac56b741b635`
- source final-audit SHA256:
  `9b562b6e0c11b696f1c0a53abff4fd9800ba8b010c3a79b5ec72e4e1b193ecaa`

No numeric, W3, six-qparam, exact-tail, workload, configuration, or golden
analysis was repeated. No package was generated. No server was inspected,
uploaded to, or run. No plan, public rule, functional RTL, or other family
asset was modified.

## Provenance

- `analysis_owner_thread`:
  `019fa2c0-b647-7a91-93bf-d21a173487e3`
- `return_target_thread`:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`

These values are also bound exactly in the machine report's top-level
`provenance` object.

## Current control receipts

All immutable receipts matched:

- `.agents/agent.md`:
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- `.agents/rules/生成前必读索引.md`:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`:
  `fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025`
- `.agents/rules/算子配置规则.md`:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/QLinearAdd算子配置规则.md`:
  `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

The mutable plan receipt matched the dispatched value:

- `.agents/plan.md`:
  `07196fe91d362f6379681fe21bf7ef3a9a6a7661048dfe0284680d16c4529f68`

## Return integrity and identity

- ZIP CRC passed.
- Exactly one internal root exists:
  `r5_qadd_n7_dbuf_colpair_v18_return`.
- 20 files, no duplicate, symlink, traversal, backslash, or out-of-root member.
- `RETURN_MANIFEST.json` size/SHA receipts match every returned member.
- Returned exact-set equals the manifest exact-set.
- Every returned target is in the frozen package return allowlist.
- Computed missing required set exactly equals the manifest's 28 formal-D
  paths.
- Returned `evidence/PACKAGE_MANIFEST.json` is byte-for-byte and semantically
  equal to the frozen source `TEST_PACKAGE_MANIFEST.json`.
- Package, install, run, and return identities all bind
  `r5_qadd_n7_dbuf_colpair_v18`.
- Package and installed preflights are valid; formal D targets were absent
  before runtime; neither preflight inspected server sources.
- Actual simulator argv binds the frozen `sca_cfg.json` and `sca_cfg_D.json`;
  the result gate confirms exact preload and SCA echo checks.

## Observer and execution

The observer source, package-local `+incdir`, enable macro, actual simulator
plusargs, time-zero marker, signal trap, and return allowlist are all present.
Compilation succeeded:

```text
compile_exit_status=0
simulation_exit_status=125
signal=INT
natural_terminal=false
```

Host simulator wall time is approximately 10.028 hours. The simulator reached
`266753961975 ps`.

The runtime canonical record is internally hashed and its parser exits zero,
but its decision is not semantically valid. It reports
`NATURAL_TERMINAL_OBSERVED` merely because any `COMP_FINISH` exists. The raw
ordered record contains four `EXEC_START` events and only three
`COMP_FINISH` events; the fourth execution is still active when simulation
exits 125/INT. Therefore the canonical record is a package diagnostic
conflict, not a natural terminal.

Individual MSE input `valid&&ready` counters and `buf5_rd` level/read-enable
samples were excluded from monotonic progress. They continue growing while
queue/AG/base accepted counters remain flat and lack one-to-one transaction
proof.

## Dynamic stage adjudication

Ordered completed stages:

1. `op_a_dequant`: `COMP_FINISH`, 540843 active cycles.
2. `op_b_dequant`: `COMP_FINISH`, 540857 active cycles.
3. `op_relocation_pad`: `COMP_FINISH`, 42984 active cycles.

The corrected relocation stage reaches:

```text
MSE4 request ch0/ch1 = 4224/4224
MSE4 wdata   ch0/ch1 = 4224/4224
MSE4 outstanding     = 0/0
```

This closes the old v16 relocation write-back hang. The static final
JSON/bitstream proof remains current-match for the approved v18 stages:
32-byte physical Buffer row, 16-byte MSE read, paired windows
`[0,16)` and `[16,32)`, no gap/overlap, actual max row zero.
The return does not expose accepted ROW/COL tag payloads and never reaches
`op_tail_mul` or `op_tail_round`, so it does not dynamically validate those
two stages.

The fourth stage, `op_fp32_add`, starts at `17536012000 ps` and never finishes.
After finite startup activity, its returned downstream snapshot is:

```text
base req/rdata/wdata = 781682/153029/614176
deep addr/meta/consume/buffer/ga = 21/21/5/1/0
SG ga_input/ga_output = 0/0
MSE4 req ch0/ch1 = 1/1
MSE4 wdata ch0/ch1 = 0/0
MSE4 outstanding ch0/ch1 = 1/1
```

These qualified base/deep/SG values remain unchanged for 198967296 active
cycles, or 189 complete 1048576-cycle stall windows. The INT therefore
interrupts a proven long hang; it is not merely a large computation that
failed to finish within an arbitrary one-hour expectation.

## Structured adjudication

```text
RETURN_ANALYSIS=VALID_INTERNAL_RETURN_EVIDENCE
LAST_PROVEN_GOOD=OP_RELOCATION_PAD_COMP_FINISH
FIRST_DIVERGENCE=OP_FP32_ADD_AFTER_FINITE_READ_ACTIVITY_BEFORE_GA_INPUT_ACCEPT
PROGRESS_ADJUDICATION=LONG_RUNNING_HANG_AT_OP_FP32_ADD_PRE_GA_INPUT
HANG_ROOT_CAUSE=NOT_UNIQUELY_IDENTIFIED_WITH_CURRENT_OBSERVER
E3=false
E4=false
E5=false
PACKAGE_RELEASE=NONE
```

The unique dynamic interval is:

`op_fp32_add stream0+stream1 read ingress / Buffer0+Buffer2 paired readiness
-> first qualified GA input accept`.

The existing observer covers selected MSE0 and MSE4 but not stream1/MSE1,
Buffer2 accepted write/row-bank valid, or the paired GA input tag/mask
consumer capture. It therefore cannot uniquely distinguish those remaining
leaves. The canonical parser defect is proven package-side, but it is
independent of the functional hang and must not be presented as the hang
root cause.

Formal D:

```text
expected=28
present=0
missing=28
mismatch_byte_count=0
mismatch_zero_evaluable=false
SERVER_RESULT_GATE.all_terms_true=false
```

`mismatch=0` is unevaluable because all formal targets are absent.

## BLOCKER_DELTA

Close:

- `B_QADD_NODE0007_STAGE3_RELOCATION_D_BUFFER_ROW_ONLY_SUPPLY`

Open:

- `B_QADD_NODE0007_FP32_ADD_PRE_GA_INPUT_HANG`
- `B_QADD_V18_CANONICAL_FINAL_STAGE_SCOPE`

The exact v18 source identity is now
`QUARANTINED_DYNAMIC_OP_FP32_ADD_HANG_AND_CANONICAL_CONFLICT`.

## RULE_DELTA_PROPOSAL

1. A multi-stage canonical terminal record must bind the expected ordered
   stage list and may report natural completion only when the final expected
   `EXEC_START` has its own `COMP_FINISH`.
2. QAdd progress validators must reject individual MSE input `valid&&ready`
   level counts as monotonic progress unless a one-to-one queue
   write/dequeue, consumer capture, or stable transaction-id witness is bound.

## SUCCESSOR_PROPOSAL_OR_NONE

Proposal only; no package was generated this turn. If mainline authorizes a
successor, it should be a narrow observer-only package that adds qualified
stream0+stream1/MSE0+MSE1 read acceptance, Buffer0/Buffer2 row-bank
valid/write acceptance, paired GA tag/mask readiness, and GA consumer
capture. It must leave numeric/W3/qparam/tail/workload/config/golden and
functional RTL unchanged.

## Machine artifacts and command

Analyzer:

`tools/analyze_qlinearadd_node0007_dbuf_colpair_v18_return.py`

- bytes: `37711`
- SHA256:
  `c9e6bed61e0afcde134b069ece034be36c9c2639138dd4ca626fd6f9f2a915b1`

Machine report:

`artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-column-pair-v18-return-analysis/report.json`

- bytes: `51966`
- SHA256:
  `a32a6023b930de3c25c1072d6692e11b36b012cbebed721b8f6fa890be66fdf8`

Read-only extraction:

`artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-column-pair-v18-return-analysis/extracted`

- files: `20`
- tree receipt SHA256:
  `1d6170c55965c1ecec96d6a1c19f6e1c42adb17b8be118930a681d1ce33e3cfe`

Validation:

```text
.venv\Scripts\python.exe -m py_compile \
  tools\analyze_qlinearadd_node0007_dbuf_colpair_v18_return.py
exit=0

.venv\Scripts\python.exe \
  tools\analyze_qlinearadd_node0007_dbuf_colpair_v18_return.py \
  "C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-08\r5_qadd_n7_dbuf_colpair_v18_return(1).zip" \
  --output artifacts\operator_config_validation\r5-qlinearadd-node0007-d-buffer-column-pair-v18-return-analysis\report.json \
  --extract-root artifacts\operator_config_validation\r5-qlinearadd-node0007-d-buffer-column-pair-v18-return-analysis\extracted
exit=0
```
