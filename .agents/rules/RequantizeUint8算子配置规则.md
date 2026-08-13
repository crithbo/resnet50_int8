# RequantizeUint8 算子配置规则

最后更新：2026-08-11（稳定 scalar-phase / exact-tail 合同）

本文件只拥有 `INT32 accumulator → UINT8` Requantize 的 qparam、逐 occurrence
multiplier 供给、scalar-phase schedule、两阶段边界和动态放行门。公共 provenance、字段
含义、complete-JSON、服务器包与证据等级分别由公共规则拥有；当前 54-stage 完成度、
候选身份和服务器结果只看 `.agents/plan.md` 与对应 task record。

## 1. 权威输入与复用边界

每个 fresh instance 必须绑定 current lowering 中的 exact stage ID、typed request、ONNX
initializer、正式 accumulator/golden 与 current source identity。原生 JSON 只授权已证明的
字段拓扑和 changed-surface applicability，不授权旧 shape、地址、常量或 schedule。

允许复用的结构原语包括一条 FP32 scalar transaction、per-channel multiplier 的
`mode=keep` 输入拓扑、normal outbuffer 和显式 scratch。禁止复用近似激活、历史 guard、
历史版本字段值或 host 预计算的 scaled/rounded/saturated/final tensor。

## 2. 精确 qparam 与数值顺序

规则 ID：`CDA-REQUANT-QPARAM-001`

对每个输出 channel `c`：

```text
multiplier[c] = binary32(binary32(x_scale * w_scale[c]) / y_scale)
scaled        = binary32(binary32(acc) * multiplier[c])
rounded       = round_to_nearest_even(scaled)
q             = saturate_uint8(rounded + int32(y_zero_point))
```

输入 qparam、multiplier 与 zero-point 必须保持 typed binary identity。每个 multiplier
都要绑定 channel axis 和最终 consumer；禁止只保留首元素、十进制近似、min/max 或 hash
摘要。sequential multiply 与 independent RNE 不得融合成改变舍入点的 FMA。

规则 ID：`CDA-REQUANT-FAMILY-QPARAM-CLASSIFICATION-001`

全族审计必须逐 exact stage 从 current lowering 重算 qparam，并按 shape、multiplier axis、
zero-point 类别和 schedule signature 分类。分类只减少重复证明，不能把一个代表实例的
地址、layout、lifetime 或 E4/E5 外推到同类其它实例。

规则 ID：`CDA-REQUANT-ZP-TIE-PARITY-001`

当 `y_zero_point != 0` 时，不得把
`RNE(scaled) + zero_point` 默认改写为 `RNE(scaled + zero_point)`；特别是 odd
zero-point 会改变 exact-half tie 的奇偶基准。正负控必须包含 exact-half、0/255 饱和、
负值、`-1`、零和正值。

## 3. current signed INT32→FP32 primitive

规则 ID：`CDA-REQUANT-GA-INT32-TO-FP32-CURRENT-IDENTITY-001`

原生 `GA_Inport.int32tofp32` 的 signed INT32→IEEE754 binary32 RNE 只在下列 exact
identity 上批准：

```text
repo          = xlsjdjdk/Trassic2.0_RTL
HEAD/master   = 0ccae916ef61904a64d6cf8ec1d1931b45e428d8
fix commit    = c81807554b5e39c040aeae39ffe30aa522f5f6ab
source blob   = 59507fc7c2e7f156f46e1ee3d2d512465e1f1873
source SHA256 = 2d27c3bc339c58c8335ae79a6341bec54d27694801c036a0af8099e29b2a18cb
source bytes  = 26030
```

该身份已覆盖完整 `2^32` INT32 输入域的 binary32 RNE；commit/blob/source/consumer
任一漂移都必须 fail closed 并重新证明。本门只关闭 signed ingress primitive，不关闭
multiplier、独立 RNE、zero-point、饱和、地址、lifetime、terminal 或 E3–E5。

## 4. per-channel multiplier 物理供给

规则 ID：`CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001`

multiplier inventory 与物理 supply 是两个独立门。每个 materialized occurrence 必须同时
绑定：

1. exact FP32 payload bits 与 channel-axis index；
2. sample/spatial/channel occurrence、目标 PE input 与 capture 时序；
3. payload address、bank/row/column 和 broadcast/serialization 次序；
4. producer/load 到 consumer capture 的 lifetime、coverage 与 release；
5. final JSON 到实际 consumer 方程的 reverse receipt。

