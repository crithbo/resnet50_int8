# QLinearAdd 算子配置规则

最后更新：2026-08-11（剥离版本状态，保留 QAdd 稳定合同）

本文件保存 ResNet50 17 个 QLinearAdd 的专项数值、复合 DAG、typed qparam 和
address/lifetime 增量。公共 provenance、物化回环、证据等级和共享 output quant
由公共规则及 `精确UINT8量化尾专项规则.md` 拥有。

当前完成度、blocker、候选身份和服务器结果只看 `.agents/plan.md` 与对应 task record；
本文件不授予 package release。

## 1. W3 数值顺序

规则 ID：`CDA-QADD-W3-OPERATION-ORDER-001`

两支输入必须严格按下列逐操作 FP32 顺序执行：

```text
a_i32 = int32(A) - int32(a_zero_point)
b_i32 = int32(B) - int32(b_zero_point)
a_f32 = float32(a_i32)
b_f32 = float32(b_i32)
a_scaled = round_float32(a_f32 * float32(a_scale))
b_scaled = round_float32(b_f32 * float32(b_scale))
sum_f32 = round_float32(a_scaled + b_scaled)
quotient = round_float32(sum_f32 / float32(y_scale))
rounded = round_nearest_even_to_int64(quotient)
shifted = rounded + int64(y_zero_point)
Y = uint8(clamp(shifted, 0, 255))
```

禁止改写为 `x*scale + float32(-zero_point*scale)`。17 组 qparam 的全
`65,536` 个 A/B 标量组合穷举已在 node0007 和 node0070 找到最终 UINT8 反例，
因此现有 add-dequant 只能复用 read/buffer/GA/write 结构，不能复用 affine 数值。

## 2. 六 qparam typed transport

规则 ID：`CDA-QADD-SIX-QPARAM-TYPED-TRANSPORT-001`

typed request 必须按固定角色承载：

```text
a_scale, a_zero_point, b_scale, b_zero_point, y_scale, y_zero_point
```

scale 以 exact float32 bits/value hash 绑定；zero-point 以 exact UINT8 scalar/value
hash 绑定。handler 必须消费全部六项并拒绝 missing、extra、dtype/shape mismatch。
mapper 只能放置已经 typed 的 stage DAG，不得推断 qparam、沿用模板常数 1 或默认 output
quant。

`B_QADD_NATIVE_TYPED_HANDLER` 在原生 OperatorSpec/json_loader/control handler 完整承载
六项前保持开放。

## 3. residual 与 broadcast DAG

规则 ID：`CDA-QADD-RESIDUAL-BROADCAST-DAG-001`

覆盖固定为 16 个 same-shape residual 与 node0076 的 trailing-axis broadcast：

```text
A/Y = [16,1000]
B   = [1000]
```

node0076 的 B 是 1000-byte immutable region；16 个 batch 必须重放同一 region，
禁止物化 16 倍 copy。validator 必须枚举全部 request occurrence/address；其
`y_zero_point=60` 是共享 quant-tail 的强制 nonzero-zp holdout。

single-stage fused 保持 `UNDECIDABLE`；two-stage explicit FP32 scratch 只算
`STRUCTURALLY_FEASIBLE_NUMERIC_TAIL_UNCLOSED`。scratch 大小为
`4*product(Y.shape)`、16-byte aligned、non-alias，并从 stage0 首写活到 stage1
最后 accepted read；必须有显式 DRAM visibility 与 completion barrier。

这里的 two-stage 是“W3 FP32 sum→UINT8 tail”的逻辑分区；在 stock topology 上，
W3 前半段必须进一步物化为 A exact dequant、B exact dequant、paired FP32 add 三个
串行 physical stage，不得把三次独立 FP32 舍入误称为一个 fused static stage。

## 4. stage0 三阶段、broadcast replay 与声明边界

规则 ID：`CDA-QADD-STAGE0-THREE-PHYSICAL-STAGES-001`

每个 QLinearAdd 的 W3 前半段固定为三个 physical stage：

1. A：`uint8→int32(A-zpA)→float32→round_float32(*a_scale)`；
2. B：`uint8→int32(B-zpB)→float32→round_float32(*b_scale)`；
3. `round_float32(A_scaled+B_scaled)`。

三个 stage 使用不 alias FP32 scratch、显式 DRAM visibility 和 completion barrier；
第三阶段必须在 A、B 与 D 同时 ready 时接受 pair。当前 17 个逻辑实例对应 51 个
physical stage。该结论只关闭到 `SUM_F32` 的精确子范围。

规则 ID：`CDA-QADD-BROADCAST-REPLAY-TAIL-ACCOUNTING-001`

