# VCD 单轮定位效果与审计无需强制改规则裁决

日期：2026-08-14

## 本轮 VCD 效果

四份 TB-VCD return 中只有 serialized Conv v92 真正进入目标因果区间并形成完整可消费 VCD。v92 的
VCD 约 74.7 MB，覆盖 43 个汇总信号和 2,549,739 个 owner-clock 上升沿；它继续排除旧 ACK comparator，
并把首分歧从宽泛 ACK/FIFO/MSE4 停滞收敛到 downstream RD_Buffer_AG/backpressure。但因缺少
RD_Buffer_AG output-buffer 与 WR_Data_Channel readiness 的直接 driver cone，仍未唯一到代码根因。

Native p47 在 package-local invalid XMR 处 compile fail；GAP v62 在 embedded manifest 中间状态处
preflight fail；QAdd v63 虽启动 simulation，但在 target entry 前被 false sim-time freeze 停止。后三者
没有可用于 DUT 根因裁决的目标 VCD。因此当前证据只能说明：VCD 在“目标实际执行且因果锥覆盖直接
driver”时能显著收窄，但尚未证明四族都能一轮唯一定位。

## 用户审计裁决

规则审计仍按触发条件执行，但审计不再强制制造规则修改。若审计证明 current public/specialized rule
语义与 current shared gate 已充分覆盖、失败只是孤立偶发的 package 实现或人工操作失误、没有共享
coverage gap，则允许机器裁决 `RULE_CONFIRMATION_NO_CHANGE`：

- 不修改公共规则、schema、tool 或共享测试；
- successor 仍修复 package-local 错误并重跑原 first-fresh/final-ZIP 门；
- 只有 current gate 无法捕获同机制时，才新增 validator/negative control 或提交非同义 delta；
- 不得为了满足“做过审计”的形式新增同义规则或无因果价值的检查。

该裁决已窄幅写入 `.agents/agent.md`、服务器测试包规则、生成前索引、整网优化专项规则和 current plan。
它不追溯改变当前四个 `PACKAGE_READY_NOT_RUN` 包，也不授权服务器、RTL、config、numeric 或 workload
动作。
