# 常态触发式因果观测 v1 主线同步收据

日期：2026-08-06  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
来源 owner：`019fd276-14c5-7800-94db-87ebfb9ce632`

## 同步结果

以下规则语义已进入主工作区：

- `CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001`
- `CDA-WHOLE-NET-ONE-ROUND-OBSERVABILITY-COMPLETENESS-FIRST-001`

适用范围保持为下一份实际进入 DUT simulation 的 fresh successor；当前冻结包不因本规则
追溯重建。观测完整性和单轮候选判别优先；50% slowdown 仅为非阻断工程偏好。v1
no-progress 只触发有界快照，不自动终止仿真。

## 主工作区身份

| artifact | SHA-256 |
|---|---|
| `.agents/rules/服务器测试包生成规则.md` | `4ff581d2add191c6345948489b90d3ccaa43fcae9c31eab8b75bcc99fae2de0b` |
| `.agents/rules/整网测试收敛优化专项规则.md` | `e7c760305c334a277c04806e53a673d9c2a0e539159d667d22f4a24a1adf67bd` |
| `.agents/rules/生成前必读索引.md` | `3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc` |
| `schemas/server_triggered_causal_observability_v1.schema.json` | `98416b147767555441390b42744c033d3688b2eb403301020b21023b13aa188e` |
| `contracts/server_triggered_causal_observability_registry_v1.json` | `89dd8e879078e8cbbde4069fc132d398fea8e14836a6f9e40c70640b01231831` |
| `contracts/server_triggered_causal_observability_current_five_v1.json` | `82a6a9166f055a209557d23ac4aed9dd8f7b7566022037ac9748a5e223c8708a` |
| `tools/validate_server_triggered_causal_observability.py` | `c8f688ff3b4ec28bbea372fb59a803e88ea75556f916351662979a158fe621e4` |
| `tests/test_server_triggered_causal_observability.py` | `bb23d1995b3fc210c3bddf6ba5fb696f16973c62c3c36f8699cb091d6366b27d` |
| `artifacts/operator_config_validation/r5-triggered-causal-observability-v1/report.json` | `8a83588236344f6656d6600617c6ccd10487a273880a89bb47a117bd812bb610` |

主线 `生成前必读索引.md` 保留了同步期间已经存在的 complete-JSON/exact-stage 并行增量，
因此采用上述主线 SHA，不以覆盖整文件的方式强求专项隔离副本 SHA。

## 验证

- `validate ... validate`：exit `0`，`valid=true`，`errors=[]`
- 专项测试：14/14 PASS
- `py_compile`：PASS
- `git diff --check`：PASS

专项隔离 worktree 中的 combined 26/26 还包含两个 shadow-only 测试模块；它们尚未合入
主线生成路径，主工作区未冒充复跑该 12 项。该边界不影响本次共享合同与14项专项门。

## 边界

本次没有修改 current ZIP、mapping、bitstream、execplan、SCA、functional RTL 或服务器
状态，没有上传、运行或取 lease。五份公共 profile 仍为
`DESIGN_READY_BINDING_AND_CALIBRATION_PENDING`、`release_eligible=false`；fresh family
必须完成 exact final HDL、owner clock/reset、actual consumer/predicate 与性能收据绑定后，
才可由原 family final-ZIP validator 裁决发布。
