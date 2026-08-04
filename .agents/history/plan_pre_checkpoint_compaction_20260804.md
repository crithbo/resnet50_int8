# ResNet50 INT8 当前状态与短期计划

最后更新：2026-08-04

## 0. 文件职责

- 本文件只保留最新状态和最新短期计划，是可覆盖更新的活动快照。
- 状态变化直接改写本文件，不在末尾追加旧过程；被取代内容移入
  `.agents/history.md`，精确证据保留在 `.agents/task_records/` 与机器报告中。
- 当前唯一主线控制会话：`019fbec2-fe93-7e03-9314-cff6f222f33d`。
- 主线维护本文件与 `.agents/rules/**`；算子 owner 不得修改公共 plan/rules/功能 RTL。
- 冲突时以磁盘 current 规则、原始 package/return、机器报告和 task record 为准。

## 1. 全网当前状态

- ONNX 独立软件公式：`78/78`。
- typed hardware request：`133/133`。
- 正式 E4/E5：`1/78`，仅 DequantizeLinear node0077；该节点冻结。
- 当前没有 `SERVER_RUNNING` lease。
- 除 node0077 外，任何算子都不得宣称正式 E4/E5、production 或性能通过。

| 算子/范围 | 当前状态 | 当前裁决 |
|---|---|---|
| GAP node0071 | `PACKAGE_READY_NOT_RUN / V33_BUFFER_AG_IDX_PAIR_DIAG` | v32 已证明 lane1 丢在 MSE0 Buffer_AG index pairing/enqueue 前；v33 单包一次覆盖 queue input/tag/match/enqueue/dequeue 与直接 consumer |
| QLinearAdd node0007 | `PACKAGE_READY_NOT_RUN / SPLIT_C_PAIRMATRIX_V29` | v28 未到 FP32-add且observer跨阶段误标；v29已修stage scope并单包覆盖MSE0/MSE1→Buffer0/2→GA全部成对候选，D继续冻结 |
| MaxPool node0002 | `RETURN_CONSUMED / DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE` | 按用户/学长特例停止通用 successor，不重跑、不升级 E4/E5 |
| Conv node0004 serialized | `PACKAGE_READY_NOT_RUN / V35_ROWLC4_BUFAG_DIAG` | v33 已证明 LC18→PE7→MSE4 第7项完整守恒，唯一阻塞为 LC18 fanout→ROW_LC4 backpressure bit10；v35 同包覆盖 ROW_LC4/COL_LC4/Buffer_AG/RD_Buffer_AG/prepared-data 五类候选 |
| Conv native four-lane | `PACKAGE_READY_NOT_RUN / DF23E4D_P4` | p4 是从冻结 v1/E2/df23e4d 身份生成的短路径、完整 exact-set delivery successor；v1 及 p2/p3 只作历史，不再运行 |
| QuantizeLinear node0074 | `APPROVED_EQUIVALENT / WAIT_NODE0075_INTEGRATION` | node0072→View→node0074 成对消除与 metadata alias 已物化；通用 exact-divider blocker 保持链外开放 |
| DequantizeLinear | node0077 `E4/E5_PASS_FROZEN` | node0072 在冻结链中由 UINT8 storage alias 绕过，不重做算术 |
| View node0073 | `APPROVED_EQUIVALENT_UINT8_ALIAS / METADATA_OVERLAY_MATERIALIZED` | `[16,2048,1,1]→[16,2048]`、零 offset、无 copy/replay/relocate 已闭合 |
| QLinearMatMul node0075 | `WAIT_USER_DECISION / PRODUCER_BARRIER_INTEGRATION` | df23e4d 算术门、24-op handler/materializer、8-pass A reload 与 config-bound compositional E2 均闭合；node0075-only fresh-memory 流缺少 node0071 真生产者前缀及 producer-final→first-read 可见性屏障，尚无服务器包 |

## 2. 当前可运行包与后继构建状态

### 2.1 GAP node0071 v33

