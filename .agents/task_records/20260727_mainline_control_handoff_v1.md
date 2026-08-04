# ResNet50 INT8 主线控制任务交接 v1

日期：2026-07-27  
来源主线：`019f8edd-10fc-7dc0-a405-937e4a00ebb5`

## 1. 接管职责

新主线是项目唯一控制面，负责：

1. 唯一维护 `.agents/plan.md`、`.agents/rules/**`、全局 blocker、证据等级和整网总账；
2. 决定下一步测试哪个真实 ResNet50 算子、为什么它最有价值、通过/失败分别改变哪些规则；
3. 验收五个 AI 算子族任务和一个人工 JSON 任务的结构化回传；
4. 管理 `NDP_copy01/02/03` 三个服务器根目录的独占 lease；
5. 只在证据充分时迁移 `RULE_DELTA_PROPOSAL`，不重复构建普通算子包；
6. 维持最终目标：

```text
同一冻结 ResNet50 输入
  ONNX/W3 golden
      ↕
  config-bound simulator
      ↕
  stock-RTL hardware
```

主线不计入六条执行线，不负责普通 package 的重复构建或回传的重复全量分析。

## 2. 当前项目总账

| 层级 | 状态 | 证据边界 |
|---|---:|---|
| ONNX 独立软件公式 | 78/78 | 不证明硬件 JSON |
| typed hardware request | 133/133 | 不证明最终物化 |
| hardware stage family | 10 | 同 family 不可自动外推 |
| 精确物化 JSON | 2/133 | Dequant 正式；Requant candidate |
| 正式 ResNet target config | 1/133 | Dequant node0077/v6 |
| 正式 stock-RTL E4 | 1 | Dequant node0077/v6 |
| 正式 stock-RTL E5 | 1 | Dequant node0077/v6 重复通过 |
| 正式 ResNet 三方节点 | 0/78 | Dequant 仍待 config-bound simulator 总账腿 |

DeepSeek 已验证 JSON 和对应 RTL 运行只作为硬件字段/原语 oracle，用来完成
ResNet50 算子，不是最终交付对象。DeepSeek 六类本地验证已达到 16/16
stage/config-length E2；ONNX Community 模型只能称 `SEMANTIC_MODEL_MATCH`，
不能称 `ORIGINAL_SOURCE_IDENTITY`。896/1792 等裁切实例必须显式经过 crop contract。

## 3. 已闭合和仍开放的算子族

### 3.1 DequantizeLinear

正式实例：`node0077/v6`，`uint8[16,1000] → float32[16,1000]`。

已闭合：

- 28 个 stage，8 slice×750 有效元素按物理布局补齐到 752；
- 最终 JSON、mapping、bitstream、execplan/SCA、occurrence 和 HIGH4 inverse；
- E4 与全新身份 E5 均 28/28 slice 自然完成；
- 两次均正式回读 `28×188=5,264` 行，逐 bit 对 physical golden；
- inverse 无损还原 `float32[16,1000]`；
- temporal raw count、return exact-set、stock RTL identity 均通过；
- `B_DEQUANT_SERVER_E5` 已关闭，`candidate_release=true`。

唯一剩余项：必须由真实 `NDPFuncModel` 或等价配置绑定执行器明确消费最终
v6 JSON/bitstream/layout，产出 physical D，再与 golden 和 E4/E5 hardware
分别比较。不得用软件公式摘要代替。

关键入口：

- `configs/native_ndp_sim/resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json`
- `.agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md`
- `.agents/task_records/20260727_dequant_node0077_full_v6_e5_pass.md`

当前禁止继续生成 Dequant 服务器包。

### 3.2 RequantizeUint8 / AverageRequant

已完成：

- 54/54 stage 按 W3 数值公式分类；
- 33 项 `y_zero_point=0` 与当前 guard 数值形式兼容，21 项被 guard 反证；
- node0001 完成唯一完整物理 E2 和 config-bound simulator：
  48 JSON / 24 occurrence / SCA+execplan / 28 physical D region 对 golden bit-exact；
- 最小 guard→round 两 stage 能自然完成，但当时输出全零；
- 后续 guard-only 探针已逐事务证明 64/64 BST data 与 selected input 一致，
  coeff address `0x00/0x41` 正确；
- 原生 `decode_silu_fp16N_fp32N` control 已证明共同 stock-RTL
  coeff→ALU→postprocess→normal outbuffer→MSE4 payload 32/32 逐事务正确，
  但其正式 D occurrence/address coverage 只保留最后值，不能冒充 Requant 通过。

