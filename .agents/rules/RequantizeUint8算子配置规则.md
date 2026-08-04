# RequantizeUint8 算子配置规则

最后更新：2026-07-29（node0004 direct signed two-stage 执行覆盖）

本文件只保存 `INT32 accumulator → UINT8` requantize 的算子特有增量规则。公共 provenance、
物化回环、证据等级和硬件字段定义由公共规则唯一拥有。

## 0. node0004 direct signed two-stage 覆盖

规则 ID：`CDA-REQUANT-NODE0004-DIRECT-SIGNED-TWO-STAGE-001`

用户已授权按服务器侧 signed INT32→FP32 修复可用推进
`node-0004 / r5:hwop-0004-01`。本实例不采用 node0001 的 guard/SFU/max0 recipe，
不消费任何 node0004 历史物化资产；只从 typed request、正式 ONNX/W3、活动工具与
当前规则 fresh rebuild。

node0004 的冻结合同为：

```text
shape = INT32[16,64,56,56] → UINT8[16,64,56,56]
y_zero_point = 0
multiplier[c] = float32(float32(x_scale * w_scale[c]) / y_scale), c=0..63

stage0 = corrected_signed_int32_to_fp32(acc)
         → explicit_fp32_mul(multiplier[c])
         → fp32_scratch
stage1 = raw_fp32(fp32_scratch)
         → add_magic(12582912.0)
         → bitcast_int32
         → sub(0x4b400000)
         → saturate_uint8
```

stage0 与 stage1 必须由显式 scratch 和 completion barrier 隔开，禁止融合为
one-round FMA；不得 host 预计算或 preload scaled/rounded/saturated/final tensor。
64 个 multiplier 必须逐 bit 运输到最终物理 lane/occurrence。完整 W3 的
3,211,264 个元素必须同时满足 stage0 位模式域检查与最终 UINT8 mismatch=0。

允许本轮使用哈希绑定的显式 materializer 补齐 placeholder handler/mapper 的
node0004 专用运输，但 materializer 必须接受 typed qparam、输出最终 JSON leaf
ownership audit，并完成 mapping→bitstream→execplan/SCA→config-bound inverse 回环。
本地门通过后可生成 `PACKAGE_READY_NOT_RUN`；服务器未运行前仍为
`candidate_release=false`、`formal_target_instance_allowed=false`，不计 E4/E5。

本节只覆盖 node0004。下文 node0001 guard 动态历史与其 blocker 保留，不得外推到
node0004；其他 Requant 实例仍按各自 zero-point、shape 与共享能力门裁决。

当前裁决：

```text
local_generation_status = APPROVED_FOR_CONDITIONAL_TWO_STAGE_E2
formal_target_instance_allowed = false
candidate_release = false
dynamic_release_ready = false
```

首个、且当前唯一完成物理物化 E2 的代表项固定为 `r5:hwop-0001-01`
（`node-0001 / QLinearConv / requantize`）。全体 54 个 Requant request 的数值分类
可以关闭“是否满足当前 recipe 前提”，但不自动批准新 shape、zero-point、
AverageRequant、QLinearAdd 或 MatMul 实例的 JSON emission。

## 1. 权威输入与模板边界

- typed request：`contracts/resnet50_r5_lowering_bundle.json` 中
  `r5:hwop-0001-01`；
- W3 accumulator/input 与独立 UINT8 golden：typed request 所绑定的正式 W3 文件；
- 已授权 requant 拓扑：
  `ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json`；
- 已授权 SFU normal-output 拓扑：
  `ndp-sim/jsons/decode_silu_fp16N_fp32N.json`；
- RTL 语义消费者：
  `GA_Inport.sv`、`Binary_Search_Tree.sv`、`Comparator.sv`、
  `GA_SFU_LUT.sv`、`GA_SFU_PE.sv`、`GA_PE_ALU.sv`、`GA_ALU.v`、
  `GA_PE_Float_*.v`、`GA_Outport.sv`；
- execplan/SFU 直接消费者：
  `operator_base_info.json`、`template_manager.py`、`control_registers.py`、
  `pipeline.py`、`instruction_generator.py`、`output_writer.py`。

授权模板只授权字段拓扑及其已验证的硬件含义，不授权旧 shape、地址、常量或近似激活
系数。活动 `ndp-sim`、`ndp-sim-ref` 和全部 `rtl/` 保持只读；项目适配只允许发生在
哈希绑定的隔离工具副本。

## 2. 精确数值合同

规则 ID：`CDA-REQUANT-QPARAM-001`

本规则批准的实例必须同时满足：

```text
y_zero_point == 0
isfinite(multiplier[c])
multiplier[c] > 0, for every channel c
multiplier[c] = float32(x_scale * w_scale[c] / y_scale)
```

目标值为：

```text
r[c] = float32(max(acc[c], 0)) * multiplier[c]
q[c] = saturate_uint8(round_to_nearest_even(r[c]))
```

浮点乘法、magic-rounding 和饱和的实际顺序不可代数重排。每个 per-channel multiplier
必须以 FP32 bit pattern 写入对应物理 lane，禁止只保存首元素或十进制近似摘要。

规则 ID：`CDA-REQUANT-FAMILY-QPARAM-CLASSIFICATION-001`

