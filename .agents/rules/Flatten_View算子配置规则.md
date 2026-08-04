# Flatten / View 算子配置规则

最后更新：2026-07-27

本文件只覆盖不改变元素顺序和字节表示的 metadata-only Flatten/View。公共 provenance、
物化字段所有权、配置绕行和证据等级由 `算子配置规则.md` 拥有。若目标实例需要 copy、
transpose、relayout、dtype conversion 或硬件请求，本规则不授权继续生成，必须另建
专项合同。

当前代表实例：

```text
node0072 D: fp32[16,2048,1,1]
  -> node0073 Flatten(axis=1) / View
node0074 A: fp32[16,2048]
```

当前状态：`ENDPOINT_BINDING_PENDING`；独立 local E2 不适用，integrated target local
E2 仍为 false。

## 1. metadata-only 物化

规则 ID：`CDA-VIEW-METADATA-ONLY-001`

满足下列全部条件时，Flatten/View 必须物化为 execplan/planner metadata alias，不生成
算术 JSON、mapping、bitstream、硬件 instruction 或 memory request：

- dtype 和逐元素字节表示不变；
- 输入输出均为 C-contiguous；
- reshape 后线性元素顺序不变；
- 完整元素地址映射逐项相等；
- 无 copy、transpose、relayout、padding 或 tail 计算。

逻辑 tensor ID 可以不同；不得因此分配新的物理 storage。

## 2. 物理身份与地址证明

规则 ID：`CDA-VIEW-PHYSICAL-IDENTITY-001`

producer output、View input/output 与 consumer input 必须共享：

```text
storage_id
allocation_owner
allocation_base + byte_offset
byte_span
linear element order
```

shape 和 stride metadata 可按 reshape 改变，但 validator 必须枚举完整冻结实例，证明
每个 input index 与 output index 的最终 byte address 相同。node0073 的冻结实例要求
32,768/32,768 元素全部相等，span 为 131,072 bytes；输入 strides
`[8192,4,4,4]`，输出 strides `[8192,4]`。

View 不拥有 allocation，不得分配或释放；allocation owner 保持 producer activation
allocator。

## 3. endpoint coverage

规则 ID：`CDA-VIEW-ENDPOINT-COVERAGE-001`

View 没有自己的 write，因此不能用“零请求”宣称输出 coverage。integrated validator
必须消费最终 address-bound：

- producer write occurrence/address 方程及 unique written-byte set；
- consumer read occurrence/address 方程及 unique read-byte set；
- allocator plan、producer/consumer layout contract 和 execplan identity。

两端 covered-byte set 都必须等于 View 所需的完整 byte region，且 storage/base+offset/
span 一致。任一 endpoint 尚未最终物化时，integrated local E2 fail closed。

## 4. accepted-handshake lifetime

规则 ID：`CDA-VIEW-ACCEPTED-LIFETIME-001`

allocation 必须在 producer final write accepted 与 completion 后对 consumer 可见，
并保持到 consumer final input-data accepted 且不存在 pending/replayed read 后才释放。
若 final input-data accepted 不可观测，只允许保守延长到 consumer completion accepted；
该 fallback 只改变 lifetime，不得复制或预计算数据。

## 5. 声明边界

规则 ID：`CDA-VIEW-INTEGRATED-CLAIM-BOUNDARY-001`

metadata、完整元素地址映射和 lifetime 合同通过，只关闭 View 本族的 shape/order/no-op
不确定项。缺少 producer/consumer 最终地址、coverage、execplan/layout hash 或 allocator
plan 时，只能声明 `ENDPOINT_BINDING_PENDING`，不得声明
`CONFIG_ONLY_CORRECTNESS_BASELINE`、完整节点 local E2、E4 或 E5。

当前开放 blocker：

- `B_VIEW_PRODUCER_ALLOCATION`
- `B_VIEW_CONSUMER_ALLOCATION`
- `B_VIEW_BYTE_OFFSET_IDENTITY`
- `B_VIEW_BUFFER_LIFETIME`

权威机器合同：
`contracts/operator_config/flatten_node0073_physical_view_v1.json`。
