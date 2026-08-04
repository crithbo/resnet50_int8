# GAP int32_mac 纯配置绕行本地闭合记录（2026-07-24）

## 决策边界

- `repair_v9`、历史回传、RTL patch 资产保持冻结只读。
- 未修改 `NDP_copy01/rtl/` 下任何功能 RTL。
- 未生成六层 operator JSON、mapping、bitstream、execplan、SCA。
- 未生成、安装或运行服务器测试包。
- 当前合同固定为 `candidate_release=false`、
  `server_package_allowed=false`、`functional_rtl_modified=false`。

## 使用规则

- `CDA-GAP-INT32MAC-NONTRANSOUT-001`
- `CDA-GAP-INT32MAC-DUAL-INPUT-001`
- `CDA-GAP-INT32MAC-NORMAL-FIFO-001`
- `CDA-GAP-INT32MAC-TREE-001`
- `CDA-GAP-INT32MAC-STAGE-MEMORY-001`
- `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`
- `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`

执行前已完整阅读：

- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/rules/GAP_repair_candidate_rules.md`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`

本轮没有调用原生 `model_execplan` 流程，因而没有生成或重建原生
execplan。

## 已闭合的本地地址/数值语义

### 两条首层 MSE read stream

- A：`READ_STREAM0 -> buffer0 -> GA group0`。
- C：`READ_STREAM3 -> buffer4 -> GA group2`。
- D 写回：`buffer5 -> WRITE_STREAM0`。
- 每个 C8 block 的 64 个物理叶按
  `A=2*j`、`C=2*j+1` 配对，`j=0..31`。
- 首层每条 A/C 请求是 8 bytes；连续四次请求分别写入八个 bank 的
  byte slot 0..3，形成八个 32-bit lane。A/C 的 occurrence、tag、
  `last`、`last_index` 逐项相同。
- 逻辑索引 49..63 由 padding 明确替换为 0。物理树为
  `64->32->16->8->4->2->1`，其非零逻辑前缀严格为
  `49->25->13->7->4->2->1`。
- padding 在 memory return 后生效；最后一个 C8 block 的物理请求会越过
  100352-byte 逻辑输入末端，因此每片输入分配固定为 100480 bytes，
  显式保留 128-byte guard。

### 六层 INT32 scratch

每片相对地址域（尚未绑定 base/address remapping）：

| region | base | end(exclusive) | bytes | physical/logical width |
|---|---:|---:|---:|---:|
| input UINT8 | 0 | 100480 | 100480 | 64/49 |
| S1 INT32 | 102400 | 364544 | 262144 | 32/25 |
| S2 INT32 | 364544 | 495616 | 131072 | 16/13 |
| S3 INT32 | 495616 | 561152 | 65536 | 8/7 |
| S4 INT32 | 561152 | 593920 | 32768 | 4/4 |
| S5 INT32 | 593920 | 610304 | 16384 | 2/2 |
| S6 final D | 610304 | 618496 | 8192 | 1/1 |

S2..S6 的每个 pair 从前一层相邻的两个 32-byte INT32 transaction
读取，分别送 A/C；每层写回区连续、唯一、32-byte 对齐且互不覆盖。
各层每片 A/C/write transaction 数依次为：

- S1：8192 / 8192 / 8192
- S2：4096 / 4096 / 4096
- S3：2048 / 2048 / 2048
- S4：1024 / 1024 / 1024
- S5：512 / 512 / 512
- S6：256 / 256 / 256

S6 的 256 个 32-byte transaction 展开为每片 512 条唯一 128-bit
相对行地址。本轮只证明本地地址覆盖，不把它声称为正式 D readback。

### terminal 与跨 stage 屏障

- 每层、每片有 255 个 C8 local-end tag `(last=1,last_index=1)`。
- 每层、每片恰有一个 terminal tag `(last=1,last_index=0)`。
- A/C terminal tag 始终一致。
- `GA_PE_Outbuffer` 的 pointer/count 仅由 `rst_n` 或 `slice_rst`
  复位，`configure_clear` 不会清空它。因此下一层开始前必须依次满足：
  前一层最终 D write handshake 已接受、normal FIFO 已空、scratch 对下一层
  read 可见。此屏障仍缺 cycle-level 动态证明。

## CGRA_SIM / explicit tree / W3 golden 三方结果

- 32,768 个 49 元素向量逐项一致。
- 逻辑层宽：`49,25,13,7,4,2,1`。
- 三方输出 SHA256 均为
  `f838df652cadb27110ed79084f49fd7e80445277d497e0d6e019c49132b73117`。
- 输出范围：0..2477。
- CGRA 证据使用锁定源码的 `SUM.SUM` 数值入口。没有调用
  `SUM.execute/compute` transport wrapper，因为锁定版本的
  `SUM.compute` 以不兼容参数个数调用 `BaseOP.reshape`。
- 该结果只证明软件数值语义；没有消费配置、码流或 execplan，不能证明
  MSE 动态路由或服务器执行。

## 新增文件与身份

- `resnet50_pipeline/gap_int32_mac_bypass.py`
  - SHA256
    `a0f0b665aa65279b7c79caf5e8d27d93ed707a422e49b8fbca03d7c8d0e0a35e`
- `tools/run_cgra_gap_int32_mac_bypass_reference.py`
  - SHA256
    `2d13a5fd005c0d1c7f3fa3b4a8e788b75092d27bcb48b21cb99db3990afda4f6`
- `tools/build_gap_int32_mac_bypass_contract.py`
  - SHA256
    `49ef510ca8f10be34ba4583dd5aafe1769e542e33ce2b4d795ec859f807e67c3`
- `tests/test_gap_int32_mac_stage_memory.py`
  - SHA256
    `4fa01a20439f03d9b72d5450b9c5530fc88f5bcc45f0049afc418bad3a2b7549`
- `artifacts/operator_config_validation/gap-int32-mac-bypass-v1/cgra_sim_reference.json`
  - 2221 bytes
  - SHA256
    `71a17ffa4063738ccb763e8753732925e090640d7a38d166de794c4e2b5ddcb4`
- `contracts/operator_config/gap_int32_mac_bypass_v1.json`
  - 只保存地址摘要、哈希与首尾样本，不保存全量 occurrence。
  - SHA256
    `896ad1915cfed421d659926d3512b50fa68cfd4317844b8e132bcec7927b77bb`

## 测试

- `tests.test_gap_int32_mac_stage_memory`：9 项通过。
- `tests.test_gap_int32_mac_reduction_semantics`：10 项通过。
- GAP D-index / accumulator-state / RTL-repair / repair-workload /
  repair-release 回归：19 项通过。
- 本轮合计：38 项通过。

## 仍未解除的 blocker

- `B_GAP_GA_ACCUM_STATE`：原 `int32_sum` 路径仍然开放；只有真实
  opcode14 动态路线通过后，才可称绕过该触发路径。
- `B_GAP_INT32MAC_REAL_STAGE_ARTIFACTS`：六层真实 JSON、mapping、
  bitstream、execplan、SCA 尚未生成。
- `B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM`：两路 MSE first/skew/stall/resume
  和同 pair 消费尚未动态证明。
- `B_GAP_INT32MAC_STAGE_BARRIER`：逐层 drain/visibility/reconfigure
  尚未动态证明。
- `B_GAP_INT32MAC_FORMAL_READBACK`：16 片 × 512 条正式 D readback
  与独立 golden 尚未执行。

下一步仍受暂停令约束。在收到新指示以前，不生成服务器候选包。