当前最窄未闭合区间：

```text
BST data / coeff address 已证明
  → coeff SRAM output / ALU / postprocess / normal outbuffer 未闭合
  → MSE4 与 formal D 为零
```

唯一待运行诊断候选：

- `artifacts/operator_config_validation/r5-server-test-packages/`
  `rq_node0001_guardonly_sfu_eventedge_stock_v1.zip`
- bytes：`78068`
- SHA256：`31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53`
- 状态：`PACKAGE_READY_NOT_RUN`
- 不计 E4/E5。

当前只允许该 event-qualified 窄探针；不得启用 round-only、alias/lifetime、
完整 E4 或原样重跑旧 full v2。完整 v2 的 48 stage/finish 全部完成，但 stock TB
用物理 slice0 Start 与 slice1 Finish 固定配对，mask 轮换导致 completion
统计错配，最终 timeout；该失败不是数值/RTL 根因。

四个 `y_zero_point=0` shape holdout 仍需物理化 E2。活动计划原列
`hwop-0004-01/0017-01/0039-01/0067-01`；新 Requant 任务首轮报告改选
`0004-01/0017-01/0034-01/0059-01`。这是一个待主线核对的范围冲突，
在确认 typed request/shape 分类前不得静默改 plan。

保持 blocker：

- `B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2`
- `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`
- `B_REQUANT_SERVER_E4_E5`

### 3.3 QuantizeLinear

新任务已选择真实代表 `node-0074 / hwop-0074-00`：

- `float32[16,2048] → uint8[16,2048]`
- scale `0.02335735410451889` (`0x3cbf57ec`)
- zero-point `0`
- 上游 Flatten，下游 QLinearMatMul。

当前 fail-closed：

- 没有 QuantizeLinear 专项规则；
- typed request 明确 `candidate_files_may_satisfy_request=false`；
- 可信 `quant_from_buffer` oracle 是 `int32→uint8`，不能替代目标 `fp32→uint8`；
- control-register handler 是 placeholder，mapper registry 未注册该算子。

因此尚未生成 JSON/bitstream/E2/package。主线应审阅：

- `.agents/task_records/20260727_quantize_node0074_inventory_blocked.md`
- `contracts/operator_config/quantize_node0074_inventory_v1.json`

不得因 oracle 名称相似而放宽输入域。

### 3.4 QLinearAdd

新任务已选择真实代表 `node-0007 / hwop-0007-00`，stage1 首个 residual merge：

- A/B/Y 均为 `uint8[16,256,56,56]`；
- 两路输入 qparam 和输出 qparam 不同；
- 原生 `add_dequant` 只实现 `uint8+uint8→fp32`，不消费
  `y_scale/y_zero_point`，不能替代完整 QLinearAdd；
- 专项规则缺失；
- 三条 tensor edge 的 physical allocation/address/alias/copy/lifetime 未绑定。

当前未生成 JSON/E2/package。新增 blocker 建议：

- `B_QADD_SPECIALTY_AND_MATERIALIZATION_CONTRACT`

保持：

- `B_ADD_DUAL_QDOMAIN`
- `B_ADD_UINT8_REQUANT`
- `B_EXECPLAN_TYPED_TRANSPORT`
- `B_ADD_REQUANT_E5`
- `B_SERVER_E4_E5`

待主线审阅：

- `.agents/task_records/20260727_qlinearadd_node0007_inventory_and_blocker.md`
- `.agents/task_records/20260727_qlinearadd_node0007_inventory.machine.json`

### 3.5 Conv / SA / MatMul

当前目标先本地闭合：

- SA INT8 CSA 方程与普通点积的差异；
- input/weight tiling；
- bias/psum 初值与累积；
- padding/tail；
- SA→Requant 交接；
- buffer/address/lifetime 和 MSE occurrence。

闭合后才选最小真实 1×1/non-symmetric Conv 代表并物化 E2。当前 Conv 任务仍在运行；
不要由主线重复扫描或提前生成包。工作树中存在大量历史 Conv 改动，均视为用户/历史资产，
禁止 reset/checkout/覆盖。

### 3.6 GAP / MaxPool / View

- GAP `int32_mac` pure-config 和 `int32_sum/repair` 服务器路线冻结；
- GAP v7 已证明 GA outbuffer count 无符号下溢、invalid-slot stale C 是 RTL_CONTROL，
  同次 D-index carrier 地址覆盖失败是独立 CONFIG_SEMANTICS；
