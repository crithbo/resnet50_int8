# QLinearAdd P1-A standalone CLI bootstrap 修复

日期：2026-07-27

## RETURN_ANALYSIS

主线复核发现从仓库根直接执行：

```text
python tools/validate_qlinearadd_predesign.py \
  contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json
```

时，Python 将 `tools/` 而非仓库根放在首个 import path，导致
`ModuleNotFoundError: No module named 'resnet50_pipeline'`。

修复只作用于本族 CLI：

```python
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

该 bootstrap 位于导入 `resnet50_pipeline.qlinearadd_predesign` 之前。新增 subprocess
测试从仓库根使用当前 Python、相对 CLI 路径和相对合同路径执行真实入口，并解析 stdout
机器报告。

P1-A 数值、DAG、lifetime、blocker、P0-A 依赖和 fail-closed 合同均未改变。

## 验证边界

- standalone CLI 必须退出 0；
- stdout 必须是合法 JSON；
- `valid=true`、`instances=17`、`materialization_allowed=false`；
- 原有 release-mutation fail-closed 测试继续通过。

使用主线指定的
`C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
从仓库根执行真实 CLI：退出 0，`valid=true`。同一解释器运行
`python -m unittest tests.test_qlinearadd_predesign -v`：3/3 通过，包含新增 standalone
subprocess 测试。

修复后关键 SHA-256：

```text
9f4f79499d4c9ac0072bfd3fcff4ef3e714f0db06612a3a125ee7ae685ce8291  tools/validate_qlinearadd_predesign.py
8ef05b97dbf2f2cbf4299dc4eb60bb8877c9d7f671a5e081b6e5de6138ce9d69  tests/test_qlinearadd_predesign.py
94e8ab0fdeb393f7d6a64e938479779b9cc250c5ba1f6ee27fd5ea1d1127e4ff  contracts/operator_config/qlinearadd_composite_backend_predesign_v1.json
c9e6b90ab5bd89d86bbb0faf0b21d51ab7a3eee33de78a250645b43e9fbf8876  resnet50_pipeline/qlinearadd_predesign.py
```

## P0-A dependency receipt

主线随后裁决 P0-A：

```text
R5_GAP_EXACT_UINT8_QUANT_TAIL
NO_UNCONDITIONAL_PURE_CONFIG_PROVEN
```

本族合同已绑定
`contracts/operator_config/exact_uint8_quant_tail_capability_v1.json`
SHA-256
`fb4805961fa13b50922005b916bbf22d58110dea370180fc83dfd0923b82cb7b`，
并验证首个共因反例：

```text
int32=400, multiplier=0x3d828f5c, zp=0
sequential FP32 multiply then RNE = 26
one-round fused magic = 25
```

影响保持 fail-closed：

- single-stage fused 仍不可裁决；
- two-stage explicit scratch 仍只证明结构可行，numeric tail 未闭合；
- fixed magic + `INT32_SUB(0x4b400000-zp)` 仍缺 GA rounding boundary、三 PE/四 lane
  placement、finite-domain bound、typed binding 和 mapper；
- 新增建议 `B_QADD_QUANT_TAIL_P0A_UNRESOLVED`，映射 P0-A 的 rounding/domain/division/
  topology/typed-binding/mapper blocker；不关闭任何 QLinearAdd blocker。

本轮未修改 plan、rules、RTL；未生成目标 JSON、mapping、bitstream、execplan、SCA、
服务器包；未检查或运行服务器。
