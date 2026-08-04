# Requant guard-only direct-signal v1 回传裁决

日期：2026-07-27

## 结论

本回传是有效、自然完成的 guard-only 动态失败，不计 node0001 E4/E5。

- return ZIP：62,590 bytes，
  SHA256 `9c2c83a81135aba64f8f17e53c6c4f708d488eed2f6041fb064a65a4395596d5`
- 来源 package：
  `rq_node0001_guardonly_directsig_stock_v1.zip`，SHA256
  `715a4b8abdd45b3251c464eba4359cea8af740c75b238a68d956f949524a1939`
- 内部 RETURN_RECEIPT：32/32 exact-set、size、SHA、allowlist 通过
- compile/sim/run：`0/0/0`；slice0+1 一个 guard stage 自然完成；stock RTL 未变

运行数据已完整通过 int32→fp32 registered conversion、GA final out 和 PE input-side
选择：三处均为 64/64，62 条非零、2 条预期零。因而更早
`GA_INPORT_CONFIG/IB/CONVERT_INPUT` 的零计数只是 observer gap，包内
`GA_INPORT_CONFIG_UNOBSERVED_AFTER_MSE0_TO_BUFFER` 路由作废。

SFU input/compute/LUT/ALU/output 和 normal outbuffer 未观测；其后 16/16 MSE4
write-data 与 16 行正式 D 全零。权威分类：

`SFU_INPUT_UNOBSERVED_AFTER_PE_SELECTED_INPUT_BEFORE_MSE4_WDATA_ALL_ZERO`

`PE_SELECTED_INPUT` 的 probe 是 input-side enable/data，不等价于 post-register accepted。
责任保持 `CONFIG_CONSUMPTION | RTL_CONTROL | OBSERVER_EVIDENCE`。

## 规则与代码更新

- 新增公共规则 `CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001`
- 新增专项规则 `CDA-REQUANT-DIRECTSIG-V1-DYNAMIC-EVIDENCE-001`
- 修正 `tools/requant_atomic_server_runtime.py`：下游完整非零证据支配较早零计数 probe，
  输出有界未观测区间
- 新增定向 validator 回归；2/2 通过
- 机器报告：
  `server_returns/rq_node0001_guardonly_directsig_stock_v1_return_analysis_20260727.json`
  SHA256 `9b952ea909734713db8d385760511965693638bbccc344c5abe2446d94b38f7e`

## 唯一后继

冻结全部语义资产，只生成全新身份的 guard-only SFU readiness 诊断包，采集 odd-PE
opcode/SFU valid、group compute-valid、LUT 初始化完成、compute-enable、PE inbuffer
post-register valid/matched 和 preprocess pipeline0 valid。round-only、alias/lifetime
与完整 E4 继续禁止。

