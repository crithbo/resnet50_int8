# Complete-JSON family scope identity 公共修复同步

日期：2026-08-06

## 状态

`SUPERSEDED_BY_EXACT_STAGE_SCOPE_DELTA`

本记录中的ONNX identity合取原型已由同日后发的pinned lowering SHA +
`PINNED_EXACT_STAGE_IDS`实现取代。前版三个公共文件SHA及
`CDA-COMPLETE-JSON-FAMILY-SCOPE-IDENTITY-001`不再是current，不得用于MatMul
最终重验；current身份见
`.agents/task_records/20260806_complete_json_exact_stage_scope_fix_sync.md`。

## 真实反例

QLinearMatMul candidate覆盖：

- `hwop-0075-00 / MatMulInt32Accumulate`
- `hwop-0075-01 / RequantizeUint8`

旧family auditor只按
`target_hw_op_types=[MatMulInt32Accumulate,RequantizeUint8]`从全图选择，
因此把其它53个QLinearConv的`RequantizeUint8` stage误纳入expected set。candidate
本身`COMPLETE`，但family被伪判missing=53。

## 公共实现

- schema:
  `schemas/operator_config_complete_json_family_set_v1.schema.json`
  - SHA256:
    `e667def92204c799f3bf62b1663b574de711c0a20597e4c02fd551b3b5734aa0`
- auditor:
  `tools/audit_complete_operator_json_family_set.py`
  - SHA256:
    `4d05860b328ec682cb28d8d16af0a29d8100d987889892e374ff8e9d57a1356d`
- tests:
  `tests/test_complete_operator_json_family_set.py`
  - SHA256:
    `45efa543452853e4fc35c99f46a6795e67f06c75bd8dd75d5946810ab18ab658`

## 新语义

- family-set manifest可选声明非空唯一的`target_onnx_op_types`。
- 不声明时，继续保持原有`target_hw_op_types`选择行为；既有八族manifest与历史报告
  不静默变义。
- 声明时，expected set从绑定lowering bundle按以下合取重算：

```text
hw_op_type in target_hw_op_types
AND
onnx_op_type in target_onnx_op_types
```

- `target_hw_op_types`继续只做真实target stage type登记，不包含内部复用source
  primitive。
- 空选择、candidate identity/type错绑、missing、duplicate、unexpected均fail closed。

## 规则同步

- `CDA-COMPLETE-JSON-FAMILY-SCOPE-IDENTITY-001`已窄幅合入：
  `.agents/rules/算子配置规则.md`
  - SHA256:
    `46d9ef0e26fd183c52ed0f91c810a3040e6b8fa1f9c20933123dd6f6a7f2e280`
- 生成路由已合入：
  `.agents/rules/生成前必读索引.md`
  - SHA256:
    `f10cb321b40a82c0e6c9f9e559acf4ad900de957b81fdd42924a62b09811809d`

## 验证

- `py_compile`：PASS。
- candidate + family tests：13/13 PASS。
- 新正/负控覆盖：
  - shared hardware primitive只按hw type时可重现跨族missing；
  - hw/ONNX identity合取后精确通过；
  - ONNX identity selector选择为空时fail closed。
- `git diff --check`：PASS。

## 边界

- MatMul只允许在原family manifest增加
  `target_onnx_op_types=["QLinearMatMul"]`并fresh重跑family audit。
- 不重建candidate、JSON、mapping、bitstream、execplan或SCA。
- 不生成/修改服务器测试包，不上传、不运行、不取lease。
- 其它八族manifest无需重写；只有因其它原因fresh重验时才按changed-surface适用性
  补齐。
