# Complete-JSON exact-stage family scope 公共修复同步

日期：2026-08-06

## 状态

`SUPERSEDING_FRESH_SHARED_EXACT_STAGE_SCOPE_DELTA_SYNCED /
MATMUL_EXACT_SCOPE_RERUN_DISPATCHED`

本记录完整取代同日ONNX identity合取原型；主线只保留一套current scope语义。

## 公共实现

- schema:
  `schemas/operator_config_complete_json_family_set_v1.schema.json`
  - SHA256:
    `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18`
- auditor:
  `tools/audit_complete_operator_json_family_set.py`
  - SHA256:
    `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1`
- tests:
  `tests/test_complete_operator_json_family_set.py`
  - SHA256:
    `3153a13f725e4cc96df1c71a7ab40cea121b00957ec0c552db1a2f9952ec17d0`

## Current语义

- manifest可选：

```json
{
  "family_scope": {
    "mode": "PINNED_EXACT_STAGE_IDS",
    "lowering_sha256": "<exact SHA256>",
    "expected_stage_ids": ["<non-empty unique IDs>"]
  }
}
```

- 存在时exact IDs是唯一选择器；`target_hw_op_types`只逐ID校验真实type。
- 不存在时保持`LEGACY_HW_OP_TYPE_SELECTOR`，报告显式记录
  `legacy_scope_compatibility=true / migration_recommended=true`，旧expected语义不变。
- lowering SHA/ID漂移、空/缺/重复ID、type错绑、scope外额外stage均fail closed。

## 规则

- current规则ID：
  `CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001`。
- 前版`CDA-COMPLETE-JSON-FAMILY-SCOPE-IDENTITY-001`已被替代，不保留双重语义。

## 验证

- `py_compile`：PASS。
- candidate + family public tests：20/20 PASS。
- MatMul exact controls覆盖：
  - 正控`hwop-0075-00/01`；
  - 缺`0075-01`；
  - 重复`0075-00`；
  - `0075-01` type错绑；
  - 额外Conv `hwop-0001-01`；
  - lowering SHA漂移；
  - stage ID漂移。
- `git diff --check`：PASS。

## 边界

- MatMul只更新family manifest并重跑family audit/final报告。
- candidate、ledger、strict JSON和current diff保持SHA不变。
- 其它八族legacy manifest继续有效，无需重写或重跑。
- 不生成mapping、bitstream、execplan、SCA或服务器包；无server动作。
