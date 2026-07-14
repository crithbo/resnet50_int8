# ADR-005：W4整网物理边、成本与生命周期候选审计【历史16-slice报告】

状态：旧16-slice软件候选审计通过但已由ADR-007取代；不构成28-slice证据
日期：2026-07-12

> 2026-07-13更新：本报告的93条逻辑边集合、生命周期/alias算法可复用；其中bundle字节、15-hop ring流量、每slice高水位和batch/ring物理签名均按旧16-slice布局计算，必须在28-slice新profile实现后重新生成，不得横向外推。

> 2026-07-14更新：RTL28版本已经按新architecture basis内容寻址重生成并用于G4 v2；本文件和旧报告继续只作legacy16历史证据。

## 决定

在等待正式硬件合同期间，对正式ResNet图执行三项不依赖目标opcode、地址编码或runner的整网静态审计：

1. 对93条runtime tensor边分别构造producer输出和consumer输入的物理签名，比较slice归属、逻辑轴线性顺序、每slice物理shape、payload字节数、dtype、对齐、tail zero-point语义和稳定qparams ID；
2. 调用现有78个节点对应的W4 `plan()`公式，汇总batch与ring/channel候选的逻辑I/O、standalone bundle、显式relayout和ring邻居传输成本；
3. 对runtime activation和显式relayout buffer建立活跃区间，用16-byte对齐的确定性first-fit合成偏移检查生命周期、地址重叠、alias动作和残差双分支冲突。

机器报告为`artifacts/w4/network_candidate_dry_run.json`，615,520 bytes，SHA-256 `852ea566112a92fd1965b6a2c2525449462e2b716db0941b368f87abc5d1eb18`。

## 93条边结论

- batch：93/93逐边通过；92条producer/consumer物理签名相等，1条Quantize→首Conv必须显式relayout。原分类仍为4 exact alias、1 explicit relayout、87 layout-compatible/W7 rebase、1 zero-copy。
- ring/channel：93/93逐边通过；89条物理签名相等，4条必须显式relayout，分别位于batch simple-op与channel/ring边界。原分类仍为3 exact alias、4 explicit relayout、85 layout-compatible/W7 rebase、1 zero-copy。
- 91条带量化输入输出约束的边，其producer输出与consumer输入scale/zero-point tensor ID全部一致。

“物理签名相等”只证明布局兼容，不自动分配相同base；exact alias与layout-compatible/rebase的地址所有权仍按原W4证明和后续网络分配规则区分。

## 成本口径和结果

| 指标 | batch | ring/channel |
|---|---:|---:|
| 正式节点数 | 78 | 78 |
| 逻辑I/O累计字节 | 652,723,622 | 652,723,622 |
| 16 slice standalone candidate bundle累计字节 | 1,722,427,648 | 1,340,921,344 |
| 显式relayout读+写字节 | 8,830,976 | 15,416,704 |
| 估算ring邻居传输字节 | 0 | 2,589,573,120 |
| 最大单节点每slice bundle | 4,441,472 | 4,820,160 |

逻辑I/O按每个节点重复计读写；bundle累计值包含对齐、逐slice复制的常量和节点局部P/D；ring邻居传输按每个Conv/MatMul A tile在16 owner间走15 hop估算。它们是布局成本指标，不是cycle、带宽、能耗或真实性能预测。

## 生命周期和alias结果

- batch分配80个对象（79个runtime tensor/图输入及1个relayout buffer），ring/channel分配83个对象（增加4个relayout buffer）。
- 两个profile的合成activation高水位均为3,411,968 bytes/slice，峰值同时活跃payload为2,408,448 bytes/slice，低于候选25,165,824 bytes/slice容量。
- first-fit分别复用75和78次已结束生命周期的空间；所有活跃期重叠对象地址区间互斥。
- 两个profile各检查16个真正的残差QLinearAdd双输入；两分支tensor ID不同、生命周期交叠时地址也不重叠。
- 物理兼容边直接引用同一runtime tensor对象；显式relayout边使用独立临时buffer，且与源地址不重叠。

该分配只覆盖activation与transition buffer。weight、qparams、operator-local P/scratch已计入逐节点bundle容量，但未被伪装成获批的整网DDR常驻地址。

## 非结论

本报告没有生成W5 JSON/bitstream，没有选择正式DDR地址，没有执行simulator或硬件，也不证明任何真实cycle、带宽或能耗。它新增的是可复用的软件门证据；G4仍必须等待ADR-004规定的真实硬件批准合同。