- v32 正式 return：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_gap_v32_col_ag_mrm_lane_rulebind_return.zip`，
  bytes=`133195`，SHA256=
  `6bf8f931104739d3f658959958d378fa97081ce7457b0098acff3b1ac3a07a6b`；
  内部 CRC/root/path/identity/manifest exact-set/allowlist/source binding 全通过。
- compile/simulation/runner=`0/125/125`、signal=`INT`、非自然终态；
  formal D=`0/48`，mismatch=0 不可评价，E3/E4/E5=false。
- `LAST_PROVEN_GOOD`：COL-LC0 接受值 1/3，且到达 MSE 写口的 8 项均被 MRM
  接受并保持 byte-lane strobe，包含 lane3。
- `FIRST_DIVERGENCE`：COL-LC0 lane1 值只在 MSE0 Buffer-AG 活动前出现；
  后续 MRM strobe 覆盖 lane0/2/3，但无 lane1。
- `HANG_ROOT_CAUSE=LONG_RUNNING_HANG_AT_MSE0_BUFFER_AG_INDEX_PAIRING_BEFORE_BYTE_LANE1_ENQUEUE_PENDING_INPUT_OR_MATCH_MASK_LEAF`。
  旧 COL_AG/MRM-strobe blocker 已关闭；新 blocker 位于 MSE0
  Buffer_AG_Idx_Queue input/match-mask，仍不能唯一化为配置或 RTL 根因。
- machine report：
  `artifacts/operator_config_validation/r5-gap-node0071-v32-return-v33-successor/report.json`，
  SHA256=`0c37f937316dfc09215f632a2d700b8607de665028d9b75d2057b88dc43d7676`。

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip
bytes   1,824,172
SHA256  5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03
sidecar SHA256 9bdb2cdb465d225d5dcd37746ba0e8e782cf3d2076a9b53625fe00b46cb46f1b
class   DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status  PACKAGE_READY_NOT_RUN
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
return  r5_n71_gap_v33_buffer_ag_idx_pair_diag_return.zip
```

- v33 按 information-gain 策略在同一包覆盖 COL-LC0、MSE0 两输入 accept/tag/index、
  valid/same/gotten/keep/masked、all-matched/mse-enable、enqueue/full/count、
  dequeue/output direct consumer；最多 256 个 qualified 事件。
- execution reduction 审计：无合法 FD 前 typed checkpoint；`sum_s1` 是首阶段且卡死后
  后续 stage 不启动，删除后续 stage 不会减少本次动态墙钟，故 keep=完整 ordered prefix、
  drop=[]。该结论是不可裁剪证据，不是因“最窄”机械保留。
- 双构建一致；67 项 feature negatives、runner/TERM/focused-HDL 负控全部 fail closed；
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0，audit SHA256=
  `2a3b72a6683b3869785c4816036b7eed9ffefb08210246b5ffda75270f772b93`。
- 新公共 time-to-root-cause 规则发布后，冻结 v33 通过
  `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`；六候选判别矩阵、256 qualified
  limit、causal keep/drop、无 checkpoint、`drop=[]` 不降墙钟证据及六类负控均闭合，
  ZIP/sidecar/identity 字节不变。外部 receipt：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v33_buffer_ag_idx_pair_diag.time_to_root_cause_revalidation.json`，
  SHA256=`939e2ea83257bfd78ec8d1324f47c760cf36498ddb52d59773ab022d3821d3bb`。
- task record：
  `.agents/task_records/20260804_gap_node0071_v32_return_and_v33_buffer_ag_idx_pair.md`，
  SHA256=`675d3edd2ccec8d38e0597b059fa45e2160ea9d3234d602c9056d75c1878808b`。
- current-rule revalidation task record：
  `.agents/task_records/20260804_gap_node0071_v33_time_to_root_cause_rule_revalidation.md`，
  SHA256=`167f44d8c5b9546be4c7593734f1ba6845491d9bb6ba828416f7ddd1dea30d64`。

### 2.2 serialized Conv node0004 v33 return → v35

- 正式 return：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v33_lc18_pe7_diag_return.zip`，
  bytes=`104383`，SHA256=
  `82c1cc545d1df6a9e0359be6902c064af30d7e9631d50fcc4182177eb904105e`；
  source v33 SHA256=
  `5094fc3e01a04c1931b81c4db3a67bf2f6b82f424124d0311866d03004997c90`。
