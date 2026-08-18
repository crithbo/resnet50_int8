# TB-VCD 软宽度参考与自适应删减 v4（取代未激活硬版）

## 用户修正

上一版把“达到同族第三轮宽度”与逐信号全候选因果无关证明设成硬门。用户已明确撤回这两个硬约束，因此旧 v4 在正式激活前被本记录取代。

继续复用 `CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001`，不新增 public rule ID；observer 默认不变，当前四包不追溯 HOLD、重建或重验。

## 当前语义

1. 首轮仍必须绑定同族 current round>=3 的 exact breadth receipt，并声明合理信号数范围。
2. 低于或高于范围本身不阻断；必须记录相对关系、偏离说明并确认。
3. HIGH 候选的 source-bound zero-hop driver 是强推荐覆盖目标；缺失时记录 exact gap。只要 candidate matrix 仍完整且两两可区分，不以该缺失单独阻断。
4. 后续删信号记录 family 判断的 reason、confidence、affected candidates；不要求证明对所有保留候选均因果无关。
5. LOW confidence 默认保留，因此低置信度删除仍 fail closed。
6. exact predecessor、add/remove/unchanged diff、候选保留/关闭、source identity、候选矩阵可区分，以及 VCD 大小/停止/flush/reap/return 保护继续是硬门。

## 验证

- focused: 26/26 PASS
- related VCD/selector/runtime/retention/first-fresh: 89/89 PASS
- package pipeline: 17/17 PASS
- Python compile: PASS
- JSON parse: 7/7 PASS

正控明确证明：低于参考范围但有说明可 PASS-with-warning；缺 HIGH driver 但矩阵可分可 PASS-with-gap；只影响部分候选的 MEDIUM-confidence 删减可 PASS。

## 产物与边界

- 机器报告：`outputs/tb_vcd_soft_reference_adaptive_pruning_v4/report.json`
- 合同：`contracts/server_tb_vcd_first_round_breadth_delta_v4.json`

未构建/修改/轮转 family package，未执行服务器动作，未改 RTL/config/numeric/workload/plan/owner registry；无族级诊断、natural terminal、formal D、E4/E5 结论。