只有 target axis 上全部值 bit-equal 且 consumer/lifetime 同时闭合时，才允许 fixed
constant broadcast；否则必须逐 channel/occurrence 运输。min/max、元素数、registry 条目或
placeholder handler 不能替代 supply 证明。

规则 ID：`CDA-REQUANT-SCALAR-PHASE-SERIALIZATION-001`

53 个 per-channel stage 使用 current fields 可表达的确定性顺序：

```text
for sample:
  for channel_shard:
    for phase p in 0..7:
      for spatial n:
        consume channel = 8 * channel_shard + p on PE00/lane0
```

字段合同：

```text
B_addr = baseB + 4 * (8 * channel_shard + p)
A_addr = base_sample + 4 * ((channel_shard * N + n) * 8 + p)
D_addr = destination with the same logical (sample, shard, n, p)
B idx_size = [3, 0, null]
phase stride = 4 bytes
shard stride = 32 bytes
buf_spatial_size = 4
buf_spatial_stride = [0, 1, 2, 3]
active lane/PE = lane0 / PE00
PE00 input1 = src_id 0, mode keep through N-inner, release before phase advance
```

one-scalar MatMul-derived stage may use the exact PE constant path only after scalar bits、consumer
和 lifetime 绑定。负控至少覆盖 32B parallel-B、错误 idx_size、错误 phase stride、非
lane0 mask、premature keep release、payload lane permutation 和非标量 fixed constant。

## 5. 两阶段与跨阶段边界

规则 ID：`CDA-REQUANT-TWO-STAGE-001`

每个 occurrence 必须显式实现：

```text
stage0: signed INT32 ingress -> binary32 multiply -> FP32 scratch write
barrier: producer completion + accepted writes + no outstanding transfer
stage1: raw FP32 scratch -> independent RNE -> add zero-point -> UINT8 saturation
```

stage0 与 stage1 必须使用同址、同 dtype/byte-span 解释和明确 lifetime；stage1 A 不得由
外部 preload 或 host replay 提供。两级均走 normal outbuffer，禁止用 reduction/transout
冒充 clamp，禁止猜测不存在的整数 opcode。

规则 ID：`CDA-REQUANT-MATERIALIZED-ROUNDTRIP-001`

本地 complete-JSON gate 必须逐 exact stage 证明：strict JSON 无 unresolved leaf；所有
phase 覆盖且 channel 恰好一次；transaction、bank/column、tag、last、地址和 byte coverage
守恒；跨阶段 boundary 全部 resolved；两次隔离构建语义产物一致；最终配置绑定执行对正式
输入逐元素匹配独立 golden。mapper/encoder 若遍历无序集合，必须同时固定 mapper seed 与
`PYTHONHASHSEED`，并由独立进程双跑证明。

规则 ID：`CDA-REQUANT-NATIVE-ADAPTER-BOUNDARY-001`

隔离 native adapter 必须保留 5PE topology、scalar-B occurrence supply、MatMul exact
constant path 和输出 binding，不得修改 active `ndp-sim`、RTL 或 ISA。local mapper/encoder
通过只证明 backend acceptance，不等于 production execplan/SCA、natural terminal、formal
D 或 E3–E5。

## 6. 配置绑定 simulator 与动态发布

规则 ID：`CDA-REQUANT-CONFIG-BOUND-SIMULATOR-001`

simulator 必须消费最终 JSON、phase program、地址/lifetime 与 exact constants，从实际
opcode、conversion flag、input binding 和 output layout 执行，而不是只读取 typed request
重算公式。报告分列 golden↔simulator、golden↔hardware、simulator↔hardware；缺正式硬件
D 时后两项必须为 `EVIDENCE_MISSING`。

规则 ID：`CDA-REQUANT-E4-E5-001`

本地 strict JSON、mapper/encoder 或 simulator 通过均不能授予 candidate release。E4
必须覆盖全部目标 occurrence、phase、跨阶段 barrier、自然完成、正式 UINT8 D、独立
golden、return receipt 与身份门；E5 必须使用全新运行身份重验。当前开闭状态只记录在
plan/task record。

规则 ID：`CDA-REQUANT-TRANSIENT-INTERMEDIATE-EVIDENCE-001`

若 stage0 scratch 在 phase/stage 间复用，run 末 SCA_D 只能证明最后驻留值。历史
occurrence 必须由 actual accepted write 的 qualified live record 或等价持久证据覆盖；
final UINT8 仍必须由正式 D 覆盖。中间 observer、last-resident D 与 final formal D 必须
分栏，任何一类不得冒充另一类。