- CRC/root/exact-set/allowlist/per-file/source binding/preflight/observer 均闭合；
  compile/run=`0/0`、signal=`NONE`，但 DUT natural terminal=false；
  formal D=`0/320`，E3/E4/E5=false。
- 动态守恒：PE7 input2/write/read/MSE4 input1=`7/7/7/7`，证明第7项
  physical LC18 value6 已被 PE7 接受并完整送到 MSE4；LC18 global release=`6`。
- `LAST_PROVEN_GOOD=PHYSICAL_LC18_VALUE6_ACCEPTED_BY_PE7_AND_CONSERVED_THROUGH_PE7_WRITE_READ_TO_MSE4_SEVENTH_INPUT1_ACCEPT`。
- `FIRST_DIVERGENCE=PHYSICAL_LC18_VALUE6_GLOBAL_FANOUT_RELEASE_BLOCKED_ONLY_BY_PHYSICAL_ROW_LC4_BACKPRESSURE_BIT10`。
  最终 `lc18_bp=0x1fffffbff`，唯一缺 bit10；活动 IGA_Interconnect 静态映射精确绑定
  bit10=`ROW_LC4`。
- 已排除 PE7/MSE/queue/WR_AG/descriptor 丢失。新 blocker：
  `B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED`。
  ROW_LC4 内仍有四类候选：selected input/same-gotten、ROW/COL counter/fanout、
  WRITE_STREAM0 row input/Buffer5 reuse、final-flush 循环依赖；当前不宣称 RTL bug。
- machine report：
  `outputs/conv_node0004_v33_return_analysis/report.json`，bytes=`19593`，
  SHA256=`6051e4185fcca45e2a56f356e1fc165c877e650151df0e71594a57670afde4ca`。
- v33 source 已消费、不得重跑。v34 因 package 内 generation-read receipt 陈旧被
  final audit 隔离，未发布。

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v35_rowlc4_bufag_diag.zip
bytes   5,845,508
SHA256  af9f94d12275e9b5e9b138101354811bf5fdc4c7a5f4b3ef32cf7d94dd5f90cd
sidecar SHA256 ab02ff10ee5234337391c731a12504642826c81fbc7e47a019cc48fe8d069023
class   DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status  PACKAGE_READY_NOT_RUN
command bash r5_n4_hw_v35_rowlc4_bufag_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
return  r5_n4_hw_v35_rowlc4_bufag_diag_return.zip
```

- v35 在同一包覆盖 ROW_LC4、COL_LC4、Buffer_AG、RD_Buffer_AG 与 prepared-data
  五类候选×观察矩阵；无合法 checkpoint，保留完整冻结 c0 causal prefix，并将
  runtime observer 从 9 项裁减为 5 项。workload/config/numeric/functional RTL 均不改。
- 绑定本地 RTL `df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727`；服务器实际 RTL identity
  仍须由 return 绑定。
- 双构建一致；focused-HDL、runner EXIT/TERM、canonical/feature 负控均闭合；
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0，final audit SHA256=
  `cb44f943b7df2b0090141d945c407dab03b01fccfdf85aa10c358b22ae30e015`。
- task record SHA256=
  `a5bdbdfed9f1fa4764132fe997a38a6d0f983c516e3588ebb0018890c88ca17c`。

### 2.3 QLinearAdd node0007 v28 return → v29

- v28 正式 return：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_split_c_ingress_v28_return.zip`，
  bytes=`170607`，SHA256=
  `e42e6159912e111e4b04293f7682de2078fd3459a921203f5a44ad7b1aebd417`；
  内部 CRC/root/path/RETURN_MANIFEST exact-set/allowlist/per-file/source v28 binding/
  preflight 均通过。
