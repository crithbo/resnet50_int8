# ResNet50 INT8 当前状态与短期计划

最后更新：2026-08-04

## 0. 文件职责

- 本文件只保留最新状态和最新短期计划；状态变化直接覆盖，不在末尾追加版本过程。
- 旧状态进入 `.agents/history.md` 或 `.agents/history/`；精确证据进入
  `.agents/task_records/` 和机器报告。
- 当前唯一主线会话：`019fbec2-fe93-7e03-9314-cff6f222f33d`。
- 算子 owner 不修改 plan、公共规则或功能 RTL；完成 return 分析或服务器包后必须主动
  向本主线回传。

## 1. 全网最新总账

- ONNX 节点：`78/78`；typed hardware request：`133/133`。
- 正式 E4/E5 闭环：`1/78`，仅 DequantizeLinear node0077；其余不得提前宣称通过。
- 当前没有 `SERVER_RUNNING` lease。

| 算子/范围 | 当前状态 | 最新裁决 |
|---|---|---|
| GAP node0071 | `PACKAGE_READY_NOT_RUN / V33_BUFFER_AG_IDX_PAIR_DIAG` | v32 将停点收窄到 MSE0 Buffer_AG index pairing/enqueue 前 |
| QLinearAdd node0007 | `PACKAGE_READY_NOT_RUN / SPLIT_C_PAIRMATRIX_V29` | A/B 结构运行通过但数值未独立绑定；C 仍未到 FP32-add 目标 |
| MaxPool node0002 | `DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE` | 按用户/学长特例暂停通用 successor；不得冒充 E4/E5 |
| Conv node0004 serialized | `PACKAGE_READY_NOT_RUN / V35_ROWLC4_BUFAG_DIAG` | 当前停在 LC18 fanout → ROW_LC4 bit10 下游 final-flush 路径 |
| Conv native four-lane | `PACKAGE_READY_NOT_RUN / DF23E4D_P4` | df23e4d 算术、all-53 W3、本地 E2 和短路径包已闭合，待服务器三门 |
| QuantizeLinear node0074 | `APPROVED_EQUIVALENT / WAIT_NODE0075_INTEGRATION` | node0072→View→node0074 可成对消除；通用 exact divider 仍开放 |
| DequantizeLinear | node0077 `E4/E5_PASS_FROZEN` | node0072 走同 qdomain UINT8 alias，不单独重算 |
| View node0073 | `APPROVED_EQUIVALENT_UINT8_ALIAS` | `[16,2048,1,1]→[16,2048]` metadata-only overlay 已闭合 |
| QLinearMatMul node0075 | `WAIT_USER_DECISION / PRODUCER_BARRIER_INTEGRATION` | 算术、24-op materializer、8-pass A reload、compositional E2 已闭合；缺同流 producer/barrier |

## 2. 当前唯一可运行包

### 2.1 GAP node0071

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip
bytes   1,824,172
SHA256  5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
return  r5_n71_gap_v33_buffer_ag_idx_pair_diag_return.zip
```

- v32：compile/sim/runner=`0/125/125`，INT，formal D=`0/48`，E3/E4/E5=false。
- LPG：COL-LC0 接受值 1/3，8 个到达 MSE 写口的事件均由 MRM 接受并保持 strobe。
- FD：lane1 只在 MSE0 Buffer_AG 活动前出现；后续 MRM 无 lane1 写。
- v33 同包覆盖 COL-LC0、MSE0 queue 两输入、match/enqueue/dequeue 和直接 consumer；
  最多 256 个 qualified 事件，`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`。

### 2.2 serialized Conv node0004

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v35_rowlc4_bufag_diag.zip
bytes   5,845,508
SHA256  af9f94d12275e9b5e9b138101354811bf5fdc4c7a5f4b3ef32cf7d94dd5f90cd
command bash r5_n4_hw_v35_rowlc4_bufag_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
return  r5_n4_hw_v35_rowlc4_bufag_diag_return.zip
```

- v33：compile/run=`0/0`，DUT natural terminal=false，formal D=`0/320`。
- LPG：physical LC18 value6 经 PE7 write/read 到 MSE4 第 7 个 input1 accept 全守恒。
- FD：LC18 global release 仅被 ROW_LC4 backpressure bit10 阻断。
- v35 一次覆盖 ROW_LC4/COL_LC4/Buffer_AG/RD_Buffer_AG/prepared-data 五类候选；
  旧 outbuffer occupancy 结论继续为 `INVALIDATED_NOT_RTL_BUG`。