- 功能 RTL repair 未获授权；
- MaxPool `int8_max` 路径被当前 RTL 反证；
- View 逻辑 bytewise alias 已知，但 physical allocation/offset/lifetime 未闭合。

没有用户新授权不得恢复这些服务器路线。

## 4. 通用语义合同与重要反例

本地材料、可信原生 JSON 和 RTL 方程已大幅关闭 LC_PE、MSE、padding/tail、
buffer、SA、GA、N2N 和多 stage 生命周期；但“通用字段已理解”不等于每个算子
实例已物化或通过动态门。

必须保留的裁决原则：

1. 最终 materialized JSON 必须反解回 occurrence/bank/address/lifetime 合同；
2. transaction bytes、bank columns、buffer demand/supply、tag/last、跨 stage
   生命周期不能只检查派生摘要；
3. 共享 LC 分支必须证明 backpressure 无环，否则优先独立 branch roots；
4. GA occupancy 每周期满足 `0<=count<=DEPTH`；
5. invalid outbuffer slot 不得影响 ALU tag/input C；
6. 新 block 在新 partial 有效前 C 必须为零，`transout_initial` 不能单独授权 feedback；
7. D-index 发布必须逐片逐行完整覆盖 golden，request 总数正确不够；
8. local request/wdata 相差 1 可能是同周期采样盲点，丢写必须由 same-clock observer
   或正式回读支持；
9. CONFIG 与 RTL 缺陷正交，修复一项不能解除另一 blocker；
10. 全树 hash 不同不能单独否决服务器回传；需结合 pre/post/post-run 稳定性和
    focused RTL 逐文件身份；
11. `last_index` 是循环/tag 层级，不是 LC 编号、连线跳数或 LC_PE 深度；
12. 动态首分歧优先，参考 JSON 字段差异只有在目标合同自证冲突后才可定性。

## 5. 六线架构和任务身份

| 组/服务器根 | 执行线 | Codex task ID | 当前状态 |
|---|---|---|---|
| A / `NDP_copy01` | RequantizeUint8 | `019fa2bf-95cd-7502-82c8-6a48cf12d648` | 本地接手完成；等待 event-edge return |
| A / `NDP_copy01` | QuantizeLinear | `019fa2c0-572b-7f21-ac5a-96e773dde534` | 盘点完成；生成前 blocked |
| B / `NDP_copy02` | QLinearAdd | `019fa2c0-b647-7a91-93bf-d21a173487e3` | 盘点完成；生成前 blocked |
| B / `NDP_copy02` | Conv/SA | `019fa2c1-17df-7122-bcbd-a727aaf173f5` | 正在本地闭合 |
| C / `NDP_copy03` | DequantizeLinear | `019fa2bf-f9a5-7a73-ada3-b2b910721de3` | 正在补 simulator 总账 |
| C / `NDP_copy03` | 人工 JSON | `019fa241-0250-7fa3-b2de-1c8951df5aa5` | 边界已切换；当前候选冻结 |

当前六线均没有 `SERVER_RUNNING` lease。

同组最多一个包处于 `SERVER_RUNNING`。前一包必须 restore/finalizer 并释放根目录后，
另一线才能接管。分析不占 lease。服务器物理并行上限为 3；资源未验证或争用时降为 2。

算子族任务不得改 plan/规则/功能 RTL/其他族资产，只提交：

- `RETURN_ANALYSIS`
- `RULE_DELTA_PROPOSAL`
- `BLOCKER_DELTA`
- 必要时唯一 `PACKAGE_RELEASE`

主线用 `wait_threads`/`read_thread` 获取结构化结果，除非证据冲突，不重复解析同一 raw return。

## 6. 人工 JSON 线的当前状态

人工线只消费用户明确提供的人写 JSON。当前 human MAC：

- corrected-v2：
  `artifacts/human_mac_int32_uint8_20260727_v1/mac_int32_uint8.corrected_v2.json`
- bytes：`13942`
- SHA256：`24002ec87abd2e1c5f659003c61aa6176d2d7bd18dbfebeae890e11d80b36eb6`
- `LC2.last_index=1` 已确认正确，不能因可信 quant 参考为 2 而改；
- 动态重跑证明 28/28 slice：MSE0 128 req/128 rdata，MSE4 仅最初 2 req，
  0 write-data；首分歧在 GA/输出 Buffer 向 MSE4 提供首个数据之前；
- 动态支持的候选错误是 `general_array.outport.src_id: 1→0`；
- 尚未得到用户对此第三次修正的明确授权，因此不能生成新 corrected candidate 或后继包。