- compile=`0`、simulation=`125`、signal=`INT`、非自然终态；
  formal readback present/missing=`0/28`，mismatch 不可评价，E3/E4/E5=false。
- 实际只有 2 个 `EXEC_START`、1 个 `COMP_FINISH`：op_a_dequant 用
  `543213` cycles 完成，op_b_dequant 启动后被人工中断；relocation 和目标
  op_fp32_add 均未启动。
- `LAST_PROVEN_GOOD=OP_A_DEQUANT_COMP_FINISH`；
  `FIRST_DIVERGENCE=OP_B_DEQUANT_MANUAL_INTERRUPT_BEFORE_COMP_FINISH`。
  本次 return 没有新的 FP32-add 功能证据。
- returned canonical 的“FP32 first output”不可消费：唯一 ingress snapshot 的
  `stage_seq=1`，计数来自 earlier dequant。package-local observer 的
  `qadd_ingress_exec_start_d` 只在 `return_obs_active` 时更新，跨 inactive inter-stage
  gap 保持高电平，导致后续 stage edge 不递增/复位 `stage_seq`。
- package-local blocker
  `B_QADD_SPLIT_C_V28_INGRESS_STAGE_SCOPE_COUNTER_RESET` 已在 v29 关闭；functional
  `B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN` 与 full-chain 28D blocker 保持开放。
  v28 source 已消费、不得重跑；D 继续冻结。
- machine report：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-ingress-v28-return-analysis/report.json`，
  bytes=`4790`，SHA256=
  `9afef5ac944950789e5da4b9b4534de3e924697b77069b239eb3b4de39227c77`。
- A dual-dequant 结构门与 B relocation 自然完成证据继续冻结复用，但均未绑定
  independent numeric golden；不得把局部结构证据扩大到 C/D 或 E4/E5。

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_c_pairmatrix_v29.zip
bytes   26,171,333
SHA256  c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3
sidecar SHA256 6b0cedd99f7ef2017f5248a3a07bdfcdab46b734c5813e2b79753e5fff461720
class   DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status  PACKAGE_READY_NOT_RUN
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02
return  r5_qadd_n7_split_c_pairmatrix_v29_return.zip
```

- v29 的 `EXEC_START` history 在 observer active 外持续更新，每次 stage 重置，并只在
  exact `stage_seq=4` 计数；canonical 对其它 stage fail closed。
- 单一 candidate×observation matrix 覆盖 MSE0/MSE1 index
  valid/ready/handshake/match/empty/full/queue-write/AG、request/rdata、
  Buffer0/2 accepted delivery、GA dual capture/pair/accept/output。
- 无合法逐字节 A/B/relocation checkpoint，故保留最短累计 prefix；无 host replay、
  timeout 延长、高频日志或 functional RTL 修改。
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0，audit SHA256=
  `ab4e48f1ffeb117414063663380c1e966dc53aef24bbfaaef70d9df9db1cbde2`；
  HDL scope SHA256=
  `b03a957385183804530111f34e776f43919327017c3a83fccdc3a484860d4532`；
  deterministic double build 与全部 observer/parser/stage/HDL negatives 闭合。
- release report/task record SHA256=
  `0251d0087d6ba6b78f5e5ab8b1238ce183000ab7b5c32dca016b1375a5cdd114` /
  `102aea4fb889bcf5062e51db57f92f102d2ae06b83883e6d70318b412000e9c0`。

### 2.4 Conv native four-lane df23e4d performance candidate

- current RTL arithmetic gate 与 all-53 W3 reachability 已闭合：53/53 实例共
  `15,426,912,256` occurrence；旧 `NEG5_PLUS5` 边界共 528 次/19 实例，全部由
  current leaf directed pass 覆盖。因此
  `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE` 已关闭。
