# Conv native-four-lane negative-psum 主线独立复核

日期：2026-08-03  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 裁决

`CONFIRMED_REAL_CURRENT_RTL_FUNCTIONAL_DEFECT`。这不是上次 occupancy/count
语义误读的重演。

必须区分两个范围：

- node0004 冻结代表实例自身完整扫描没有命中 `psum=-5,dot4=+5`；
- native-four-lane 候选预期扩展到 53 个 Conv，冻结 node0003 /
  `hwop-0003-00` 的真实执行顺序明确命中该边界。一个真实可达且 current RTL
  错算的点已经足以阻断全族性能候选。

因此保持：

```text
B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE = OPEN
SA_INT32_NEGATIVE_PSUM_FULL_WIDTH_RECONSTRUCTION = OPEN
B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING = OPEN
status = HARDWARE_CAPABILITY_BLOCKED
PACKAGE_RELEASE = NONE
```

serialized correctness baseline 与 serialized Conv v28→successor 路线不受此裁决影响。

## 独立重建真实 Conv occurrence

主线新增了不 import owner 扫描模块、不读取 owner 首例作为计算输入的 fresh 程序：

- `tools/recheck_conv_native_four_lane_negative_psum_independent.py`

程序直接读取：

- ONNX 模型
  `artifacts/reference_model/resnet50-v1-12-int8.onnx`；
- W3 激活
  `artifacts/w3/golden_batch16/tensors/tensor-8d2f28c80ac24676.npy`；
- typed request `hwop-0003-00`；
- ONNX 中对应 weight、bias 与 per-channel weight zero-point。

所有模型、激活、typed lowering、request 与 initializer content SHA 都先做精确校验。
随后只使用 NumPy 整数乘加和显式 s32 recurrence，在
`(sample,h,w,oc,k_group)=(0,23,40,33,14)` 重建：

```text
corrected bias = 5687
sum(dot4 group 0..13) = -5692
psum before group14 = -5
activation lanes = [21,24,24,26]
weight lanes = [-1,0,0,1]
lane products = [-21,0,0,26]
dot4 = +5
mathematical next psum = 0
```

独立数据报告：

- `artifacts/operator_config_validation/r5-conv-native-four-lane-negative-psum-mainline-independent-recheck/data_recheck.json`
- bytes=`9592`
- SHA256=`62d71f719c332c3de868e814d221c68dcf58d31e1706bfe837c520e8ead24e82`
- command exit=`0`

这排除了 synthetic-unreachable 与 owner enumerator 自证。owner 所报
`528 hits / 19 instances` 聚合计数本轮没有重复枚举；blocker 只依赖一个真实可达
mismatch，因此不依赖该聚合数。

## current RTL 独立动态复现

目标为已同步 current commit
`8f2f3181c1103d705cdf9b9722959e7315f8b875`，关键 current SHA：

- `SA_PE_Float_CSA.v`：
  `ea24759841d990f230f9c33a111f934e107c996a85b2f5ea00c9408ca73d0223`
- `SA_PE_Float_Control.v`：
  `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6`
- `SA_PE_Mul_Array.v`：
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_ALU.v`：
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`

fresh 数学期望驱动 testbench：

- `outputs/conv_native_four_lane_negative_psum_reachability/independent_mainline_recheck_tb.sv`
- bytes=`2371`
- SHA256=`f98ab1fe3a594419e91f453a7dd45bece117cc6daab703aceaa55b8baee031bf`

Icarus `-g2012` 对 current exact arithmetic source 集编译 exit=`0`，仿真 exit=`0`。
结果：

| psum | dot4 | 数学期望 | current RTL | 裁决 |
|---:|---:|---:|---:|---|
| -6 | +5 | `0xffffffff` (-1) | `0xffffffff` | pass |
| -5 | +5 | `0x00000000` | `0x80000000` | **fail** |
| -4 | +5 | `0x00000001` | `0x00000001` | pass |
| 0 | +5 | `0x00000005` | `0x00000005` | pass |
| 7 | +5 | `0x0000000c` | `0x0000000c` | pass |

相邻点与正数点通过，排除了一般 packing、操作数方向、dot4 或采样延迟问题。

精确机制是：

1. `SA_PE_Float_Control` 对负 DataC 生成 magnitude，并把负号独立携带；
2. exact cancellation 时 `SA_PE_Float_CSA.c_Result0_wire=0x80000000`；
3. current line 50 只对 `[30:0]` 做负数重建，得到 0；
4. current line 51 又直接复制 raw bit31=1；
5. 最终得到 `0x80000000`，而非 `0x00000000`。

line 49 的 full-width 写法仍是注释，不参与硬件。本记录不裁决“取消注释是否就是充分
修复”；任何 functional RTL repair 仍需用户明确授权并经过完整验收。

## 机器收据与边界

汇总报告：

- `artifacts/operator_config_validation/r5-conv-native-four-lane-negative-psum-mainline-independent-recheck/report.json`
- bytes=`6116`
- SHA256=`64bea88f857ce13d63b5e8567550fc056f2cab48ca6812b4d83cd497046fa480`

独立重建程序：

- `tools/recheck_conv_native_four_lane_negative_psum_independent.py`
- bytes=`8846`
- SHA256=`2a98d064fc0144af3a37a597292689390c2f58120359565d4e74e5d9031fe409`

本轮未修改功能 RTL、未生成服务器包、未上传或运行服务器。没有重跑 53-Conv 全枚举，
也没有绑定服务器 production filelist；因此不增加 E2/E3/E4/E5。

`RULE_CONFIRMATION`：

- `CDA-SA-INT8-RTL-COMPATIBILITY-001`
- `CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001`

现行规则正确要求真实 W3 可达性、current RTL 动态反例与 fail-fast 停止；
`RULE_DELTA_PROPOSAL=[]`。
