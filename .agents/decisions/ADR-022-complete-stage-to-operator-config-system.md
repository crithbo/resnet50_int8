# ADR-022：建立完整 stage→算子 JSON 配置体系

日期：2026-07-23

状态：accepted；实现覆盖全部 stage 的规则和失败边界，不代表全部 stage 已可发射或已通过硬件。

## 1. 决策

以 `contracts/resnet50_r5_lowering_bundle.json` 中的 133 个 typed request 为唯一 stage
输入，以 `contracts/operator_config/operator_config_authority_v1.json` 判定参考配置
正确性，再生成统一的机器合同
`contracts/operator_config/stage_config_system_v1.json`。

每个 stage 必须依次经过：

```text
typed request
→ 算子族规则
→ logical ScheduleIR
→ slice/wave/buffer 物理调度
→ 数值 kernel 与 typed constant
→ 跨 stage CONFIG 状态
→ strict address-unbound JSON
→ address/mapping/bitstream/execplan/SCA
→ independent golden + server E4/E5
```

系统覆盖与 emitter 放行分开统计。只要任一语义层未闭合，stage 仍有完整计划，但
emitter 必须 fail closed。

## 2. 字段所有权

顶层 JSON 模块必须有单一语义所有者：

- `CONFIG`：有序 stage 的 update/reuse/disable 状态机；
- `dram_loop_configs`、`processing_element`：逻辑循环、依赖和 terminal tag；
- `stream_engine`：物理布局、padding/tailing/keep、ping-pong，地址后绑定；
- `scratchpad`：buffer 生命周期和生产者/消费者；
- `special_array`：SA dtype、非对称端口布局、bias/psum；
- `general_array`：typed arithmetic、转换和常量放置；
- `n2n`：跨 slice 通信、归约及 completion。

任何字段不得仅从文件名、相邻样例或 encoder silent default 猜测。

## 3. 来源与当前覆盖

参考正确性沿用 ADR-021：固定上游原生且未改变的 53 份配置和根仓 12 份用户参考配置
可用于规则闭合；两份项目后加 `node0004*` 只能作为诊断证据。

当前机器结果：

- 133/133 stage 均有计划，覆盖 10 种 hardware stage；
- shape 变体：Conv 20、Requant 20、Add 5，其余按实际 typed geometry 登记；
- address-unbound candidate JSON ready：2（精确 MaxPool、精确 GAP）；
- zero-copy binding ready：1（View）；
- 仍阻塞：130；
- formal release：0。

因此“完整”指输入、规则层、字段所有权、shape 变体、blocker 和后续验证链无空洞；
不等于 133 份 JSON 已生成。

## 4. GAP 精确闭环

固定上游 `ndp-sim/jsons/avgpool_config_2048_7_7.json` 与
`hwop-0071-00` 是精确 shape 对应关系。合同
`contracts/operator_config/gap_sum_zero_padding_contract_v1.json` 已绑定：

- 输入 `[16,2048,7,7] uint8`、输出 `[16,2048,1,1] int32`；
- `x_zero_point=0`、空间元素数 49；
- 8 个 GA lane 的 `int32_sum`；
- shared stream RTL 的 padding 替换语义；
- padding byte 取加法单位元 0；
- strict 物化配置及其源/目标哈希。

该合同直接绑定不可变 typed stage，而不绑定 lowering bundle，避免
`lowering→overlay→GAP contract→lowering` 的哈希循环。

后续 ADR-023 的 DeepSeek reduction 规则已证明：`x_zero_point=0` 可编译期特化，
每个活动 slice 接收完整 sample，无跨 slice reduction，且 terminal 链到
`last_index=0`。因此上述三个本地 blocker 已解除并开放第二个 address-unbound
candidate；地址/mapping/execplan/SCA 与 E4/E5 仍未解除。

## 5. 实施顺序

1. GA reduction：为 GAP strict template 建立 mapping/execplan、跨 slice completion
   和 sum→requant CONFIG handoff；
2. GA affine/requant：先闭合 Requant 的完整 batch/wave dispatch，再复用到
   Add、Quant、Dequant 和 AverageRequant；
3. SA INT8 accumulate：从授权上游模板、RTL、register map 独立闭合 Conv/MatMul
   的端口方向、bias/psum、完整波次与尾块，再反向审查未授权 node0004；
4. 每族先做非对称微测，取得 E4 和重复 E5 后才推广 shape。

## 6. 声明边界

授权参考模板可闭合其精确配置的参考语义，但不能自动批准派生 shape、地址、常量、
跨 stage 状态或服务器结果。strict JSON、candidate emitter、formal target、E4 和 E5
必须分别声明；任何一层不能替代后一层。