全体 typed Requant request 必须逐项从 ONNX initializer 重新计算 multiplier，并与
typed hash、正式 W3 accumulator 和 UINT8 golden 绑定。当前 54-stage 审计结果为：

- 54/54 的 multiplier 均为有限正数，独立 `round-to-nearest-even(scaled)+zero_point`
  软件公式均与 W3 golden 完全一致；
- 33 项 `y_zero_point=0`，数值上满足当前 guard recipe；其中只有 node0001 已完成
  JSON、W4 lifetime、bitstream、execplan 与 SCA 的物化 E2；
- 其余 32 项只可标记
  `NUMERIC_RECIPE_COMPATIBLE_PHYSICAL_E2_PENDING`，不得由相同公式直接放行；
- 21 项 `y_zero_point!=0`，均不得复用 node0001 的 clamp guard。

共享能力合同进一步裁决为 `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`。因此 33/33
`y_zero_point=0` 项即使保留 W3/当前 recipe 数值兼容，也全部继续受
`CDA-QUANT-TAIL-NUMERIC-ORDER-001` 的 FMA rounding boundary 和
`CDA-QUANT-TAIL-MAGIC-DOMAIN-001` 的 finite-domain 门约束；这不撤销 node0001
已完成的实例级本地 E2，但禁止把它推广为全族硬件能力。

全量机器记录由 `contracts/operator_config/requant_family_classification_v1.json`
绑定；分类合同是只读数值证据，不是新 JSON 的生成授权。

规则 ID：`CDA-REQUANT-INT32-GUARD-001`

原生 `GA_Inport.int32tofp32` 对负数幅值有固定反例，不能直接把负 accumulator 送入
requant MAC。条件绕行必须先执行独立 SFU guard stage：

```text
bad_convert(acc) -> sign-preserving finite FP32 z
guard(z) = z * slope[addr(z)] + intercept[addr(z)]
addr(z) = 0  when sign(z)=1
addr(z) = 65 when sign(z)=0
slope[0]=0, intercept[0]=0
slope[65]=1, intercept[65]=0
```

`GA_Inport.sv` 保留原 INT32 符号；因此所有负 accumulator 即使幅值错误，也在 guard
后成为精确 `+0`。非负 accumulator 的 converter 正向路径必须由 RTL 方程和完整 W3
逐元素回放证明与 `float32(acc)` 一致。只验证最终 UINT8 饱和结果不够。

规则 ID：`CDA-REQUANT-NONZERO-ZP-GUARD-001`

当 `y_zero_point!=0` 时，目标为
`clamp(round(acc*multiplier)+y_zero_point)`；负 accumulator 中靠近零的值可能映射为
正 UINT8。先执行 `max(acc,0)` 会不可逆丢失负数幅值，因此 node0001 guard 对这 21 项
均为 `CONTRADICTED`。正式 W3 共命中 47,844,816 个输出差异；不得用最终饱和、未命中
某个单点或 magic 常量补偿解除 `B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN`。

规则 ID：`CDA-REQUANT-SFU-LUT-001`

guard 的 SFU payload 必须是独立命名、哈希绑定的精确系数文件：

- breakpoint 65 words：全部 `0x00000000`；
- intercept 66 words：全部 `0x00000000`；
- slope 66 words：index 65 为 `0x3f800000`，其余全部 `0x00000000`；
- payload 为 50 行 × 128 bit，每行 4 个 32-bit word，按行内 MSB→LSB 消费；
- 前 197 words 依次为 breakpoint、intercept、slope，最后 3 words 必须为零 padding；
- execplan 中 SFU 长度必须反解为 100 个 64-bit word；
- 所有 guard operator 必须共享同一 `config_sfu` type、payload hash 和 SFU config
  地址，且在首次 `Start_Comp` 前出现 `Config_SFU=1` 的 `Load_Config`。

禁止复用原生近似 `ReLU.txt`；文件名相同或 `config_sfu="ReLU"` 不能代替内容验证。
`Comparator_FP32` 对全零 breakpoint 的分支必须独立回放：负数到地址 0，`+0` 和正数
到地址 65。

## 3. 两级硬件 stage

规则 ID：`CDA-REQUANT-TWO-STAGE-001`

每个 occurrence 必须由两个独立 stage 顺序实现：

1. `guard`：INT32 A read → `int32tofp32=true` → 8 个奇数列
   `sfu_activation` PE → FP32 D write；
2. `round_saturate`：上述 FP32 D 作为 A，所有 inport conversion flag 均为 false，
   8 个原生 `mac → int32_sub` lane → `int32touint8=true` → UINT8 D write。

两级均必须使用 normal outbuffer：

```text
transout_last_index = null
```

禁止用 `max`/reduction transout 实现 clamp；禁止猜测不存在的整数高乘、右移或 fixed-point
opcode；禁止修改 `rtl/`。

stage0 D 与 stage1 A 必须逐 slice 同址，stage1 A 不得出现在外部 preload/SCA 输入中。
每对 stage 之间必须有明确完成边界；CONFIG、SFU、buffer 和 stream 状态按最终
`Load_Config → Write_Reg → Start_Comp` 顺序回放。

规则 ID：`CDA-REQUANT-ROUND-MAGIC-001`

stage1 必须保留授权模板的 FP32 magic-rounding 顺序：

```text
t = fp32_fma(stage0_value, multiplier[c], 12582912.0 + y_zero_point)
i = bitcast_int32(t) - 0x4b400000
out = clamp_int32_to_uint8(i)
```

