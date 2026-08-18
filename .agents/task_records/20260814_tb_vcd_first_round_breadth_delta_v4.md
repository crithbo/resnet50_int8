# TB-VCD 首轮宽因果锥与后续证据删减门 v4

## 裁决

- 复用现有 `CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001`，不新增同义 public rule ID。
- 这是非同义窄幅增强：旧语义已有完整因果锥、四层边界和候选两两可分，但没有机器绑定“首轮至少达到本族当前第三轮宽度”，也没有强制后续删信号前验证因果无关证明的内容。
- `OBSERVER_ONLY_WIDE_CAUSAL` 默认保持不变；只有显式选择 `TB_VCD_BOUNDED_CAUSAL_CONE` 的 next fresh 包适用。
- 当前四包不追溯 HOLD、重建或重验。

## 已实现

1. 首轮绑定本族 round>=3 的 exact breadth receipt，signal/direct-driver/candidate/boundary 四项实际计数均不得低于基线。
2. 每个 HIGH 概率候选至少绑定一个 source-bound、0-hop 的直接 driver leaf。
3. catalog 绑定 pinned RTL tree SHA 与 signal hierarchy/width/source/declaration 的 semantic SHA。
4. 后续轮绑定 exact predecessor；added/removed/unchanged signal 与 preserved/closed/new candidate 必须精确对账。
5. 每个删除信号必须有覆盖全部仍开放候选的机器因果无关收据；validator读取并核实收据内容，任意 SHA-bound JSON 不能冒充证明。
6. 100,000,000-byte 软告警、8GB/10GB 投影、无截断/采样/按大小删除、平台/冻结、flush/reap 与 exact return 保护均未弱化。
7. first-fresh clean exact-ZIP 负控覆盖低于基线、缺 direct driver、无证据删减、diff 错配、候选丢失、source 漂移和保护弱化。

## 验证

- focused breadth tests: 24/24 PASS
- related VCD/selector/runtime/retention/first-fresh tests: 87/87 PASS
- package pipeline tests: 17/17 PASS
- `py_compile`: PASS
- JSON parse: 7/7 PASS
- isolated worktree 的 `.agents` receipt 在本任务前已漂移，故 active-rule audit 留给主线窄幅合并后在 canonical root 重跑；本任务没有修改这些只读文件。

## 产物

- 机器报告：`outputs/tb_vcd_first_round_breadth_delta_v4/report.json`
- 增量合同：`contracts/server_tb_vcd_first_round_breadth_delta_v4.json`
- 完整 exact shared set 与 SHA 见机器报告。

## 边界

未构建/修改/轮转 family package，未执行服务器动作，未改 RTL/config/numeric/workload/plan/owner registry；未产生 natural terminal、formal D、E4/E5 或族级根因结论。
