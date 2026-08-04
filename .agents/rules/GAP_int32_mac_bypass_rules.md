# GAP int32_mac pure-config bypass rules

最后更新：2026-07-27（node0071 sum-stage config-only local E2 已闭合）

## 1. 当前边界

目标是在不修改功能 RTL 的前提下，用普通 GA `int32_mac(A,1,C)` 多 stage 加法树规避
原 `int32_sum` transout/outbuffer feedback 缺陷。

用户继续冻结本路线的功能 RTL repair、服务器续测和新包生成；允许的纯配置本地闭环已
完成。同系列不存在自然完成并通过正式 readback 的 known-good 动态身份，逐版本结果只在
task record 追溯。

因此当前固定为：

```text
candidate_release=false
sum_stage_evidence_level=E2_LOCAL
complete_gap_target=false
server_package_allowed=false
dynamic_baseline=NO_DYNAMIC_BASELINE
```

不得把本路线后续失败称为“回归”。本地 sum-stage E2 不能替代 dual-stream/FIFO/barrier
动态门、正式 readback 或 shared exact UINT8 tail。

## 2. `CDA-GAP-INT32MAC-NONTRANSOUT-001`

- opcode 固定为 `int32_mac=14=5'b01110`；
- `alu_op_is_transout` 必须为 false；
- PE 方程固定为 `D=int32(A*B+C)`，B 为常数 1；
- 禁止使用 `int32_sum`、`sum`、`summac` 或 outbuffer feedback 归约；
- `transout_last_index` 必须为 null。

该规则只证明 opcode 分类；不证明 A/C producer、tag、FIFO 或 writeback 正确。

## 3. `CDA-GAP-INT32MAC-DUAL-INPUT-001`

- A 使用 READ_STREAM0→buffer0→GA group0；
- C 使用 READ_STREAM3→buffer4→GA group2；
- B 使用 PE constant 1；
- buffer5 只作 GA 写回，不得作为 C 输入；
- A/C occurrence 必须同拍 match，任一侧 stall 时另一侧不得越过；
- A/C 的 tag、last、last_index 必须逐 occurrence 相同；
- 每次 accepted match 必须恰消费一个 A 和一个 C。

buffer0、buffer4、buffer5 分别是 `(group0,slot0)`、`(group2,slot0)`、
`(group2,slot1)`。上述拓扑必须在最终 JSON、mapping 和 parsed bitstream 三层一致。

## 4. `CDA-GAP-INT32MAC-NORMAL-FIFO-001`

- opcode14 走 normal outbuffer；
- count 只按 accepted write/read 更新：
  `next=count+write-read`；
- 任意周期 `0<=count<=2`；
- 同时 read/write 不得读取无效槽或覆盖未读槽；
- 测试覆盖 empty、single、full、stall、resume 和同时 read/write；
- invalid tag/slot 不得影响 ALU C 或下一 block。

该规则用于证明绕行不触发 v7 transout compaction，不自动解除原
`B_GAP_GA_ACCUM_STATE`。

## 5. `CDA-GAP-INT32MAC-TREE-001`

逻辑 49 项归约为：

```text
49 → 25 → 13 → 7 → 4 → 2 → 1
```

每层使用 `int32_mac(left,1,right)`；奇数尾项 right 必须是显式零，不得越界或复用旧
buffer。UINT8 最终范围为 `0..12495`，无 INT32 overflow。

物理 padding/transaction 计划必须由最终 JSON 回环证明；不得把逻辑树或独立 numpy
公式直接写成已闭合硬件 schedule。

## 6. `CDA-GAP-INT32MAC-STAGE-MEMORY-001`

每层必须同时证明：

- 输入/输出 shape、dtype、layout 和逐 C8 block occurrence；
- A/C ordered address 一一配对；
- memory transaction、buffer spatial bank/byte 和 GA lane 消费守恒；
- 中间 INT32 write region 完整、互不覆盖且下一层可见；
- 全部 256 个 C8 block 和 16 slice 覆盖；
- terminal tag 不早停、不泄漏到下一层；
- stage reconfigure 发生前 buffer5、normal FIFO 和 scratch write 已 drain；
- 每层 config/mapping/bitstream/execplan/SCA provenance 独立；
- 最终每 slice 512 条 128-bit D readback 逐行 golden。

## 7. `CDA-GAP-INT32MAC-STAGE1-ALIGNED-EVEN-ODD-001`

旧 int32_mac v1 的 16B materialization 和独立 `C_base=A_base+8` 路线保持否决。RTL
丢弃 stream base 低 4 位，因此 8B C8 pair 不得靠 base+8 选择右操作数。

当前 node0071 sum-stage local E2 固定：