node0076 的 B-scaled scratch 保持原始 1000 元素，不得展开为 16 倍副本；add stage
按 `logical_output_index % 1000` 重放同一 region。B-dequant 的最后 occurrence 必须
把 valid typed bytes 与 physical padding 分开计账：当前冻结实例为 63 occurrence，
末 occurrence 8 个有效 FP32 元素/32 bytes，physical allocation 4032 bytes =
4000 typed bytes + 32 padding bytes。validator 必须枚举全部 16,000 个 replay 地址，
并证明 padding 不进入逻辑结果。

规则 ID：`CDA-QADD-STAGE0-CLAIM-BOUNDARY-001`

stage0 config-bound pass 只能声明 A/B exact dequant、paired FP32 sum、scratch/barrier/
lifetime/replay 的精确子范围。共享 UINT8 tail、最终 Y、native static→address-bound
leaf diff、mapping/bitstream、execplan/SCA 和动态门未闭合时，不得声明完整
QLinearAdd `CONFIG_ONLY_CORRECTNESS_BASELINE`。

## 5. readiness、allocation 与 lifetime

规则 ID：`CDA-QADD-READINESS-LIFETIME-001`

- A：read0→buffer0→GA in0；
- B：read1→buffer2→GA in1；
- Y：GA normal outport→buffer5→write0；
- A/B/Y 禁止 alias；Y 必须 fresh allocation；
- A/B 共享 logical occurrence carrier，以 ready AND 保持 pair matching；
- Y write 使用独立授权 branch；
- 完整 ready graph 必须无环，并证明两个 read stream 均可进展；
- lifetime 以 accepted handshake 为边界，不以 request issue 为边界；
- 物化后必须证明 read bytes、Buffer supply、GA pair、GA output 与 MSE write 守恒。

node0076 的 broadcast region、16-batch replay、Y nonzero zero-point 和全部 inter-node
edge 的具体 bank/base/offset/lifetime 未闭合前，`B_QADD_BROADCAST_ADDRESS_LIFETIME`
保持开放。

## 6. 大型 FP32 scratch 的物理行边界

规则 ID：`CDA-QADD-LARGE-FP32-SCRATCH-ROW-BOUNDARY-001`

任何 QLinearAdd FP32 scratch 在进入 mapping、execplan 或 SCA 放行前，必须把最终
allocation 的每个 request 重新代入目标 `slave/bank/row/column` 地址方程，并逐 slice
证明全部 request 满足 `row < MAX_ROWS`。只验证 allocation 的起始地址、总字节数或逻辑
coverage 不足以放行。

如果任一 request 达到 `row >= MAX_ROWS`，必须 fail closed。只有 QLinearAdd owner
显式执行以下一种修复并完成相应证明后，才允许继续物化：

1. 将整个 scratch 搬移到可完整容纳它的合法物理区间；或
2. 将 scratch 与对应 stage 拆成独立 tile，每个 tile 使用独立合法 allocation。

搬移或拆分后必须重新证明 non-alias、completion barrier、accepted-handshake lifetime、
逐 tile occurrence 守恒、完整有效字节 coverage、padding 隔离，以及从空 mapping state
重建最终 JSON→mapping→bitstream→execplan/SCA 的确定性。禁止只截断越界 request、
回卷 row、复用旧地址，或以 host 预计算/预置中间 tensor 绕过该门。

冻结反例为 node0007 的 `op_fp32_add/WRITE_STREAM0`：FP32 SUM scratch
base=`0x005be000`、bytes=`2,408,448`、end-exclusive=`0x0080a000`，原 no-free
planner 在 row 5880 起放置并首次生成 row 6144，而目标要求 `<6144`。该反例证明的是
物理地址不可编码，不推翻已通过的 QLinearAdd W3、tail、config-bound 数值或
mapping/bitstream 算术证据。

## 7. 大循环嵌套拆分与字段宽度耦合

规则 ID：`CDA-QADD-NESTED-LC-FACTOR-WIDTH-COUPLING-001`

QLinearAdd 的大型 FP32 activation/scratch schedule 若把 flat DRAM LC 拆成嵌套
LC，必须联合满足：

1. 当前正 stride DRAM LC 的每个 `end<=32768`；
2. 每个派生 outer `dim_stride` 均能无损编码进 unsigned 20-bit 字段；
3. `outer_count*inner_count` 精确等于冻结 logical occurrence count；
4. flat 与 nested 的 ordered offset hash、最终逐 slice request signature、有效字节
   coverage 与 terminal occurrence 全部相同；
5. 从空 mapping state 重建最终 JSON→mapping→bitstream→execplan/SCA，并重新证明
   barrier、accepted lifetime、non-alias 与 config-bound golden。

node0007 的冻结反例与批准修正为：

