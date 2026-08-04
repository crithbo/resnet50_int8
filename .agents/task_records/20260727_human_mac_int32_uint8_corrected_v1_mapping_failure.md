# 人工 mac_int32_uint8 corrected-v1 原生 mapping 失败

## 候选身份

- 原 ZIP SHA-256：
  `7b6770dfe038d5e92b810c20fb4a8a620472afd1dc1e3d6837d4e3af54755a55`
- 原 entry SHA-256：
  `d98929d1c31b6c55d12ea8b232cf76400024d60ebc29d8d4e39c6e3abc8e4db9`
- corrected-v1：
  `artifacts/human_mac_int32_uint8_20260727_v1/mac_int32_uint8.corrected.json`
- corrected-v1 bytes：12163
- corrected-v1 SHA-256：
  `9b5319b2935a2b0886a59682d4375e36883a795b621bb1998451472915aec42a`
- `human_authored_input=true`

corrected-v1 相对原 entry 只有用户授权的 8 处
`alu_opcode: mac → int32_mac`。

## 已通过

- JSON 可解析；
- 通用结构 validator：`valid=true`；
- 8 个整数 MAC PE 的三输入模式完整；
- CONFIG 为 IGA/LSU/GA enable+update，SA disabled；
- 原文件未修改。

## 原生 mapping 首分歧

两次隔离构建均调用活动原生：

```text
ndp-sim/bitstream/main.py
seed=20260727
heuristic_iterations=5000
heuristic_restarts=10
```

两次均失败，最优 mapping penalty 均为 4。四项违反均为：

```text
DRAM_LC.LC0 → READ_STREAM0  violates LCtoStreamConstraint
DRAM_LC.LC0 → READ_STREAM0  violates LCtoStreamConstraint
DRAM_LC.LC0 → WRITE_STREAM0 violates LCtoStreamConstraint
DRAM_LC.LC0 → WRITE_STREAM0 violates LCtoStreamConstraint
```

人工 JSON 让同一逻辑 `DRAM_LC.LC0` 同时成为 read stream 和 write stream 的第二 memory
index source。两个固定物理 stream 对 LC 的可达域不相交，无法获得 penalty=0 placement。

## 可信参照与最小修正方向

可信原生 `ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json` 对同类
int32→uint8 数据路使用三个 LC_PE：

1. `PE0` 从 `DRAM_LC.LC0` 接收；
2. `PE1` 从 `PE0` 接收，作为 read stream branch；
3. `PE2` 从 `PE0` 接收，作为 write stream branch；
4. read/write stream 分别引用 `LC_PE.PE1` 与 `LC_PE.PE2`。

该参照只证明分支拓扑方向，不授权静默替换人工候选。corrected-v1 保持冻结。

## 裁决

- `CONFIRMED_REFERENCE`：原生 LC_PE 分支拓扑与 mapper 可达约束；
- `LOCAL_E2=false`；
- `STRUCTURAL_RISK=MAPPING_EXACT_ZERO_FAILURE`；
- `DYNAMIC_REQUIRED=true`；
- `candidate_release=false`；
- `generated_package=false`。

根据 `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`，不得使用 direct mapping、非零 penalty
或旧码流继续生成。等待用户对第二组字段修正作出明确授权。

