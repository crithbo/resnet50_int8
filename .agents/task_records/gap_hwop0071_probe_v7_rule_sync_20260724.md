# GAP probe_v7 规则同步记录

状态：已完成规则资产与 validator 同步；未修改功能 RTL，未改写服务器测试分析结论。

更新文件：

- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `resnet50_pipeline/gap_ga_accumulator_state.py`
- `resnet50_pipeline/gap_d_index_schedule.py`
- `resnet50_pipeline/stage_operator_semantics_audit.py`
- `tests/test_gap_ga_accumulator_state.py`
- `tests/test_gap_d_index_schedule.py`
- `contracts/operator_config/gap_ga_accumulator_state_v1.json`
- `contracts/operator_config/gap_d_index_schedule_v1.json`
- `contracts/operator_config/stage_operator_semantics_audit_v1.json`
- `contracts/resnet50_r5_lowering_bundle.json`（依赖哈希重建）
- `configs/stage_codegen/hwop-0071-00-d-index-v1/`（D-index 规则合同重建）

验证：`.venv/Scripts/python.exe -m unittest
tests.test_gap_ga_accumulator_state tests.test_gap_d_index_schedule
tests.test_stage_operator_semantics_audit`，23 项通过。

规则 ID：

- `CDA-GA-OUTBUFFER-OCCUPANCY-001`
- `CDA-GA-INVALID-SLOT-ISOLATION-001`
- `CDA-GA-CROSS-BLOCK-INIT-001`
- `CDA-GAP-ORTHOGONAL-DEFECTS-001`
- `CDA-GAP-D-READBACK-COVERAGE-001`
- `CDA-MSE4-MONITOR-EVIDENCE-001`
- `CDA-SERVER-FOCUSED-IDENTITY-001`

最终分类：
`ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse`。