- 旧 flat `end=37632` 在 16-bit signed feedback 上回绕，动态不可终止；
- dequant `2×18816` 虽满足 LC end 门，但 write outer stride
  `18816×64=1204224` 超过 `1048575`，必须拒绝；
- dequant `4×9408` 的 read/write outer stride 分别为 `150528/602112`；
- FP32 add `8×18816` 的 outer stride 为 `301056`；
- 最终所有正 stride LC 的最大 `end=18816`。

禁止把延长 watchdog、截断 stride、地址回卷或只比较 occurrence 总数当成修复。

## 8. shared quant-tail 依赖与停止门

规则 ID：`CDA-QADD-EXACT-QUANT-TAIL-DEPENDENCY-001`

QLinearAdd output 必须消费 `精确UINT8量化尾专项规则.md`。只有 six-qparam typed
transport、A/B dequant、FP32 add、exact UINT8 tail、broadcast replay、地址、transaction
supply、scratch barrier/lifetime 与最终物化回环在同一冻结实例上全部闭合，才能通过
本族 complete-JSON 门；任一共享能力未闭合均 fail closed。

## 9. Start_Comp 到首请求卡死的内部 ready 可观测门

规则 ID：`CDA-QADD-FIRST-REQUEST-HANG-INTERNAL-READY-OBSERVABILITY-001`

当 QLinearAdd 已接受 `Start_Comp`，但一个完整声明的 `stall_window` 内没有任何
qualified DRAM request、read-data、write-data 或 completion 进展时，必须把卡死定位到
“Start_Comp→首个 request”区间，并在下一只定位包中同时回收以下 qualified 状态：

1. 本 stage 所有 active DRAM LC 的 enable、output-valid 与 output-ready handshake；
2. 被选择的 MSE index input valid/ready、match、queue empty/full；
3. MSE request enqueue valid/ready 与首个正式 request handshake；
4. 对应 stage/slice、active-cycle 窗口和唯一 canonical decision。

持续为高的 enable/ready/valid level 不能按周期累计成新事务。若空 MSE index/request
queue 按 RTL 可以接收初始工作，则不得仅凭 shared-LC 扇出、AND-backpressure 或静态
拓扑宣称组合环为根因；必须指出第一条不再变化的 qualified handshake，并由活动 RTL
消费者方程和动态窗口共同证明。

在上述第一阻塞点未闭合前：

- 禁止用延长 timeout 作为修复；
- 禁止仅凭地址、LC 编号或共享根拓扑猜测改写配置；
- 禁止复用已实证卡死的冻结 workload 生成新的可运行包；
- 只允许生成不改变 workload/config 数值语义的窄定位包，并仍须通过最终 ZIP
  current-rule 自检。

版本化动态反例和已关闭 blocker 只保存在 task record。本观测门对所有
`Start_Comp→first-request` 卡死继续有效。

## 10. D-buffer 事务供给守恒

规则 ID：`CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`

每个向 D/write MSE 提交多拍写事务的 QLinearAdd stage，最终物化 JSON 必须从活动
RTL 常量、最终 `ROW_LC/COL_LC` 和被 `Buffer_AG_Idx_Queue` 接受的成对 tag 重建
Buffer5→write-MSE 的字节窗口。禁止把 `stream.buf_spatial_size` 当作物理 Buffer row
宽度，也禁止只用 ROW trip count 推导事务供给。

```text
buffer_row_bytes
  = BUFFER_BANK_NUM * BUFFER_BANK_DATA_NUM

mse_read_bytes
  = MSE_BUF_REQ_NUM * MSE_BUF_REQ_DATA_WIDTH / 8

window(row, col)
  = [row * buffer_row_bytes + col_byte_offset,
     row * buffer_row_bytes + col_byte_offset + mse_read_bytes)

transaction_coverage
  = disjoint_union(all accepted window(row, col))
```

其中 `col_byte_offset` 必须按活动 RTL 对 Buffer column tag 的单位和地址方程解码，
不得从 JSON 字段名或历史模板猜测。validator 必须直接读取最终 JSON、最终 bitstream
解码值、活动 RTL 常量/消费方程和目标 write transaction 合同，逐 stage 检查：

1. 每个窗口完全位于其物理 Buffer row 内：
   `0 <= col_byte_offset` 且
   `col_byte_offset + mse_read_bytes <= buffer_row_bytes`；
2. 窗口起点来自 `Buffer_AG_Idx_Queue` 实际接受的 ROW/COL 成对 tag；ROW、COL 任一侧
   未匹配、未接受或重复的 level 均不得生成新窗口；
3. 同一 transaction 的窗口并集无 gap、无 overlap，并与目标 transaction 的
   `[0, transaction_bytes)` 精确相等；只比较总窗口数或总字节数不足以放行；