### 2.3 QLinearAdd node0007

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_c_pairmatrix_v29.zip
bytes   26,171,333
SHA256  c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3
command bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02
return  r5_qadd_n7_split_c_pairmatrix_v29_return.zip
```

- split-B relocation 自然完成且有 28/28 结构 readback，但未绑定独立数值 golden。
- split-A 两个 dequant 自然完成且有 28/28 结构 readback，同样不升级为数值通过。
- split-C v28 只完成 A dequant，B dequant 被人工中断，目标 relocation/FP32-add 未到达；
  返回的 FP32 snapshot 因跨 stage 累计被拒绝。
- v29 修正 stage scope，只在 exact stage4 统计 MSE0/MSE1→Buffer0/2→GA 配对边界。
  无合法内部 checkpoint，故保留最短合法累计 prefix；D/full-chain 继续冻结。

### 2.4 Conv native four-lane

```text
ZIP     artifacts/operator_config_validation/r5-server-test-packages/r5_n4_df23e4d_p4.zip
bytes   45,989,623
SHA256  c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e
command bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
return  r5_n4_df23e4d_p4_return.zip
```

- current RTL=`df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727`；
  `SA_PE_Float_CSA.v` SHA256=`72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3`。
- 53/53、15,426,912,256 occurrences 和 528 个 reachable exact-cancellation 已复验；
  frozen node0004 native config-bound E2=`LOCAL_E2_PASS`。
- p4 必须从空 extraction parent 的唯一 archive root 运行；v1/p2/p3 不再运行。
- 仍需 27/27 DUT natural terminal、320/320 formal D mismatch=0、production RTL identity。

## 3. 当前硬件与跨族边界

- df23e4d 已关闭 Conv performance 与 node0075 共用的 negative-psum exact-zero RTL 缺陷；
  本地复验不能代替服务器 production identity。
- node0075 已物化 8 accum + 8 scale + 8 exact round，A reload 为实际最小 8 pass，
  但 node0075-only fresh-memory stream 没有 node0071 true-producer writer 和
  producer-final→first-read visibility barrier。
- 未经用户授权，不用 A preload 或 producer base 冒充真实 producer/consumer acceptance；
  不跨族擅自修改 GAP workload。

## 4. 最新短期计划

1. 按服务器资源依次运行 GAP v33、serialized Conv v35、QAdd v29 和 native Conv p4；
   每个根只运行唯一入口，运行期间无需主线持续盯守。
2. return 到达后交由原 owner 连续分析并生成修正包或高信息增益 successor；owner 完成后
   主动通知本主线并提交规则确证/增量。
3. GAP v33 区分 lane1 未进入、未匹配或 enqueue 受阻。
4. serialized Conv v35 区分 ROW_LC4 五类 final-flush 候选，继续追 natural terminal/320D。
5. QAdd v29 必须先真正到达 FP32-add stage，再裁决 paired ingress；full-chain D 继续冻结。
6. native Conv p4 只在 27/27、320/320 和 production identity 全部通过后升级性能结论。
7. node0075 等待用户授权同一执行流的 node0071 producer prefix 与 visibility barrier；
   未授权前不生成服务器包。

## 5. 当前开放 blocker

- `B_GAP_NODE0071_MSE0_BUFFER_AG_INDEX_PAIRING_BEFORE_BYTE_LANE1_ENQUEUE_PENDING_INPUT_OR_MATCH_MASK_LEAF`
- `B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED`
- `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL` / `B_CONV_NODE0004_FORMAL_D_320`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320`
- `B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY`
- `B_QADD_SPLIT_A_B_STAGE_LOCAL_NUMERIC_GOLDEN_UNBOUND`
- `B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN`
- `B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN`
- `B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED`
- `B_QUANT_NODE0074_EXACT_DIVISION` / `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- `B_GA_INT8_MAX_NUMERIC` / `B_GA_INT8_MAX_FLOW` / `B_MAXPOOL_SERVER_E4_E5`
- shared allocator/execplan/coverage/lifetime 与最终 133-stage integration assembly

## 6. 当前规则入口

- `.agents/rules/生成前必读索引.md`
- `.agents/rules/算子配置规则.md`
- `.agents/rules/NDP硬件字段语义.md`
- `.agents/rules/服务器测试包生成规则.md`
- 当前目标算子专项规则
