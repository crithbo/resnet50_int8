# TB-VCD planned-dumpoff / freeze / one-shot STOP 共享修复

日期：2026-08-15  
角色：`optimizer.whole-network`  
状态：`CURRENT_DISK_SHARED_DUMPOFF_FREEZE_ONE_SHOT_READY`

## 输入与裁决

p51 正式 return 证明：TB 在 VCD timestamp `7689350625` 计划执行 `$dumpoff` 后，执行时间继续到
`8847360625`，但旧共享 evaluator 因 VCD 不再追加而清空 `dump_off_cycle`，随后误判
`SIM_TIME_FREEZE`；level 型 STOP marker 重复 `678453` 次。

分类为现有
`CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001` 的实现逃逸，并包含一个窄幅相位语义
歧义：规则已要求 dumpoff+grace 优先形成 `CAUSAL_PLATEAU`，却仍把 intentional dumpoff 后停止增长的
VCD timestamp 当作 freeze 的唯一 witness。不新增同义 public rule ID。

## 实现

- dumpoff 前继续以 appended VCD timestamp 裁决 freeze；
- 只接受同次运行、粘性、cycle/timestamp 精确绑定的 planned-dumpoff 事件；
- dumpoff 后以 owner clock 与 TB execution sim time完成 `262144` cycle grace；
- `dumpoff+grace` 在 evaluator 内先于 freeze；
- STOP marker 必须 one-shot，重复、回退、dumpoff 状态清除/漂移均 fail closed；
- runtime receipt 新增 phase-aware `dump_control` 与三项 consistency replay authority；
- quiescent VCD、flush/close、process-tree reap、PARTIAL 和独立安全退出门全部保留。

## 验证

- `py_compile`：3/3 PASS；
- focused + related regression：120/120 PASS；
- positive causal-cone contract CLI：PASS，errors=0；
- JSON parse：6/6 PASS；
- `git diff --check`：PASS；
- p51 永久反例已固化，计划 dumpoff 后 VCD timestamp 固定而 execution time推进时，grace 完成得到
  `CAUSAL_PLATEAU`；无 dumpoff 的三次真实冻结仍为 `SIM_TIME_FREEZE`；重复 STOP fail closed。

## 精确机器报告

`outputs/tb_vcd_planned_dumpoff_consistency_v5/report.json`  
bytes=`6976`  
SHA256=`b175c14254f33505ae94df2ec031b070ce3d79a49617702ce8f9923c6d531dea`

该报告列出全部 13 项工具/schema/contract/fixture/test exact identity 和主线窄幅同步指令。

## 读取收据

读取了 canonical current：

- `.agents/agent.md` SHA256=`fe1cf8cc17d48d626a233694dfe0c7f0004fad0b17e21881b77736167088fb81`；
- `.agents/plan.md` SHA256=`45bbc125c6754abce46ce123dd8214a9e894b16c7f27fb6e4a872e6f885693c1`；
- `.agents/rules/生成前必读索引.md` SHA256=`1621988243c208ff81475e2a1e2e61aa72ad857f4d98ffe2e5fb2b5dacf52ac4`；
- `.agents/rules/整网测试收敛优化专项规则.md` SHA256=`3f082f07b4d7efb239d6b79b6cc72e979b5ad638166796a18a24879502b6b7db`；
- `.agents/rules/服务器测试包生成规则.md` SHA256=`f2aa05d8571a3ec4d782bafdff30a4bbcefed5d34cf799cec8131c09ab75c2d6`；
- p51 mainline receipt SHA256=`4178f10529787eed41570a014a55d124f998fdc09a55659b42b032c8189f36bc`。

## 边界

仅修改隔离 worktree 的共享工具/schema/contract/fixture/test/report/task record。未修改 family package、
storage、plan、owner registry、functional RTL、config、numeric 或 workload；未上传、连接、取 lease 或
运行服务器。本地修复不证明 production natural terminal、formal D、E4 或 E5。