本规则当前只批准 `y_zero_point=0`。validator 必须从最终物理 PE 常量反解 multiplier、
magic 和 subtract constant，并用与 RTL 相同的 FP32 舍入点对正式 W3 全量回放。

这里的“批准”仅指 node0001 已物化身份在其正式 W3 输入域内的条件式本地 E2，不表示
one-round FMA 与目标 sequential FP32 multiply-then-RNE 在完整合法输入域恒等。新实例、
新输入域或全族推广必须同时满足 `精确UINT8量化尾专项规则.md` 的
`CDA-QUANT-TAIL-NUMERIC-ORDER-001`、`CDA-QUANT-TAIL-MAGIC-DOMAIN-001` 和对应
capability cells；区分向量 `400 × bits(0x3d828f5c)` 的 26-vs-25 分歧未闭合时，
不得以该 FMA recipe 解除共享 blocker。

规则 ID：`CDA-REQUANT-ZP-TIE-PARITY-001`

对非零 zero-point，不得把
`round-to-nearest-even(scaled)+zero_point` 默认改写为
`magic_round(scaled+zero_point)`。当 zero-point 为奇数时，两者在 exact half tie
上的偶数奇偶基准相反。`r5:hwop-0014-01` 的正式 W3 已命中 32 个反例：
`scaled=4.5`、`zero_point=123` 时 golden 为 127，而旧 magic 路径为 128。
因此五个 odd nonzero-zero-point stage 还必须保留
`B_REQUANT_MAGIC_ZP_TIE_PARITY`；即使某次输入未命中 tie 也不能按抽样解除。

## 4. layout、occurrence 与物化回环

规则 ID：`CDA-REQUANT-LAYOUT-HWC8-001`

首个实例使用已批准 W4 的 28-slice HWC8 物理布局：

- logical tensor：`INT32/UINT8 [16,64,112,112]`；
- 每个 operator occurrence 处理 8 个 channel lane；
- 每个 sample/channel shard 的物理 shape 为 `[1,12544,8]`；
- 采用 3 个 sample wave × 8 个 channel shard，共 24 个 occurrence；
- guard 中间值为 FP32，round_saturate 输出为 UINT8；
- occurrence→slice owner、地址 region、bank/column、tail 和完整覆盖必须从最终
  address-bound JSON/execplan 反解，不得从 node-0004 或生成器常量外推。

规则 ID：`CDA-REQUANT-MATERIALIZED-ROUNDTRIP-001`

本地 E2 至少同时满足：

1. 24 个 guard 和 24 个 round_saturate 的最终 JSON 全部严格可编码；
2. 每个 JSON 反解 transaction bytes、buffer bank columns、8-lane occurrence、
   tag/last/lifetime 与 read/write byte 守恒；
3. 最终 bitstream 中 guard 的 8 个物理 SFU PE、conversion bit、normal outbuffer 与
   stage1 的 8 个 MAC/sub lane、三组常量、conversion=false、UINT8 outport 均逐 bit
   一致；
4. 48 个 stage 的 producer/consumer 地址、barrier、`Repeat_Num`、CONFIG 和 SFU
   lifecycle 顺序闭合；
5. 两份空 cache、固定 seed 的隔离重建在最终 JSON、mapping、bitstream、execplan、
   SCA/SCA_D 和系数 payload 上逐文件一致；
6. 正式 W3 全量逐元素验证：
   converter→guard 中间值与 `float32(max(acc,0))` bitwise 相等，最终 UINT8 与独立
   golden bitwise 相等。

任一项失败时只报告第一处差异和 blocker；不得降级成单 stage、抽样验证或最终饱和
掩盖中间错误。

## 5. 配置绑定 simulator

规则 ID：`CDA-REQUANT-CONFIG-BOUND-SIMULATOR-001`

node0001 的 simulator 中间腿必须消费 48 份最终 address-bound JSON、24 occurrence 的
slice/sample/channel 布局、SCA/execplan 生命周期和最终 SFU payload；必须从最终 GA
opcode、conversion flag、lane multiplier、magic/subtract 常量和 stream 地址执行
guard→round，并用与服务器 readback 相同的 HWC8 inverse 还原 NCHW。不得用只读取 typed
request 的另一份公式冒充 config-bound 执行。

当前 `NDPFuncModel` 的 `ActivationUnit` 只作为原生 tie-to-even 数值交叉检查，不得声称
其已提供完整两级 target executor；`CGRA_SIM` 只作为公式参考。报告必须分列
golden↔simulator、golden↔hardware、simulator↔hardware；没有正式硬件 D 时后两项保持
`EVIDENCE_MISSING`，整体仍为 E2。冻结输入身份未变时复用报告；只在输入/执行器变化或
服务器交接前重跑一次，不在普通编辑后重复全量执行。

## 6. 动态发布门

规则 ID：`CDA-REQUANT-E4-E5-001`

本地 E2 通过后仍保持：

```text
candidate_release=false
formal_target_instance_allowed=false
NO_DYNAMIC_BASELINE
```