4. `buffer5.buf_end_row_addr` 等于全部窗口实际触及的最大物理 row，而不是
   `trip_count(ROW_LC)-1` 的无条件别名；
5. write request 数、prepared-data beat 数、accepted write-data 数与窗口供给守恒，
   并联合绑定 qualified Buffer5 GA write accept/row-bank valid、
   Buffer_AG pair enqueue/dequeue、RD_Buffer_AG request/clear、
   WR_Data_Channel request/prepared-data/accepted-wdata/outstanding；
6. 删除任一窗口、制造窗口重叠或空洞、恢复错误 `COL_LC.stride=2`、增加未使用的第二
   physical row、篡改 MSE read width/transaction length、或只改
   `buf_spatial_size` 的负控必须全部 fail closed；
7. 修复后必须从空 mapping state 重建 JSON→mapping→bitstream→execplan/SCA，并证明
   地址、DRAM occurrence、数值 DAG、golden、ready/backpressure 与 formal D 合同没有
   非授权变化。

当前活动 RTL 常量给出：

```text
buffer_row_bytes = 8 banks * 4 bytes = 32 bytes
mse_read_bytes   = 16 lanes * 1 byte = 16 bytes
```

历史错误参数、修复候选和版本化动态反例只在 task record 追溯。fresh 配置必须从最终
RTL 常量和目标 transaction 重新计算窗口，不能把任何历史版本字段值当作授权模板。

不得以延长 timeout、减小正式 transaction、预置 D、丢弃第二拍或只修改 observer
掩盖该守恒错误。

## 11. A/B input-buffer 事务供给守恒

规则 ID：`CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`

QLinearAdd 的双输入计算 stage 在启动 Buffer0/Buffer2→Array Request Manager 读之前，
每个 operand buffer 都必须由上游 MSE→Buffer accepted write 窗口独立覆盖下游
ARM masked row 所要求的全部物理 bank/byte。第10节约束 D/writeback 方向；本节约束
A/B read-side ingress，二者不得互相替代。

对每个 operand `i ∈ {0,1}`：

```text
buffer_row_bytes
  = BUFFER_BANK_NUM * BUFFER_BANK_DATA_NUM

producer_window_i(row, col)
  = [row * buffer_row_bytes + col_byte_offset,
     row * buffer_row_bytes + col_byte_offset + producer_write_bytes_i)

required_arm_bytes_i
  = exact byte set selected by ARM bank mask, row address and operand layout

accepted_supply_i
  = disjoint_union(all qualified accepted producer_window_i(row, col))
```

必须满足：

```text
accepted_supply_i == required_arm_bytes_i
```

validator 必须直接绑定最终 JSON、mapping/bitstream 解码、活动 RTL 的 transaction/
bank-mask 方程以及 qualified producer→Buffer/Buffer→ARM/ARM→GA 证据，并逐 operand
检查：

1. 每个 producer window 完全位于目标物理 row，起点来自实际接受的 ROW/COL tag；
2. 同一 ARM row 所需窗口无 gap、无 overlap，窗口精确并集等于 masked bank/byte set；
   总字节数相同但 bank/lane、row 或 column 分布不同不得放行；
3. Buffer0 与 Buffer2 分别验收；一侧完整不能替代另一侧，单边 MSE/GA level 不能计作
   paired ingress progress；
4. 在 ARM request accept 前，所选地址的全部 required bank/byte valid 必须已由
   qualified producer write 建立；`req_valid` 持续高、`ready=0` 或单次16B写不能冒充
   32B masked row 已就绪；
5. 动态证据至少绑定两侧 producer write accept、per-bank/per-byte valid-at-address、
   ARM mask/request/ready/accept、Buffer delivery 和 GA 双输入 capture/pair/accept；
6. 删除任一 column window、重复首窗口、制造 gap/overlap、错配 row/column 单位、
   仅修改 `buf_spatial_size`、或把全8-bank mask缩窄来迁就不完整供给的负控必须
   fail closed；
7. 修正后从空 mapping state 重建 JSON→mapping→bitstream→execplan/SCA，并证明
   workload、数值 DAG、地址、ready/backpressure、golden 与 formal D 合同没有非授权变化。

若 producer 只有一笔 16B accepted write，而 consumer ARM 需要完整 32B row mask，必须
判为供给不足；合法候选应在同一物理 row 内形成无重叠、无空洞的完整窗口并由 fresh
最终物化和动态 return 验收，不能仅凭静态总字节数升级。

不得以缩窄 ARM mask、预载内部 tensor、延长 timeout、跳过一侧 operand 或只改 observer
掩盖供给不足。
