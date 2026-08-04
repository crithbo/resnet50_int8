# Requant single-occurrence-two-stage 最小组合动态合同

日期：2026-07-26

## 结论

已从 node0001 已闭合的 `w0/s00` 两份最终 address-bound JSON 精确派生一个
slice、一个 HWC8 occurrence、4 个空间位置、2 个 stage 的诊断合同。未裁剪旧服务器
包，未生成服务器包，未修改任何 `rtl/` 文件。

状态：

```text
LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN
candidate_release=false
formal_target_instance_allowed=false
server_package=false
counts_as_node0001_e4=false
counts_as_node0001_e5=false
remaining_blocker=B_REQUANT_SERVER_E4_E5
```

新增规则：`CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001`。默认只运行组合合同；
`guard-only`、`round-only`、`alias-lifetime` 均保持禁用，只在组合合同出现匹配的
首分歧后启用唯一对应项。

## 物化内容

入口：

- `configs/native_ndp_sim/node0001_requant_single_occurrence_two_stage_v1/`
- `contracts/operator_config/requant_node0001_single_occurrence_two_stage_dynamic_v1.json`
- `artifacts/operator_config_validation/r5-requant-node0001-single-occurrence-two-stage-v1/local_contract_report.json`

两份 strict JSON 只改变 shape schedule 的 4 个 leaf：

- guard：LC end `[1,12544,12544] → [1,4,4]`，A/D outer stride
  `401408 → 128`；
- round：LC end `[1,12544,3136] → [1,4,1]`，A outer stride
  `401408 → 128`，D outer stride `100352 → 32`；
- 其余 topology、GA opcode/conversion、normal outbuffer、buffer bank/column、
  base address 和 8 lane 常量不变。

物理数据：

- input：`int32 HWC8 [4,8]`，128 bytes / 8×128-bit line；
- guard golden：`fp32 HWC8 [4,8]`，128 bytes；
- final golden：`uint8 HWC8 [4,8]`，32 bytes；
- 覆盖 2 个负值、`-1`、零、29 个正值、8 个 exact FP32 half tie
  （2 个向下取偶、6 个向上取偶）、低端/高端饱和各 9 个，以及全部 8 lane
  multiplier；
- magic-round 与独立 `rint` mismatch=0。

动态期望：

- guard MSE4 accepted write：8 beats，byte address
  `0x00800000..0x00800070`；
- round MSE4 accepted write：2 beats，byte address
  `0x01000000..0x01000010`；
- 每 beat 固定 `strobe=0xffff`，地址、128-bit data 与单 beat SHA 已完整枚举；
- `Repeat_Num=2`，两次 Start/Comp Finish，同一 slice0 mask；
- RequantGuard 在首个 start 前加载一次；
- stage0 D=`0x00800000` 与 stage1 A 同址，stage1 A external preload=0，
  stage0 `Comp Finish` 后才允许 stage1 start。

## 身份

- Requant 专项规则：
  `6e3be32694a3962166980e52bcff8d3b47a867a5c7d628c3446724d9c84932d1`
- generation receipt semantic SHA：
  `8b78d1945992ffd6695a9b7c4a61b0a194c34ae9775046b04939ed0c325f8a24`
- guard JSON：
  `defeca56b0c248eb1f4915b0338227580687d4e8c92cedf548ad727f6457d5d2`
- round JSON：
  `e8e3d0f2ed67f77f8228aeb142e64b038f1f0ac4cdbc2e79f297ca4ee4be08b0`
- manifest semantic SHA：
  `55f876129ae11f6d6ad28fac7cc32f77ed4ee81da72950f9cd9997370302209e`
- manifest file SHA：
  `17ec522f48de0d31dea4212b03b4f97253b93e850731240a828705b5d056d1da`
- contract file SHA：
  `1e00fbd4c697a0d7866f609fc48c2f88388ada4895f66c1e5ed05b40ff5ef076`

规则 SHA 变化后仅刷新了直接受影响的 Requant config-bound simulator 和 54-stage
family 数值报告收据，没有重建 node0001 全量 native E2，也没有改写服务器候选。

## 验证

- 两份 JSON：strict validator 通过；
- 活动 native encoder direct-mapping parse/encode smoke：guard、round 均通过；
  该项只证明可编码，不作为正式 mapping/bitstream provenance；
- 定向 Requant + 公共 plan/rule tests：35/35 通过；
- 组合合同 fresh rebuild 与 checked manifest 逐文件一致；
- `NDP_copy01/rtl` 无本任务改动。

下一步由“测试修复”会话按服务器生成规则从本合同完整生成最小 stock-RTL 动态包。
本会话不生成包；若回传出现首分歧，再按
`first_divergence_routing.json` 唯一启用对应附加原子项。
