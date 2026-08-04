# Requant 原子合同 stock-TB 兼容 v2

日期：2026-07-26

## 裁决

活动 `tb_NDP_Top_new_phy.sv` 对每个 `Repeat_Num` 固定观察物理 slice0 的
`Start_Comp`，随后等待物理 slice1 的 `slice_cmpt_finish`；该观察不是 mask-aware，
`RUN_TIME=100000000000000`。因此只启用 slice0 的 v1 即使计算语义正确，也不能由
stock TB 自然进入 SCA_D。

本轮选择配置侧方案：

- 不修改 TB；
- 不修改 `NDP_copy01/rtl/**`；
- 不使用 force/deposit、缩短 timeout 或驱动式 observer；
- 冻结 v1 为 `STOCK_TB_COMPLETION_MASK_INCOMPATIBLE`，未封包、未运行，不计动态失败；
- 以全新 v2 身份启用 slice0+slice1。

## v2 语义边界

v2 仍是一个逻辑 HWC8 occurrence 和严格相邻的两个 stage：

```text
guard -> round_saturate
Repeat_Num = 2
active_slices = [0, 1]
physical_slice_instance_count = 2
```

物理 slice 增加不改变 stage 数，也不把 `Repeat_Num` 改为 4。两个 slice 使用相同的
address-bound JSON 拓扑，但输入按 row rotation 区分；输入、guard FP32 golden、
final UINT8 golden 和 MSE4 write 均按 slice 独立物化。stage0 D 与 stage1 A 仍逐
slice 同址 `0x00800000`，stage1 external preload 为 0；两个 slice 的 guard 完成后
才允许 round 启动。

物化计数：

- 64 elements total，32 elements/slice；
- guard：8 beats/slice，16 beats total；
- round：2 beats/slice，4 beats total；
- accepted MSE4 writes：20 total；
- candidate_release=false，server_package=false，dynamic status=NOT_RUN。

## 新增规则

- `CDA-REQUANT-ATOMIC-STOCK-TB-MASK-COMPAT-001`

同时收紧 `CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001`：逻辑 occurrence 数与物理
slice instance 数必须分栏，不能因为适配 TB 而混淆两者。

专项规则身份：

```text
.agents/rules/RequantizeUint8算子配置规则.md
size=14910
sha256=f0315f627a492a660c91a95aa12d46339518863b79358280e498dc2125799cf3
```

## 主要资产

```text
configs/native_ndp_sim/node0001_requant_single_occurrence_two_stage_v2/
  guard.json
    sha256=defeca56b0c248eb1f4915b0338227580687d4e8c92cedf548ad727f6457d5d2
  round_saturate.json
    sha256=e8e3d0f2ed67f77f8228aeb142e64b038f1f0ac4cdbc2e79f297ca4ee4be08b0
  manifest.json
    sha256=c6e50200d01209147851d990e824b3eead748ecfec9fb64aaaf6cd0cd97d4097
  generation_receipt.json
    sha256=0046cc4ad1e19e905b24b3b78524a5c80b991c5c4699bcd329c6d9c8063f7f25

artifacts/operator_config_validation/
  r5-requant-node0001-single-occurrence-two-stage-v2/local_contract_report.json
    sha256=aa1acd52995cfa22dc6cbb9f8c2682fd50782dfdc80d893673237130dddeaeb3

contracts/operator_config/
  requant_node0001_single_occurrence_two_stage_dynamic_v2.json
    sha256=efba2a4f00764d7f9cecef8c91888255ea5f0a1d409b94df4d277d41766cbd9b
```

两份 v2 JSON 与 v1 对应 JSON 逐字节一致。新身份来自 active mask、双 slice
input/golden/write/lifecycle 和新读取 provenance，而不是伪造 JSON leaf 差异。

## 直接消费者证据

```text
NDP_copy01/README_HARDWARE_SIM_ENTRY.md
sha256=4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7

NDP_copy01/tb_NDP_Top_new_phy.sv
sha256=e068f7500f0c71c2ba2c756f74a4519c33d13d4afe0fa4cc9f6c9e79b1e3f994
```

关键源码范围为主流程的 `RUN_TIME` 和完成循环：每次先采样 group0/slice0 start，
再采样 group0/slice1 finish。

## 定向验证

命令：

```text
.venv/Scripts/python.exe -m unittest
  tests.test_requant_single_occurrence_dynamic
  tests.test_requantize_uint8_vertical
  tests.test_requant_node0001_config_bound_simulator
  tests.test_requant_family_classification
```

结果：20/20 PASS。

规则 SHA 更新后，直接 hash-bound 的 node0001 config-bound simulator 与 Requant
family classification 报告已重建；数值结论不变：

- node0001 config-bound simulator：48/48 stage，golden mismatch=0；
- Requant family：54/54 标准 W3 公式匹配，仍只有 node0001 完成物理 E2；
- `B_REQUANT_SERVER_E4_E5` 未解除。

## 交接

本会话不生成服务器包。测试修复会话只应消费 v2，按最新服务器生成规则做一次封包前
自检；不得回退到 v1，也不得修改 TB 或 `rtl/**`。

## 后续包状态

测试修复会话已按上述边界生成唯一 stock-RTL FIRST_DYNAMIC 诊断包：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  rq_node0001_atomic2_stock_v1.zip
size=74100
sha256=4f732020c598ac9e00eec5dddf4a06f84e5f0caf54fb75243d6df7e38922f54b
```

本地包级验收为 26/26 PASS；ZIP 共 48 entries，`rtl/`、wave 和 nested archive 均为
0。该状态仅为 `PACKAGE_READY_NOT_RUN`；尚无动态首分歧，不计 node0001 E4/E5，
`candidate_release=false`、`NO_DYNAMIC_BASELINE` 和
`B_REQUANT_SERVER_E4_E5` 均保持不变。正式记录见
`.agents/task_records/20260726_requant_atomic_v2_stockrtl_package_ready.md`。