人工任务过去曾直接修改公共规则；新架构已经禁止。已有修改不回滚，由主线审阅；
今后只接收其 RULE_DELTA_PROPOSAL。

## 7. 强制生成和服务器边界

1. 生成 JSON 前必须按 `.agents/rules/生成前必读索引.md` 完整阅读本轮相关规则、
   专项合同和真实消费者，并保存 SHA 收据；
2. 生成服务器包前必须完整阅读服务器规则和 README；服务器操作最好一条，最多三行；
3. 效率优先：普通编辑只跑受影响测试，服务器交付前做一次完整自检，不在每个步骤
   反复全量重建；
4. 默认禁止修改任何 `rtl/**`；
5. 如规则允许 TB/observer，只能修改 package 实际粘贴/安装目录内的精确文件，
   禁止修改其他目录同名文件；
6. TB/observer 必须只读、非驱动、事务式 backup/install/compile/restore，
   做 pre/post/post-run/post-restore 身份；不得改变 DUT 激励、握手、completion、
   timeout，不得 force/deposit；
7. 包内 `rtl/ entries=0`，ZIP+sidecar，return allowlist-only；
8. 隔离 RUN_DIR 编译相对 include 必须显式传 include 目录，并在 compile 前校验
   目标 bytes/SHA；
9. exact-set 运行时不得产生未列出的 `__pycache__/pyc`；
10. 返回缺 exit receipt/result gate/身份/自然完成或只是手工 RUN_DIR/截断快照，
    分类为 non-authoritative/incomplete，fail-closed；
11. 没有通过相同动态门的 known-good identity 时，使用
    `FIRST_DYNAMIC_FAILURE / NO_DYNAMIC_BASELINE`，不得称 regression；
12. 本地 E2/诊断包均 `candidate_release=false`，不能称硬件动态闭环或正式 target config。

## 8. 新主线的推荐立即动作

1. 完整读取当前 `.agents/agent.md`、`.agents/plan.md` 和生成前必读索引；
2. 核验本交接记录所列 SHA 与磁盘，保留 dirty worktree，禁止 reset/checkout；
3. 用 `wait_threads` 获取 Dequant 与 Conv 当前结果，不重复其工作；
4. 审阅 Quantize、QLinearAdd 的两个 RULE_DELTA_PROPOSAL：
   - 先判断是否需要新增专项规则；
   - 不允许任务在专项规则缺失时直接生成；
5. 核对 Requant holdout 代表范围冲突，确定正确四 shape 后再派发；
6. event-edge 包如由用户上机，给组 A/`NDP_copy01` lease；回传交 Requant 任务分析；
7. Dequant simulator 腿若通过，将正式三方节点从 0/78 更新为 1/78；
8. 规则更新必须由证据驱动，保留规则唯一归属，随后刷新受影响任务读取收据；
9. 当前不要自行生成新的普通算子包，也不要恢复 GAP/MaxPool/RTL repair 路线。

## 9. 当前活动入口 SHA

交接时：

- `.agents/agent.md`：
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- `.agents/plan.md`：
  `0914c90145b81e360754621730ff59cf5f8bb8b0400349314a98c818531aecfe`
- `.agents/rules/生成前必读索引.md`：
  `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7`
- `.agents/rules/算子配置规则.md`：
  `f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023`
- `.agents/rules/NDP硬件字段语义.md`：
  `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
- `.agents/rules/服务器测试包生成规则.md`：
  `f3fe8dd18c9e2009db4a2736c6c1e86841760d8ec023bb7b57562f27f5faff04`
- `.agents/rules/DequantizeLinear算子配置规则.md`：
  `76c66fb19268061caaeafca5ba2899017f6f0c95326a6350c5fb12f18e710dd2`
- `.agents/rules/RequantizeUint8算子配置规则.md`：
  `44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

磁盘内容可能被正在运行的算子任务新增 family-specific 文件；若公共文件 SHA 改变，
必须先确认修改者与授权，不能静默接受或覆盖。

## 10. 工作树安全

工作树长期 dirty，包含用户、历史主线和算子任务的未提交资产。新主线必须：

- 保留所有无关改动；
- 不运行 destructive reset/checkout/clean；
- 编辑前检查目标 ownership；
- 原始 return、冻结 package、server snapshot、history/archive 只读；
- 新实验使用全新 package/install/run/return 命名空间；
- 不从旧失败包、服务器残留或来源不明文件补齐新候选。

