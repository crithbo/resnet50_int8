# 双包流水与 Dequant 原子合同物化

日期：2026-07-26

## 双包策略

服务器后续采用两个候选交错运行：

1. Requant node0001 atomic2 的全新 bootstrap 修正版；
2. Dequant node0077 atomic single-stage 的全新诊断包。

一份包在本地分析回传时，服务器可以直接运行另一份，减少服务器空闲。两者使用独立
package/install/run/return 命名空间，结果不能互相代替。

Requant atomic v1 的正式回传在 package exact-set preflight 即失败：

```text
classification=SERVER_TEST_INFRASTRUCTURE_PACKAGE_PREFLIGHT_FAILURE
compile/sim/run=125
start/finish/MSE4/formal D=0
counts_as_atomic_dynamic_attempt=false
```

根因是包内 runtime import 在 preflight 前生成 `__pycache__/*.pyc`。公共规则新增：

```text
CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001
```

新规则要求 shell 与 Python 双层禁止 bytecode，并从全新解压 ZIP 执行真实入口、核对
运行前后 package tree 不变；不得忽略或允许 pyc。

公共规则身份：

```text
.agents/rules/服务器测试包生成规则.md
sha256=bdddfedd8d361d745298ac36db9862638a54096eac3d7da5c77e852a3e8dfeea
```

## 第二包选择

第二包选择 DequantizeLinear node0077，而不是提前生成 Requant guard-only/round-only：

- Requant 附加原子项仍必须等待 atomic2 真正进入仿真后的首分歧；
- Dequant 全量 E4 已有 28/28 Start、0/28 Finish 的独立 blocker；
- 最小 Dequant 可以直接区分 A read、GA add→mul、normal outbuffer、MSE4 writeback 和
  completion/tag。

新增专项规则：

```text
CDA-DEQUANT-ATOMIC-STOCK-TB-001
.agents/rules/DequantizeLinear原子动态合同规则.md
sha256=c2873ebf86181262ae1f6235f19162e44ab31523e5031cc329b89150a61b7e53
```

## Dequant 原子合同

```text
logical occurrence count = 1
physical slices = [0, 1]
used_slices = ...0011
stage count = 1
Repeat_Num = 1
per-slice CWH shape = [16, 1, 1]
A base = 0x00000000
D base = 0x00000010
A = 16 bytes/slice
D = 64 bytes/slice
formal D = 4 x 128-bit lines/slice
accepted MSE4 = 4/slice, 8 total
```

配置从已闭合 node0077 v5 JSON 精确派生，只改变 6 个 leaf：

- LC1/LC3 `end: 47 -> 1`
- A/D 最外 shape stride：752/3008 -> 16/64
- A/D address-bound base -> `0x0/0x10`

GA add→mul、UINT8→FP32 conversion、常量 bit、normal outbuffer、Buffer、transaction 和
bank/column 均不变。输入覆盖 0、255、59/60/61 和 zero-point 两侧；slice1 是 slice0
的确定 rotation。

## 资产身份

```text
configs/native_ndp_sim/node0077_dequant_atomic_single_stage_stocktb_v1/
  config.json
    sha256=1e331488ff95d10f5c9b50abde13193b495d24f0230f51b6e4f38f836a9ee290
  manifest.json
    sha256=fe9103a3a672f9270f0f82c128550d046d9d0511adfc489fd22cfa45722c4318
  generation_receipt.json
    sha256=d8f97f5f81b2f3939ab20de86b31dc04b515ead171675ec2913aa3e98bcff04f

contracts/operator_config/dequant_node0077_atomic_single_stage_stocktb_v1.json
sha256=6cba3fd2c04dd9feb3447c185d4432a1aaba28f15276595c57406b67c64cf74d

artifacts/operator_config_validation/
  r5-dequant-node0077-atomic-single-stage-stocktb-v1/local_contract_report.json
sha256=cf59f82a0b962662e4cdc1983b254e3d79c74e9d02f689090c382c1e7f394cff
```

验证：Dequant atomic、完整 Dequant vertical 和既有 Dequant package 定向测试
15/15 PASS。

## 声明边界

当前 Dequant 原子合同是 `LOCAL_DYNAMIC_CONTRACT_MATERIALIZED_NOT_RUN`：

```text
candidate_release=false
server_package=false
counts_as_node0077_e4=false
counts_as_node0077_e5=false
remaining_blocker=B_DEQUANT_SERVER_E4_E5
```

本会话不生成服务器包。测试修复会话必须为两份包分别使用全新身份，并在封包前共同执行
no-bytecode/bootstrap immutability 自检。