后续最小 stock-RTL E4/E5 由“测试修复”任务按公共服务器规则独立生成和验收；本任务不
生成服务器包。E4 必须正式回读全部 occurrence 并同时验证 guard 中间语义、最终 UINT8
golden、自然完成、return receipt 和身份门；E5 必须以全新身份覆盖至少负值、`-1`、
零、正值、round-half-even、0/255 饱和与全部 channel multiplier。E4/E5 未通过前不得
把本地资产称为正式 target config 或硬件动态闭环。

规则 ID：`CDA-REQUANT-TRANSIENT-GUARD-E4-001`

guard D 与 round A 按 slice/生命周期复用同一地址时，run 末 SCA_D 只能证明最后驻留
值，不得复制成多个历史 occurrence 的“正式 D”。alias-aware E4 必须分开报告：

1. `TRANSIENT_GUARD_WRITE_OBSERVER`：在 actual accepted MSE4 write 的 same-clock
   边界，以只读 observer 全量记录 cycle、slice、stage/occurrence、address、
   valid-mask/strobe 和 data，并逐历史 occurrence 对 guard golden；重复、缺失、额外
   或顺序错均失败；
2. `FINAL_UINT8_FORMAL_SCA_D`：最终 UINT8 的全部 shard 必须由正式 SCA_D 对 golden；
3. `LAST_RESIDENT_GUARD_FORMAL_D`：每 slice 最后驻留 guard 的唯一地址必须正式回读。

observer 只能通过服务器公共规则允许的 `rtl/` 外、事务式安装/恢复入口，且必须保存
pre/install/post-compile/post-run/post-restore identity；任何 `rtl/` 文件变化或恢复
失败均判失败。三类证据必须分栏，observer 不得称为 end-of-run formal D，alias SCA_D
不得冒充全部历史 guard。overall E4 还必须同时满足 48-stage 自然完成、barrier、
return receipt、SERVER_RESULT_GATE 和 focused identity。

## 7. 最小组合动态合同

规则 ID：`CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001`

在重跑 node0001 全量 E4 前，默认只物化和运行一个
`single-occurrence-two-stage` 诊断合同。它必须由已闭合的同一 node0001 最终 JSON
拓扑重新派生，而不是裁剪旧服务器包，并同时覆盖：

1. 一个逻辑 HWC8 occurrence、严格相邻的 `guard → round_saturate` 两个 stage；允许为
   适配 stock TB 的固定完成观察，把同一逻辑 occurrence 同步部署到最小必要物理 slice
   集，但必须单列逻辑 occurrence 数和物理 slice instance 数；
2. 负值、`-1`、零、正值、exact half-even、低端和高端饱和，以及 8 个物理 lane
   multiplier；
3. guard FP32 与 final UINT8 的全部 accepted MSE4 write 地址、strobe、数据和数量；
4. stage0 D 与 stage1 A 同址、stage1 A 外部 preload 为零，以及 stage0 完成后才允许
   stage1 启动的同 mask barrier；
5. `Repeat_Num=2`、首次 start 前仅一次 RequantGuard load、两个 stage 均自然完成。

该合同只用于定位首个动态分歧，不计作完整 node0001 E4/E5。默认不得同时生成或运行
`guard-only`、`round-only`、额外 `alias/lifetime` 原子项；只有组合合同出现相应首分歧
后才启用唯一对应项：

- guard 写入或 guard 完成前首分歧 → `guard-only`；
- guard 完成而 round 未启动，或 D→A 可见性/同址交接首分歧 → `alias/lifetime`；
- round 已启动而 final write/round 数值首分歧 → `round-only`。

组合合同通过时三类附加原子项保持禁用。若两级写入都正确但最终完成条件失败，先保留
组合合同的 completion 证据，不得用无关原子项扩大服务器试跑。

规则 ID：`CDA-REQUANT-GUARD-DIAGNOSTIC-EVIDENCE-BOUNDARY-001`

`guard-only` 只有在仿真已经启动并产生绑定 slice/stage 的 checkpoint 后，才能推进
`B_REQUANT_GUARD_DYNAMIC_DATA_PATH`。如果失败发生在 package、observer 安装或编译阶段，
则 0 条 A-read/Buffer/GA/SFU/MSE4 checkpoint 只表示“未观测”，不能表示数据为零、
握手缺失或硬件未执行。此类失败不改变组合合同已经给出的首分歧，也不启用
`round-only` 或 `alias-lifetime`。

后继仍须是同一个 `guard-only` 语义合同：JSON、mapping、bitstream、execplan、输入、
SFU payload、golden 和预期写保持冻结；只允许以全新身份修复服务器基础设施或只读
observer。服务器编译通过后，才按
`MSE0 request/rdata → Buffer → GA raw/convert → SFU input/ALU/output →
MSE4 request/wdata → formal D`
的顺序裁决最早真实数据分歧。

规则 ID：`CDA-REQUANT-ATOMIC-STOCK-TB-MASK-COMPAT-001`

原子合同的 active mask 必须覆盖 stock TB 完成观察实际采样的全部物理 slice。当前活动
TB 对每个 `Repeat_Num` 固定等待 slice0 的 `Start_Comp` 和 slice1 的
`slice_cmpt_finish`，不是 mask-aware；因此当前可封包的最小合同必须启用
`slice0+slice1`，同时保持：

- `Repeat_Num=2` 仍只表示 guard、round 两个 stage，不因物理 slice 数增加而翻倍；
- 两个 slice 使用相同 address-bound JSON 拓扑，但输入、guard golden、final golden
  和 MSE4 accepted write 必须按 slice 独立物化和核对；
