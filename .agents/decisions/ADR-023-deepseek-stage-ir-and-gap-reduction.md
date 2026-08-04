# ADR-023：以 DeepSeek StageIR 提炼 stage→JSON 规则并闭合精确 GAP

日期：2026-07-23

状态：accepted；只批准机器化规则和精确 GAP 本地候选，不批准跨 dtype 派生或 formal。

补充：执行所有权由后续 ADR-024 澄清。这里的三份合同是索引/审计/迁移边界，
不构成独立 graph parser、control-register generator 或 execplan pipeline。

## 1. 决策

固定上游授权正确的 DeepSeek 配置不再只作为文件级样例，而是建立三份可重建合同：

- `deepseek_stage_ir_crosswalk_v1.json`：47 份模板、87 个 graph、158 次 stage 出现、
  40 种 stage type 的 graph location/type/shape/source/slice→模板 SHA 交叉索引；
- `deepseek_reduction_rules_v1.json`：local/remote reduction、terminal 与 GAP 精确调度；
- `deepseek_primitive_rules_v1.json`：22 份 GA add/mul/mac 和 6 份 SA GEMM/GEMV 的
  local/ring/N2N 结构。

消费方必须验证合同与当前固定上游 blob 一致。项目后加 `node0004*` 不进入这些规则。

## 2. GAP 结论

RMSNorm graph 证明 remote sum 的选择条件是：前一个 local reduction 仍留下被多个
slice 分割的同一 reduction domain。ResNet `hwop-0071-00` 的归约轴只有 H/W；
每个活动 slice 接收一份完整 `[2048,7,7]` sample，精确配置一次写出
`256 × 32 = 8192` bytes，即 2048 个 int32 channel，所以不需要 remote sum。

`x_zero_point=0` 将 `sum(uint8(x)-xzp)` 编译期特化为普通 uint8→int32 sum，并同时
把 padding byte 绑定为加法单位元 0。严格配置 terminal 链到唯一可达的
`last_index=0`。因此精确 GAP 的 typed transport、centered sum、cross-slice 和
completion 本地 blocker 均关闭，允许生成 address-unbound candidate。

这不批准地址、mapping、bitstream、execplan、SCA、服务器 E4/E5 或 formal。

## 3. GA/SA/N2N 迁移边界

GA 模板可证明 opcode、active lane、broadcast/source 和 terminal 结构。SA local/ring
对可证明：核心 mode/dtype/outport 可保持，但 K 分块、LC/stream、SA `nbr_enable`
与 N2N 必须一起变化。ring 不是给 local JSON 添加一个字段。

上游模板以 FP16/FP32 为主，不能证明 ResNet INT8 Conv 的非对称 A/B 布局、
bias/psum 数值位置、量化 multiplier/rounding/saturation、尾块或跨 wave CONFIG。
JSON 只有 neighbor transport 字段，没有名为 psum 的数值语义字段；这些继续保留 blocker。

## 4. Strict schema 兼容性

授权正确模板与派生 target 的 strict schema 是两件事。当前发现：

- 一份 vector-add 在 write stream 保留四个原生不编码的 read-only 字段；
- 三份 prefill GEMM 使用 legacy `mem_idx_mode[2]=0` sentinel。

这些模板的精确上游证据仍有效，但不得放宽全局 strict schema，也不得静默规范化。
只有原生 encoder/RTL 等价合同可以授权 strict materialization 生成只读源之外的新副本。
