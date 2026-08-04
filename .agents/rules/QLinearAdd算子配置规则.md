# QLinearAdd 算子配置规则

最后更新：2026-08-02（修正 D-buffer 事务供给守恒）

本文件保存 ResNet50 17 个 QLinearAdd 的专项数值、复合 DAG、typed qparam 和
address/lifetime 增量。公共 provenance、物化回环、证据等级和共享 output quant
由公共规则及 `精确UINT8量化尾专项规则.md` 拥有。

当前裁决：

```text
predesign = COMPLETE_17_OF_17
stage0_config_bound_candidate = COMPLETE_17_OF_17
complete_operator_materialization_allowed = NODE0007_LOCAL_E2_ONLY
candidate_release = false
formal_target_instance_allowed = false
dynamic_baseline = NODE0007_V16_RETURN2_PROVEN_STAGE3_WRITE_BACKEND_HANG
local_candidate = NODE0007_COLUMN_PAIR_V18_LOCAL_VALIDATED_NOT_PACKAGED
server_package_ready = NONE_PENDING_CURRENT_RULE_REVALIDATION
```

权威预设计合同为
`contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json`。
权威 stage0 合同为
`contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json`。

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

QLinearAdd output 必须消费 `精确UINT8量化尾专项规则.md`。当前 P0-A 决策为
`NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`；FMA rounding boundary、magic finite-domain、
exact division、three-PE topology、typed binding 和 mapper registration 尚未闭合。

stage0 子范围的 W3 DAG、paired readiness、node0076 replay/tail、scratch
non-overlap/barrier/lifetime 与 config-bound negative control 已局部闭合。

node0007 已在冻结六 qparam、W3 顺序和共享 exact UINT8 tail 下完成 fresh nested-LC
本地 E2：六个串行 stage、最终 JSON、6/6 mapping/bitstream、execplan/SCA、
37,352,448 requests、地址/coverage/lifetime 与 config-bound golden 已闭合。该本地
结论不能单独签发服务器运行包：v6 正式动态回传已经证明同一冻结 workload 在首个
`op_a_dequant Start_Comp` 后、首个 MSE request 前进入长期零进度卡死；任何复用该
workload 的 v8 或其他派生包必须隔离。该结论不外推到其余 16 个 QLinearAdd，也不关闭
最终服务器 RTL identity、E4 正式 readback、E5 独立重跑或 performance qualification。

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

node0007 v6 的冻结动态反例为：88.78 分钟、23,330,816 连续 active cycles、
22 个完整 stall window，qualified `req/rdata/wdata=0/0/0`、`COMP_FINISH=0`；
最后正证据是 `op_a_dequant EXEC_START`，第一坏边界是首个 DRAM LC address
enqueue/MSE request 始终未出现。后续 v13 通过窄定位证明该区间的确定根因是六个
`Load_Config` payload 虽已打包但没有对应 SCA config preload，导致所有物理 LC
enable 保持0；v14 增加六条一一绑定的 config preload 后，A/B dequant 与首请求链
均已动态前进。因此该旧区间 blocker 已关闭，但上述内部-ready观测门继续适用于其他
Start_Comp→first-request 卡死。

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

node0007 v14、v15、v16 保留为冻结动态反例：

- v14 的三个目标 stage 只供应一个 16-byte窗口，无法完成32-byte transaction；
- v15/v16 把 `buf_spatial_size=16` 错当物理 row 宽度，配置两个32-byte physical row，
  且 `COL_LC stride=2` 形成错误/重叠窗口；旧标量式 `2*16=32` 掩盖了
  `2*32=64` 的物理 overcoverage；
- v16 return(2) 已证明 A/B dequant 自然完成，真实首坏 stage 是
  `op_relocation_pad` 的 Buffer5→Buffer_AG→RD_Buffer_AG→WR_Data_Channel 写回链。

因此撤销 v15 的旧批准方案；不得再使用：

```text
GROUP2.ROW_LC.end:        1 -> 2
buffer5.buf_end_row_addr: 0 -> 1
```

node0007 本地 v18 的批准候选仅用于按本规则重新验收，不能因本节文字直接升级：

```text
GROUP2.ROW_LC.end:        2 -> 1
GROUP2.COL_LC.end:        4 -> 32
GROUP2.COL_LC.stride:     2 -> 16
buffer5.buf_end_row_addr: 1 -> 0
```

它应形成同一32-byte row内的两个不重叠窗口 `[0,16)`、`[16,32)`，并与
`ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json` 的原生写回结构交叉核对。最终是否
满足本规则，必须由QLinearAdd owner直接读取本地 v18 最终 JSON/bitstream/RTL合同重新
验证，并在服务器包生成后执行 current-rule final-ZIP 自检；本规则本身不授权封包或
服务器运行。

不得以延长 timeout、减小正式 transaction、预置 D、丢弃第二拍或只修改 observer
掩盖该守恒错误。