- stage barrier 必须覆盖同一 active mask：两个 slice 的 guard 都完成后才允许 round
  启动；
- 单 slice v1 只保留为本地诊断历史，分类为
  `STOCK_TB_COMPLETION_MASK_INCOMPATIBLE`，未封包、未运行，不计动态失败；
- 未经用户另行授权，不得通过修改 TB、修改 `rtl/**`、force/deposit completion、
  缩短 timeout 或驱动式 observer 绕过此门。

规则 ID：`CDA-REQUANT-GUARD-CHECKPOINT-ROUTING-001`

`guard-only` 首分歧必须区分“解析错误”“未观测”“部分覆盖”和“已观测为零”：

- 只有同一边界 `raw != parsed` 时才能分类为 parser divergence；
- `raw=parsed=0` 表示 `UNOBSERVED_NOT_ZERO`，不得据此声称该边界 valid 为零、数据为零
  或硬件未执行；
- `0 < parsed < expected` 表示 `PARTIAL_COVERAGE`，不得把已采样子集外推为完整事务；
- 只有存在真实 payload 记录且全部为零时，才能分类为 `*_PAYLOAD_ALL_ZERO`；
- MSE4 request 与 write-data 是解耦握手，必须按
  `CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001` 独立采集和归一化地址；不得用同周期
  request、固定通道或易失单槽状态为后续 write-data 补地址。

validator 的顺序固定为：先核 `raw↔parsed`，再核 coverage，最后核 payload。缺少中间
checkpoint 时，最早可报告的只是不确定区间
`LAST_PROVEN_GOOD → FIRST_UNOBSERVED_BOUNDARY`；后面的零写和正式零回读可以证明最终
结果错误，但不能越过未观测区间指定唯一 CONFIG 或 RTL 根因。

规则 ID：`CDA-REQUANT-GUARD-V4-DYNAMIC-EVIDENCE-001`

`rq_node0001_guardonly_stock_v4` 的正式回传固定为以下动态证据，不得沿用包内旧
`GUARD_OBSERVER_COVERAGE_OR_PARSE_DIVERGENCE` 路由：

- return ZIP：55,405 bytes，SHA256
  `248eeed826d62fb343289b370fa20dbf6bc2d90f3d4aeba315160d5d30628077`；
- compile/sim/run 均为 0；一个 guard stage 在 slice0+1 上自然 start/finish，
  同 mask fence、单次 RequantGuard load、return receipt 和 stock-RTL identity 通过；
- MSE0 read-data 为 16/16 非零，MSE0→Buffer 为 16/16 非零；GA_RAW 为 64/64，
  其中 62 条非零、2 条是输入中预期的零；
- guard JSON 的 inport0 `int32tofp32=true`，最终 parsed bitstream 的 GA inport0 也声明
  conversion enabled；这只证明静态配置意图，不证明运行期 RTL 已消费或传播该位；
- GA_CONVERT、SFU_INPUT、SFU_ALU、SFU_OUTPUT 均为 `raw=parsed=0`，因此是未观测，
  不是“已观测为零”；最后可信非零边界为 GA_RAW；
- MSE4 observer 只覆盖 8/16 条 write-data，已采 8 条均为零，且存在解耦握手配对
  错误；该 observer 不能证明完整写事务数量或地址；
- 两份正式 D 各 8 行，共 16 行，全部为零且不来自 preload，均与 guard golden 不同；
  因此 guard 数值输出失败是确定事实。

权威首分歧分类为
`GA_CONVERT_UNOBSERVED_AFTER_GA_RAW`，责任区间为
`GA inport conversion/config consumption → odd-PE SFU selection/valid → SFU LUT/ALU
→ normal outbuffer`。在直接运行期信号闭合前，责任保持
`CONFIG_CONSUMPTION | RTL_CONTROL | OBSERVER_EVIDENCE` 未裁决；不得提前写成 JSON
错误或 RTL 缺陷。该原子测试不计 node0001 E4/E5，保持
`candidate_release=false`、`NO_DYNAMIC_BASELINE`、
`B_REQUANT_GUARD_DYNAMIC_DATA_PATH` 和 `B_REQUANT_SERVER_E4_E5`。

下一轮仍只能使用冻结语义的 guard-only 全新身份。只读 observer 至少覆盖：

1. GA inport 的运行期 conversion 配置位、配置译码结果、input-buffer valid/data、
   converter input valid/data、converter registered output valid/data 和最终 out
   tag/data/ready；
2. 奇数列 PE 的已选 input valid/data、SFU input valid、compute enable、LUT 地址及
   slope/intercept、ALU/output valid/data、normal outbuffer write valid/data；
3. MSE4 request 与 write-data 的独立握手和独立计数，并用稳定事务 ID 或 FIFO
   事后关联，不得丢弃无法同周期配对的 write-data。

规则 ID：`CDA-REQUANT-DIRECTSIG-V1-DYNAMIC-EVIDENCE-001`

`rq_node0001_guardonly_directsig_stock_v1` 的正式回传修正了 v4 的首分歧上界：

- return ZIP 为 62,590 bytes，SHA256
  `9c2c83a81135aba64f8f17e53c6c4f708d488eed2f6041fb064a65a4395596d5`；
  来源 package SHA256 为
  `715a4b8abdd45b3251c464eba4359cea8af740c75b238a68d956f949524a1939`；
