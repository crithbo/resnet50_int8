# ADR-002：ResNet INT8 Conv 16-slice拓扑裁决【已废止】

状态：已由ADR-007取代（superseded）；不得再作为当前目标或W4/W5输入
日期：2026-07-12

> 2026-07-13更新：操作者已确认目标硬件为28-slice，并采用ADR-007的七个4-slice小环主方案及28-slice大环比较候选。本文件只保留旧16-slice候选的历史背景；其中`w4_*16*` profile、`(owner+step)%16`和15次neighbor transfer均不是当前硬件合同。

## 待裁决事项

目标16-slice硬件上的Conv究竟采用哪一种slice所有权：

1. `w4_conv_batch16_candidate_v1`：一张batch样本归属一个slice，B和qparams逐slice复制，C/K reduction在slice内完成。
2. `w4_conv_ring16_candidate_v1`：A按C owner分片，B/qparams/P/D按K owner分片；每个K owner按`(owner+step)%16`访问16个activation slice。

本ADR不批准任何候选为硬件真值。批准前，两profile同时保留且manifest必须显式记录profile ID，禁止依赖默认值切换。

## 已有软件证据

- 正式模型53个QLinearConv已按shape、kernel、stride、padding、dilation和group稳定归并为20类，覆盖计数53/53。
- Conv0已用现有W3真实activation、initializer、int32 accumulator和D验证；batch/ring两profile的12类对象inverse均bit-exact，且恢复的logical tensor逐对象一致。
- 20类正式shape在N=16规划下均不越过候选25,165,824-byte slice容量；C/K owner无遗漏、无重复，所有owner的16步ring均为slice 0～15的排列。
- 20类shape均使用N=1非零坐标模式完成batch/ring A/B/qparams/P/D round-trip；N=16 batch维已由真实Conv0覆盖。
- 最大per-slice占用来自Conv0：batch 4,441,472 bytes，ring 4,820,160 bytes。软件容量不是当前裁决因素。
- 机器报告：`artifacts/w4/conv_shape_coverage.json`，SHA-256 `307f54bd55330270de1cb90fe42a8ee4433d6de66e23f9291c46148f1d2b30b3`。

## 软件侧暂定处理

- W4继续把batch与ring都作为可替换candidate验证，不把任一profile写成approved。
- Quantize D当前是一张样本一个slice的NCHW/C-order；进入batch Conv A需要NCHW→HWC+C-tail显式转换，不能标记zero-copy。
- ring profile保持与W2意图兼容，但不复用W2隐式`slice_count`；C/K owner、ring step、空贡献和last均写入manifest。
- 未获得批准前不从candidate生成目标INT8 Conv JSON/bitstream，不进入G5。

## 请求硬件侧回答

1. 一个slice在正式Conv中代表batch owner、C owner、K owner，还是随阶段变化？
2. B/bias/per-channel qparams是逐slice复制，还是只放在K owner slice？
3. 若采用ring，正式方向和起点是否为`(K owner + step) % 16`，是否固定15次neighbor transfer？
4. A窗口由AG从NHWC/raw activation生成，还是软件必须物化im2col？
5. int32 psum由哪个slice持有；跨slice归约何时结束；`last_index`引用哪个循环层？
6. requant/multiplier、output zero point和可选ReLU在SA、GA还是writeback阶段执行？
7. 请给出答案适用的RTL/ISA/register-map完整commit或版本号。

## 批准记录

- 批准profile：待填写
- 适用RTL/ISA/register-map版本：待填写
- 批准人和日期：待填写
- 证据链接或原始回复：待填写
- 需要失效/重建的candidate artifact：批准后填写