- 冻结 node0004 native config-bound E2=`LOCAL_E2_PASS`：51 mappings、27 execplans、
  54 SCA/SCA_D consumer closure；native、serialized 与 direct W3 accumulator
  完全一致，UINT8 requant tail exact。该结论不是服务器 E3/E4/E5。
- fresh materialization 的静态/配置预算：occurrence
  `205,520,896→51,380,224`（4× reduction），最大 useful-lane utilization
  `25%→100%`；weights `262144→65536B`（4×），activation single-B
  `51,380,224→12,845,056B`（4×），但 native B+B-prime 合计为 25,690,112B，
  物理 activation 总量仅 2× reduction。以上不是服务器性能成绩。

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n4_df23e4d_p4.zip
bytes   45,989,623
SHA256  c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e
sidecar SHA256 22163623e58c919f440dbc941c34213864bc44f1aa72d180b3c5025be053526e
class   PERFORMANCE_DIAGNOSTIC_CANDIDATE
status  PACKAGE_READY_NOT_RUN
command bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
return  r5_n4_df23e4d_p4_return.zip
```

- p4 是唯一可运行身份；冻结 v1 仅保留为 source/E2 历史身份，p2/p3 为失败且未发布
  候选。p4 不改变 typed request、W3、qparams、numeric config、mapping、bitstream、
  execplan、SCA/SCA_D、golden、observer 或 production RTL leaves。
- final ZIP 含 834 files、27 runs、320 formal-D consumers；双构建一致，
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、functional RTL entries=0。
  final audit SHA256=
  `6a4aa8ca2719b16e62ff5c2b6e5a3684c0b3014d6d55fed60df6243d6c1f0a99`；
  build receipt SHA256=
  `5f4c559438c66dc700053410cbcb6ecf0cae25d3dc8fd1a2d2305fa91ae0acaa`。
- fresh extract exact-set PASS；此前缺失的三个 runtime member 均直接存在于 p4 ZIP
  与 manifest，删除任一 witness 会在 compile 前 fail closed，且不会遗留 candidate
  namespace。
- current path budget：projected absolute=`229/240`、inner suffix=`116/128`、
  inner depth=`8/8`、ZIP member max=`133`；outer identity 未在内层重复。运行时仍须从
  fresh empty extraction parent 的唯一 archive root 启动。
- 服务器开放门：27/27 DUT natural terminal、320/320 formal D mismatch=0，以及
  actual compiled production RTL leaves/compile receipts identity。三门通过前不得宣称
  performance、E3/E4/E5 或 production。
- task record：
  `.agents/task_records/20260804_conv_native_four_lane_df23e4d_p4_delivery_successor_ready.md`，
  SHA256=`50eca0c6a1c3c09ddc6a1a5306628085845a06f6b9848873f58a21c59c0d46ad`。

## 3. 当前 active RTL 与硬件能力门

### 3.1 Trassic source identity

- 权威私有仓库：`xlsjdjdk/Trassic2.0_RTL`，branch=`master`。
- current commit=`df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727`；
  parent=`d0aa87f682880a260fb792aaac88f70a23aba414`。
- GitHub commit 相对 parent 只改一个文件（`+2/-6`）。同步前 active member 精确匹配
  已认证 d0aa87f 源；同步后 active member、GitHub raw bytes 与冻结 selected source
  copy 逐字节相同：

```text
SA_PE_Float_CSA.v
72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3