- 内部 `RETURN_RECEIPT` 的 32 项 payload exact-set、size、SHA 和 allowlist 全部通过；
  compile/sim/run 均为 0，一个 guard stage 在 slice0+1 上自然 start/finish，stock RTL
  和事务式 observer 身份稳定；
- MSE0 read-data 与 MSE0→Buffer 均为 16/16 非零；`GA_CONVERT_REGISTERED`、
  `GA_INPORT_FINAL`、`PE_SELECTED_INPUT` 均为 64/64，其中 62 条非零、2 条为输入中
  预期的零。int32→fp32 转换值逐 bit 符合运行输入；
- `GA_INPORT_CONFIG`、`GA_INPORT_IB`、`GA_CONVERT_INPUT` 的零计数已被上述更下游
  正证据支配，只能记为 observer-only gap；不得继续使用包内
  `GA_INPORT_CONFIG_UNOBSERVED_AFTER_MSE0_TO_BUFFER`；
- `SFU_INPUT`、`SFU_COMPUTE`、`SFU_LUT`、`SFU_ALU`、`SFU_OUTPUT` 和
  `NORMAL_OUTBUFFER_WRITE` 均未观测；其后 MSE4 request/write-data 为 16/16，
  16 条 write-data 全零，两份正式 guard D 各 8 行且全部为零、均不来自 preload，
  因而最终 guard 数值失败确定；
- `PE_SELECTED_INPUT` 实际采样条件是 PE inbuffer input-side enable/data，不得扩写为
  `ga_pe_inbuffer_valid_bit[0]` 已置位或 post-register accepted。

权威分类为
`SFU_INPUT_UNOBSERVED_AFTER_PE_SELECTED_INPUT_BEFORE_MSE4_WDATA_ALL_ZERO`，
证据状态为 `BOUNDED_UNOBSERVED_INTERVAL_WITH_DOWNSTREAM_ZERO`。责任仍为
`CONFIG_CONSUMPTION | RTL_CONTROL | OBSERVER_EVIDENCE`，但待查范围已缩小到
PE inbuffer 接收/匹配、运行期 SFU opcode/enable、LUT 初始化完成与 normal outbuffer
之间；不得返回 GA conversion，也不得启用 round-only、alias/lifetime 或完整 E4。

下一轮保持 JSON、mapping、bitstream、execplan、输入、RequantGuard、golden 全部冻结，
只用全新身份增加最小只读 readiness 证据：

1. 奇数 PE 的运行期 `ga_pe_alu_opcode`、`ga_pe_sfu_valid`、
   `ga_pe_sfu_compute_en`；
2. 每个 GA group 的 `ga_pe_sfu_compute_valid`，以及 SFU LoadConfig 期间
   LUT 初始化 enable/address/end-address 和 `slice_rst`；
3. PE inbuffer 寄存后的 valid、matched/output-valid 与 SFU preprocess pipeline0
   enable/valid。

本结果不计 node0001 E4/E5，保持 `candidate_release=false`、
`NO_DYNAMIC_BASELINE`、`B_REQUANT_GUARD_DYNAMIC_DATA_PATH` 和
`B_REQUANT_SERVER_E4_E5`。

focused identity 至少新增
`GA_Inport.sv`、`GA_Inport_Group_Config.sv`、`GA_Inport_Group.sv`、
`GA_Inport_Connect.sv`、`GA_PE_Group_Interconnect.sv`、`GA_SFU_LUT.sv`、
`GA_SFU_PE.sv`、`GA_SFU_PE_Preprocess.sv`、`GA_SFU_PE_Postprocess.sv`、
`Binary_Search_Tree.sv`、`Comparator.sv` 以及 `GA_Outport/*.sv`。JSON、mapping、
bitstream、execplan、输入、SFU payload、golden 和预期写均保持冻结；不得启用
round-only、alias/lifetime 或完整 E4。

规则 ID：`CDA-REQUANT-SFU-READY-V1-DYNAMIC-EVIDENCE-001`

`rq_node0001_guardonly_sfu_ready_stock_v1` 将 direct-signal 结果进一步收窄，但包内
`PE_REGISTER_MATCH` 首分歧被下游寄存正证据推翻：

- return ZIP 为 65,566 bytes，SHA256
  `a9c9206fc3f04c77172242cd8356ffb9a3a367f9b5922fda540d528438832ab9`；
  来源 package SHA256 为
  `8cb224163271e0ed9166831bf434c88ce10e1f76ed78a42344724f8b5126c2ac`；
- 内部 `RETURN_RECEIPT` 的 32 项 payload exact-set、size、SHA 和 allowlist 全部
  通过；compile/sim/run 均为 0，一个 guard stage 在 slice0+1 上自然 start/finish，
  同 mask fence、单次 RequantGuard load、stock RTL 和 observer 身份通过；
- `PE_SELECTED_INPUT` 为 64/64，其中 62 条非零、2 条为输入中预期的零；
- 奇数 PE 运行期 opcode 精确出现 `0x18` 32 次，`sfu_valid` 断言 32 次，
  `compute_en` 断言 16 次；LUT 初始化 enable 断言 198 次、end-address 2 次，
  group compute-valid 2 次，说明 opcode 消费和 LUT readiness 已闭合；