- A/C 使用同一个 16B-aligned base，但分别由独立 LC branch 拥有索引；
- A：`start=0,stride=2`，产生 `0,2,...,62`；
- C：`start=1,stride=2`，产生 `1,3,...,63`；
- 两支 transaction bytes 均为 8，ordered cardinality 必须相等；
- 8 个 C8 lane 的 `buf_spatial_stride` 固定为
  `[0,4,8,12,16,20,24,28]`，它们通过
  `low5(col_base + buf_spatial_stride) >> 2` 选择 8 个 bank；
- 对 8B read，COL LC 必须独立产生 `0,1,2,3`，由
  `low5(col_base + buf_spatial_stride) & 3` 依次选择每个 bank 的四个
  byte lane；四次 transaction 才形成一个全有效的 32B Buffer row；
- 禁止把 bank 空间偏移误写成 COL LC 序列 `0,4,8,...`。该序列的低
  2 位恒为 0，只会重复写每个 bank 的 byte lane 0；Buffer 的
  array-ready 要求所有启用 bank 的四个 byte-valid 位均为 1，因此会在
  第一次写入后永久停滞；
- A/C/D 分别使用独立 branch roots，越过真实 0..48 域的索引必须显式 padding；
- final materialized JSON 必须重新证明 pairing、padding、branch、buffer supply 和
  contiguous D byte coverage。

六级 occurrence/slice 固定为
`[8192,4096,2048,1024,512,256]`，对应最终 D coverage 为
`[262144,131072,65536,32768,16384,8192]` bytes，均 exact contiguous。

## 8. `CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001`

真实 `r5:hwop-0071-00` 的 INT32 sum 子阶段已完成本地
`CONFIG_ONLY_CORRECTNESS_BASELINE`：

- 六级非 transout 树 `49→25→13→7→4→2→1`；
- 每级显式 INT32 scratch、reload 和 same-mask barrier；
- config-bound simulator 对真实 W3 输入逐 bit 等于独立 sum golden，输出范围
  `[0,2477]`；
- 六份 logical→final JSON 只有 planner-owned `base_addr` 变化，non-base diff=0；
- 两个隔离 mapping 的核心语义产物逐 SHA 相同；
- input replay 只复制正式 `r5:hwop-0070-00` uint8 output，不 host-precompute
  internal/scaled/rounded/saturated/final tensor。

该批准只覆盖 INT32 sum stage，不覆盖完整 QLinearGlobalAveragePool、UINT8 tail、
production/performance、服务器 target、E3/E4/E5。

## 8.1 `CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001`

每个 8B read 到 8-bank Buffer 的最终 JSON、bitstream 和动态包必须联合证明：

- `idx_size[0]=7`，一次 memory transaction 向每个启用 bank 写 1 byte；
- bank 选择和 bank 内 byte 选择分别按上节两条 RTL 方程计算，不能混用；
- 在一次 Buffer row 消费前，每个启用 bank 的 byte lane 0/1/2/3 恰好各写一次；
- COL LC 的 ordered sequence、transaction count、最终 bitstream decode 和
  Buffer row-valid 覆盖完全一致；
- 删除任一 byte lane、重复任一 byte lane、恢复旧 `0,4,8,...` 序列或仅修改
  报告而不修改 bitstream，validator 必须 fail closed。

该门属于配置语义硬门。若动态证据表现为 memory→Buffer 首次 accept 后
Buffer ARM/GA ingress 永远无 qualified accept，应优先核对本门，而不是先归因
GA、timeout 或服务器环境。

## 9. `CDA-GAP-INT32MAC-BRANCH-ISOLATION-001`

当前物化 JSON 让 A/C/D stream 与三个 buffer group 共享同一 DRAM LC branch。IGA
上游 ready 是全部目的 ready 的 AND；共享 root 可能耦合 read/write backpressure。

该项目前是 `STRUCTURAL_RISK`，不是已证明根因。恢复路线时必须二选一：

1. 证明共享 LC 的 trigger/tag/ready 图无环且有进度；或
2. 按授权工作模板为 A/C/D 使用独立 branch roots，并完整重建/验证。

不得凭静态风险直接宣称服务器卡死根因。

## 10. SCA_D 和服务器动态门

旧 16-slice/512-line SCA_D 合同不自动适用于当前 28-slice 六级 local baseline。当前
没有获批服务器包或正式 readback shape；未来如获用户新授权，必须从最终六级
address-bound JSON 独立派生新的 SCA_D/return 合同，不得沿用旧 identity。动态放行仍
必须通过：

- 正确 SCA/SCA_D 回显和 16 个 D dump；
- dual stream first/skew/stall/resume；
- normal FIFO 全周期 occupancy 和 invalid-slot isolation；
- 六级 drain/barrier/lifecycle；
- 28-slice 正式 readback coverage 与独立 golden；
- 全新身份重复 E5。

自然完成、内部 MSE4 write、请求总数或通用 validator valid 都不能替代这些门。