SA_PE_Float_Control.v
00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb
```

- sync report：
  `artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json`，
  SHA256=`6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5`。
- task record：
  `.agents/task_records/20260804_trassic_master_df23e4d_active_rtl_sync_and_revalidation.md`，
  SHA256=`15192baf2abc9c08e87b0ea129de5ba1c0cb6b50964fce9263be638deae43bee`。

### 3.2 df23e4d 功能复验裁决

- 上游改为对 `o_IntResult[31:0]` 做一次完整 32-bit two's-complement 赋值，
  删除旧 lower-31-bit 与独立 sign 重构路径。
- focused current-source Icarus/VVP compile/simulation=`0/0`：
  Conv 真实 node0003 `-5+5` 与 node0075 首例 `-19+19` 均从旧
  `0x80000000` 修正为 `0x00000000`；邻例 `-6+5=-1` 仍正确。
- node0075 owner 已在 df23e4d 下 fresh 完整扫描
  `8,192,000/8,192,000` recurrence：negative psum=`4,343,952`、
  negative→exact-zero=`272`，全部 272 个真实4-lane occurrence送入 current-source
  SA_ALU 后 mismatch=`0`；另有 110,364 个 adjacent/acceptance/small-domain/
  single-product/full-domain/four-lane-corner RTL 向量 mismatch=`0`，
  marker=`RTL_REPAIR_FULL_REACHABLE_PASS`。因此
  `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE` 正式关闭。
- node0075 machine report：
  `outputs/node0075_negative_psum_df23e4d_revalidation/current_rtl_and_recurrence.json`，
  SHA256=`4d4aad044e4f241bc9af3cf244cec0069335d7da17760645c8a2f57926105c88`。
- Conv native 已完成 current-identity arithmetic、all-53 W3 reachability、
  frozen-node0004 config-bound E2、fresh materialization 与 final-ZIP package；
  当前只等待服务器 natural terminal、formal D 与 production RTL identity。
  node0075 已完成
  8 accum + 8 scale + 8 exact-round 共 24 个算子的 handler/materializer，
  生成 505 条 128-bit execplan，并通过 261-member 双重 fresh rebuild 的
  config-bound compositional E2；accumulator、UINT8 D 与 padding mismatch 均为 0。
- node0075 已实际物化最小 8-pass A reload：每 pass `1024×32B=32768B`，
  总计 8192 个 read occurrence、262144B configured/accepted traffic，unique
  storage 32768B；这不是反事实预算。
- node0075-only execplan 从 pass00 consumer 开始，既没有 node0071 producer
  occurrence，也没有 producer-final→first-read visibility barrier；SCA 又依法没有
  A preload，因此 fresh server memory 没有合法 writer。SCA 预载 A 属于禁止的内部
  tensor replay，producer base 也不能冒充 runtime writer/consumer acceptance。
- node0075 当前终态为 `WAIT_USER_DECISION`，`PACKAGE_RELEASE=NONE`。最小解阻条件是
  授权一个跨族同一执行流：合法 node0071 true-producer prefix → final write/visibility
  barrier → node0075 pass00；在此之前不生成服务器包，也不宣称 E3/E4/E5。
- Conv native owner `019fc783-1146-7901-9e40-64d0ed8e052d` 已交付独立性能候选；
  node0075 owner
  `019fc775-8de0-7f10-bc4a-026a4673776f` 已在上述跨族权限叶停止。两支均不得修改
  functional RTL/plan/public rules，完成分析或包后必须主动通知主线。
- `RULE_DELTA_PROPOSAL=NONE`；current-identity arithmetic fail-fast 与 owner
  completion notification 规则在本次继续充分。

## 4. 最新短期计划

1. 当前可立即运行身份是 GAP v33、serialized Conv v35、QAdd split-C pairmatrix v29，
   以及 Conv native-four-lane df23e4d p4；p4 必须在空 parent fresh extract 后进入唯一
   archive root 运行，v1/p2/p3 禁止重跑；
   QAdd D 继续冻结。
   当前无 `SERVER_RUNNING` lease；已消费 return 的 GAP v32、
   Conv v33、QAdd C-ingress v28 以及所有更早身份禁止重跑。
2. GAP v33 一次覆盖 MSE0 Buffer_AG queue 两输入、tag/index、match-mask、
   enqueue/dequeue 与直接 consumer；运行后应唯一化 lane1 是未进入 input、未匹配还是
   enqueue 被拒。不复活已关闭的 COL_AG/MRM-strobe、Buffer→prepared 或 GA→MSE4 blocker。
3. serialized Conv v35 一次覆盖 ROW_LC4/COL_LC4/Buffer_AG/RD_Buffer_AG/
   prepared-data 五类候选，定位 LC18 fanout 在 ROW_LC4 bit10 下的最终 flush 阻塞；
   不改 end/keep/config，不复活旧 occupancy 误判，其后仍需 DUT natural terminal
   与 320/320 formal D。
4. QAdd v29 已修复 stage-scope observer reset，并在 exact stage4 一次覆盖
   MSE0/MSE1→Buffer0/2→GA 全候选判别矩阵；因无合法内部 checkpoint 保留最短累计
   prefix。D 继续冻结，A/B/C 的局部/前缀证据不能替代端到端六阶段+28D 联合门。
5. MaxPool 保持用户特例 `DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE`，不重跑、不恢复
   通用诊断，也不把复用 authority 冒充本轮 E4/E5。
6. node0075 的 arithmetic、24-op materializer、最小 8-pass A reload 与
   compositional E2 已闭合；当前等待用户决定是否授权独立跨族 integration task，
   把 node0071 true-producer prefix、producer-final visibility barrier 与
   node0075 pass00 放入同一 fresh-memory exec stream。未授权前不得用 A preload
   或 producer base 绕过，也不得生成服务器包。Conv native-four-lane 的本地 W3/E2
   已闭合；当前只运行短路径且 exact-set 完整的 p4，随后验证服务器三门。
7. serialized Conv 继续作为 correctness-first 非优化基线：约 4× occurrence、
   useful-lane utilization 最多 25%。先运行 ROW_LC4 五候选高信息增益 v35，再闭合
   320 D；native-four-lane p4 独立验证 27/27 natural terminal、320/320 D 与
   production RTL identity，不能用其本地 E2 取代 serialized correctness 闭环。
8. 每个 owner 完成 RETURN→successor 或本地 package 后必须主动通知当前主线并提交
   `RULE_CONFIRMATION` 或非同义 `RULE_DELTA_PROPOSAL`。分支不得修改公共规则/plan。
9. 服务器运行期间不要求主线持续盯守。同一物理服务器根目录禁止并发；只执行包内唯一
   `PREPARE_AND_RUN.sh`，只接受 runner 正式 return。

## 5. 当前开放 blocker

- `B_GAP_NODE0071_MSE0_BUFFER_AG_INDEX_PAIRING_BEFORE_BYTE_LANE1_ENQUEUE_PENDING_INPUT_OR_MATCH_MASK_LEAF`
- `B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED`
- `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`
- `B_CONV_NODE0004_FORMAL_D_320`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY`
- `B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED`
- `B_QUANT_TAIL_SIGNED_INT32_INGRESS`
- `B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING`
- `B_QADD_SPLIT_A_B_STAGE_LOCAL_NUMERIC_GOLDEN_UNBOUND`
- `B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN`
- `B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN`
- `B_QUANT_NODE0074_EXACT_DIVISION`
- `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- `B_GA_INT8_MAX_NUMERIC` / `B_GA_INT8_MAX_FLOW` / `B_MAXPOOL_SERVER_E4_E5`
- shared allocator/execplan/coverage/lifetime
- 最终 133-stage integration assembly 与逐层三方比较

## 6. 当前关键规则收据

| 文件 | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/rules/生成前必读索引.md` | `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2` |
| `.agents/rules/服务器测试包生成规则.md` | `14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `.agents/rules/QLinearAdd算子配置规则.md` | `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f` |
| `.agents/rules/INT8_SA点积专项规则.md` | `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce` |
| `.agents/rules/GAP_int32_mac_bypass_rules.md` | `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b` |
| `.agents/rules/GAP_probe_v7_validator_rules.md` | `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |

以上 SHA 只是 current receipt。任何新生成、封包或 return 裁决前，仍须完整读取磁盘
current 文件并重算身份。