- `SFU_PREPROCESS0.enable` 断言 144 次、寄存后的 valid 断言 64 次。
  `GA_PE_Inbuffer.sv` 在该 enable 下执行
  `sfu_preprocess_pipeline0_valid_bit <= ib_output_valid_bit`，因此这 64 条下游
  valid 是捕获边沿 `ib_output_valid_bit` 为真的正证据；
- `PE_POST_REGISTER` 只有 cycle 1 的 16 条全零 change-only 记录，不能覆盖上述
  下游寄存 witness，只能按
  `CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001` 记为采样盲点；
- `SFU_PREPROCESS0.data=0x3` 是 enable/valid 拼接的状态摘要，不是数值 payload；
  本轮仍未观测 preprocess 输入/输出、LUT 系数选择、SFU ALU/result 或 normal
  outbuffer 的实际数值；
- MSE4 request/write-data 为 16/16，16 条 write-data 全零；两份正式 guard D 各
  8 行且全部为零、均未 preload，与 guard golden 不同。

权威分类更新为
`SFU_PREPROCESS0_VALID_PROVEN__NUMERIC_PIPELINE_UNOBSERVED__MSE4_ZERO`，最后可信边界为
`SFU_PREPROCESS0_VALID`，首个未观测数值区间为
`SFU preprocess0 payload → breakpoint/coeff selection → SFU ALU/postprocess →
normal outbuffer`，下游坏边界为 `MSE4_WDATA/formal D all zero`。责任仍保持
`CONFIG_CONSUMPTION | RTL_CONTROL | OBSERVER_EVIDENCE` 未裁决；不得退回 GA conversion，
也不得启用 round-only、alias/lifetime 或完整 E4。

下一轮只允许冻结同一 guard-only 语义并增加 capture-edge-safe 的真实 payload
checkpoint：`ga_pe_sfu_inport2pre_data`、preprocess/BST 输出与 coeff address/data、
SFU ALU input/result/tag、postprocess result、normal outbuffer accepted write 和
outport。可并行运行一个严格隔离的可信原生
`decode_silu_fp16N_fp32N.json` SFU control，用于验证相同 stock RTL 的
SFU/normal-outbuffer 路径和 observer 边界；control 不得改写 Requant 资产，也不计
node0001 E4/E5 或证明 guard 数值正确。

规则 ID：`CDA-REQUANT-SFU-NUMERIC-V1-DYNAMIC-EVIDENCE-001`

`rq_node0001_guardonly_sfu_numeric_stock_v1` 将最后可信数值边界推进到 BST 数据与
系数地址，但包内自动路由把 level sample 误当 transaction event，须由离线逐事务复核
取代：

- return ZIP 为 74,933 bytes，SHA256
  `a1d15ef3b5a1c426eec92e8fd7b1888a81b29e8825cc9a3c753d0809e947bbad`；
  外部 sidecar 缺失，故外层交付门不完整；内部 `RETURN_RECEIPT` 的 32 项 payload
  exact-set、size、SHA 与 allowlist 全部通过；
- 来源 package ZIP 为 66,563 bytes，SHA256
  `8e96d1bbd6e0379b8d33fca251b27bbc40bb32fc56d82418a3ae85e0515e1a1b`；
  返回 manifest SHA256
  `d4b7ccf7ca24f0c4a940fb863ada3dc5c367797f71dfa04822aba400adbdf4ae`
  与本地来源逐字节一致；
- compile/sim/run 均为 0；一个 guard stage 在 slice0+1 上自然 start/finish，同 mask
  fence、单次 RequantGuard load、stock RTL、focused RTL、support files 与 observer
  restore 身份均通过；
- `PE_SELECTED_INPUT` 为 64/64，其中 62 条非零、2 条为输入中预期的零；
- 离线按每个 PE 的捕获周期加三拍配对后，64/64 条 BST data 与 selected input
  逐 bit 一致；符号位为 1 时 coeff address 精确为 `0x00`，否则精确为 `0x41`，
  共 64/64 无误。因此最后可信数值边界更新为
  `SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT`；
- 包内 BST 日志共有 3,888 条，其中 3,488 条为可解析十六进制、400 条含 X/Z；
  每个物理 PE 被持续为高的
  `pipeline5_enable && comparator_valid_5` 重复采样 243 个周期。该计数不表示
  3,888 个事务，`raw != parsed` 也不是 parser divergence，而是
  `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001` 所定义的 observer 事件限定错误；
- 本轮未取得实际 slope/intercept SRAM 输出、SFU ALU 捕获输入/tag/result、
  postprocess 结果或 normal outbuffer accepted-write 的逐事务证据；
- normal outport 已接受 64/64 个有效 tag，但 payload 全零；MSE4 request/write-data
  为 16/16 且 write-data 全零；两份未预置的正式 guard D 各 8 行且全部为零，与
  guard golden 不同。此前 normal-write 零计数被这组下游 accepted 证据反证为
  observer 采样盲点。

权威分类为
`SFU_BST_DATA_AND_COEFF_ADDR_PROVEN__COEFF_TO_ALU_UNOBSERVED__DOWNSTREAM_ZERO`。
最后可信边界是 BST data/address；首个未观测区间是
`selected coefficient SRAM output → ALU capture/tag/result → postprocess →
normal outbuffer write`；下游坏边界是
`NORMAL_OUTPORT_ACCEPTED_64_ALL_ZERO → MSE4_WDATA_16_ALL_ZERO → formal D all zero`。
责任继续保持 `CONFIG_SEMANTICS | RTL_CONTROL | OBSERVER_EVIDENCE` 正交未裁决；
不得把自动 parser route 当根因，不得启用 round-only、alias/lifetime 或完整 E4。

