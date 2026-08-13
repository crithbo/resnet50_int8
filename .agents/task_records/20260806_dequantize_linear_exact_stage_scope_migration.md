# DequantizeLinear complete-JSON exact-stage scope 迁移

日期：2026-08-06  
上级任务：`019fd276-14c5-7800-94db-87ebfb9ce632`  
唯一主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
状态：`EXACT_STAGE_SCOPE_MIGRATION_COMPLETE`

## 1. 迁移结论

只将
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set.json`
从 `LEGACY_HW_OP_TYPE_SELECTOR` 迁移为 `PINNED_EXACT_STAGE_IDS`。

current lowering：

- path：`contracts/resnet50_r5_lowering_bundle.json`
- SHA256：
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`

从 current lowering 实际读取并唯一核实：

| stage ID | hw_op_type | onnx_op_type | request SHA256 |
|---|---|---|---|
| `hwop-0072-00` | `DequantizeLinear` | `DequantizeLinear` | `22657270d4f617aaa60795575aa0ca21bd5125de775b12e46e47648587f23746` |
| `hwop-0077-00` | `DequantizeLinear` | `DequantizeLinear` | `cb8522a4ba2386ce3c303f5de274b2fa2e130d719c09933c686a11d28d9b7f63` |

`target_hw_op_types=["DequantizeLinear"]` 只用于上述两个 exact ID 的逐 ID type
绑定，不再从 hw type 扩张 family scope。

## 2. current 收据

完整复读：

| path | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md`（mutable provenance） | `db3394a1f902bc7426fa791ae0574464e9f972678ea7980bcadad2efb1f42102` |
| `.agents/rules/生成前必读索引.md` | `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6` |
| `.agents/rules/算子配置规则.md` | `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820` |
| `.agents/rules/DequantizeLinear算子配置规则.md` | `f8cf7d2a041426f2b3348f3d02b570e3e559fe1a77c643a8393e77a2583e15a1` |
| `schemas/operator_config_complete_json_family_set_v1.schema.json` | `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18` |
| `tools/audit_complete_operator_json_family_set.py` | `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1` |

废止的 `target_onnx_op_types` 路线未使用。

## 3. current manifest 与 fresh audit

manifest：

- SHA256：
  `a3bf2365551f7f74d386cf276b8ec1f7f1131a310d59d7567a67504e8ef3a199`
- `family_scope.mode=PINNED_EXACT_STAGE_IDS`
- `family_scope.lowering_sha256=bf661e4d...5432`
- `expected_stage_ids=[hwop-0072-00, hwop-0077-00]`

fresh audit：

- path：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set_exact_stage_scope_audit.json`
- SHA256：
  `65234e0bc916af497a032ca24197a8deb39aa3e70a19441fc9bde587d429ab04`
- command：

```text
<workspace-python> tools/audit_complete_operator_json_family_set.py \
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set.json \
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set_exact_stage_scope_audit.json
```

- exit code：0
- `pass=true`
- `scope_mode=PINNED_EXACT_STAGE_IDS`
- `legacy_scope_compatibility=false`
- `migration_recommended=false`
- expected=2，covered=2
- `errors=[]`
- `missing_stage_ids=[]`
- `unexpected_stage_ids=[]`
- 两 candidate report 均 `pass=true`、`contract_valid=true`、
  `completion_blockers=[]`、`errors=[]`

迁移报告：

- path：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/dequantize_linear/family_set_exact_stage_scope_migration_report.json`
- SHA256：
  `a39401c122e94285f6adb76e74f1689decbd19627930e5be4b01de4174721ce5`

## 4. 冻结资产断言

本轮没有重建或修改以下资产：

| asset | SHA256 |
|---|---|
| node0072 candidate JSON | `317f263033d5789988ba7d50985bb166c0df7fb35425b51109ca049efb61e390` |
| node0077 candidate JSON | `1235ef420360750b22cba37d72029e555db7c50c069be8ed741ebf747ca23632` |
| node0072 candidate contract | `c56ba06bf2b6ebbd412ac52f4fa1cb51f667f5fa291e70b943df48f67c8a8935` |
| node0077 candidate contract | `998cef009940c9e3389c937bbe74afeb242c24885bc7c7422f3a7822d75924ce` |
| node0072 field ledger | `3887206aef0dd2a293a66205900cbf611035686dacdcbde0c36311f470910c11` |
| node0077 field ledger | `6d963023cd5ca416dedd610a10313412428f1058eab6e786170fe67159197168` |
| node0072 current diff | `34e97fe52ce5dbf912db27528928aec2b273d8546697cd6b0babe1b46e57b2d9` |
| node0077 current diff | `0cd01d5def1f12f3282013b4335bff27a906f36d9ee6b0ee5d027cc8b5cba66c` |
| 原 complete-JSON report | `8bb7199fd8c86afccf62601cac67b89af5503cb4426ee83c6f2b3fdc5981cae5` |

因此：

- candidate leaves 保持 416+416=832；
- `UNRESOLVED=0` 保持；
- node0072 candidate ↔ current final：416 `SAME` 保持；
- node0077 candidate ↔ current final：416 `SAME` 保持；
- node0077 E4/E5 历史证据保持冻结且未重跑：
  - E4 task SHA：
    `e7fe4ceaf9a9581b68b5ddf16d57f7bc19a9f5ee6a34aa4b4b9235f16c81cc28`
  - E5 task SHA：
    `96ddaeaacfecb6d7d2b3dff4be4ab5b37ef69ea0f47f8a1633893a5f02141556`
- 原 complete-JSON report 字节保持不变；其中旧 manifest receipt 作为历史，
  current scope receipt 由本迁移报告接替。

## 5. 结构化回传

### RETURN_ANALYSIS

- status：`EXACT_STAGE_SCOPE_MIGRATION_COMPLETE`
- family：`dequantize_linear`
- scope：`PINNED_EXACT_STAGE_IDS`
- exact stage coverage：2/2
- errors/missing/unexpected：0/0/0
- repeated numeric analysis：false
- candidates/leaves/current diff/E4/E5：全部冻结复用

### BLOCKER_DELTA

`NO_CHANGE`。该 selector 迁移不关闭或新增 production、integrated、formal 或 dynamic
blocker。

### RULE_DELTA_PROPOSAL

`NONE`。current exact-stage schema/auditor 已充分裁决。

### PACKAGE_RELEASE

`NONE`。没有生成 mapping、bitstream、execplan、SCA/SCA_D、ZIP 或服务器资产；
没有上传、运行、lease 或服务器检查。

### claim boundary

本轮只迁移 Dequant family-set 的选择器与 fresh family audit。它不改变两个 candidate、
832 leaf provenance、current-final SAME、node0077 E4/E5、数值结论、后端产物或任何
服务器状态。