唯一后继 Requant 探针必须冻结当前 guard-only JSON、mapping、bitstream、execplan、
输入、RequantGuard、golden 和预期写，并以全新 package/install/run/return 身份：

1. 对 64 个真实事务使用 capture/handshake 或 post-NBA/`$strobe`/shadow event，
   逐项记录 coeff address、实际 slope/intercept SRAM 输出、pre2alu data、
   ALU pipeline0 接受的 tag/data0/data1/data2、ALU result tag/data、postprocess result
   与实际 normal-mode outbuffer write tag/data；
2. 继续保留 64 条 normal outport accepted、16 条 MSE4 write-data 和两份正式 D，
   并按公共规则分栏 raw/qualified/parseable/XZ/duplicate 计数；
3. 若地址正确而 slope/intercept 错，路由到 SFU LUT load/read selection；若系数和输入
   正确而 ALU result 错，路由到 ALU/RTL；若 ALU result 正确而 postprocess/outbuffer
   错，路由到 postprocess/outbuffer；若 outbuffer 正确而 outport/MSE4 错，路由到
   downstream transport；
4. 不修改功能 RTL 或 TB driver；只读 observer 只能安装到服务器命令显式传入的唯一
   `NDP_copyXX` 根目录，并满足 `CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001`。

独立原生 SiLU control 仍可作为并行控制项，但不能代替上述 Requant 逐事务边界，也不计
node0001 E4/E5。当前仍为 `candidate_release=false`，保留
`B_REQUANT_GUARD_DYNAMIC_DATA_PATH` 与 `B_REQUANT_SERVER_E4_E5`。

规则 ID：`CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001`

`decode_silu_fp16N_fp32N_control_stock_v1` 已证明共同 SFU 数值与 normal-outbuffer 路径
能够在同一 stock RTL 上正确工作，但其独立 D 地址覆盖合同失败，二者必须分栏裁决：

- return ZIP 为 57,030 bytes，SHA256
  `182d3dbb160aac768cd37d634cc2ba34584a8524df4cb4983df3cc6691e0f246`；
  外部 sidecar 缺失；内部 23/23 payload exact-set、size、SHA 和 allowlist 通过；
- 来源 package ZIP 为 47,209 bytes，SHA256
  `3cbabba52e414f38ec33a2e234972fe3455655a6669163e5765d4c1141a62c53`，
  returned manifest SHA256
  `4eea577c1227d9a6bd9f4a7ffb5297e22ab667219e9f4b70e79cb77231017ae5`
  与本地一致；compile/sim/run 均为 0，单 stage 自然完成，stock RTL、focused RTL 和
  observer restore 身份通过；
- 每片真实事务数是 8 个 SFU PE×2 个输入=16，而不是包内自动门误设的 32；两片合计
  preprocess capture、coeff capture、ALU input/result、postprocess、
  normal outbuffer input/commit 和 normal outport 均为 32/32；
- 四个区分案例逐 bit 正确：
  `-1 → slope/intercept 3dad0980/be3ceb13 → be89b7ea`，
  `0 → 3f000000/397ff6ab → 397ff6ab`，
  `-4 → bd5f3921/be947a3d → bd9376b2`，
  `+4 → 3f86950b/be8e34b8 → 407b637f`；MSE4 16/16 write-data payload 同样正确；
- BST 的 1,936 条 raw/sample 每片仍是 level qualifier 重复采样，不是 1,936 个事务，
  按 `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001` 排除；
- 每片正式 D 的 8 行中仅前 2 行为 binary-known，且均为最后一个 occurrence 的正确
  值；后 6 行为全 X，较早 occurrence 不再驻留。包内把这种情况压成
  `line_count=0/invalid text` 不足以表达证据，权威状态是 D occurrence/address
  coverage alias 或未覆盖；尚未仅凭本回传裁决具体 LC/stream 字段。

控制项权威分类为
`SHARED_SFU_NUMERIC_NORMAL_OUTBUFFER_MSE4_PAYLOAD_PASS__D_OCCURRENCE_ADDRESS_COVERAGE_FAIL`。
最后可信边界是 `MSE4_WDATA_16_OF_16_BIT_EXACT`，首分歧区间是
`MSE4 accepted address/occurrence carrier → final D row residency/readback`。
该正证据排除“共同 SFU/normal-outbuffer 在 stock RTL 上普遍失效”，但不能证明
RequantGuard 的系数表、opcode、tag 或配置消费正确，也不计 node0001 E4/E5。

后续生成原子 control 时，checkpoint 预期数必须从
`active physical PE × accepted input occurrence` 推导；SCA_D 行数、golden 和输出地址
覆盖必须从最终 LC/stream/buffer 的逐 occurrence 唯一 D row 计划共同派生，不能从输入
字节数或 observer write-data 总数单独猜测。本 control 已完成共同路径使命，不再生成
SiLU control 重跑；下一项仍是冻结 Requant guard-only 语义的 event-qualified
coeff→ALU→outbuffer 窄探针。
