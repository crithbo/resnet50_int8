# QLinearMatMul/node0075 complete-JSON regeneration v1

日期：2026-08-06  
Owner family：`qlinear_matmul` / `QLinearMatMul node0075`  
上级任务：`019fd276-14c5-7800-94db-87ebfb9ce632`  
唯一主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
族级最终状态：`COMPLETE`（pinned exact-stage family scope `2/2` 覆盖通过）  
候选合同状态：`COMPLETE`（`pass=true`、`contract_valid=true`、`errors=0`、`completion_blockers=0`）

## 1. 边界与 current receipt

- 只生成全新 complete-JSON 分析/候选资产；未生成或修改 mapping、bitstream、execplan、SCA/SCA_D 或任何服务器测试包。
- 未修改 current v9 ZIP、current family config/golden/observer/runner、functional RTL、`.agents/plan.md`、公共规则或其他 family 资产。
- 未上传、未运行服务器、未取 lease。
- 禁止项扫描结果：artifact root 内 ZIP、`PREPARE_AND_RUN`、`TEST_PACKAGE_MANIFEST` 均为 `0`。
- 启动时完整读取 `.agents/agent.md`、当时 current `.agents/plan.md`、生成前必读索引、算子配置规则及索引路由的硬件字段、INT8 SA、精确 UINT8、Requant 与 native JSON 公共规则。
- final receipt：
  - `.agents/agent.md`：`32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
  - `.agents/plan.md`：`add16cbf259314ffc04948c4b268766f677d629901e148d970e37a8d99fdf4b0`（共享 mutable provenance；启动后由主线合法更新）
  - `.agents/rules/生成前必读索引.md`：`e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6`
  - `.agents/rules/算子配置规则.md`：`dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
  - complete-JSON policy：`de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746`
  - lowering bundle：`bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
  - public candidate validator：`4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
  - public family-set schema：`bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18`
  - public family-set auditor：`3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1`
  - public family-set tests：`3153a13f725e4cc96df1c71a7ab40cea121b00957ec0c552db1a2f9952ec17d0`
- RTL authority：`Trassic2.0_RTL@0ccae916ef61904a64d6cf8ec1d1931b45e428d8`。
- current 对照包只读消费：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_0cc_bankrow_v9.zip`，
  SHA256=`f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165`。

## 2. 全族 stage 覆盖

lowering bundle 中本族恰有两个 logical target stages：

1. `hwop-0075-00` / `MatMulInt32Accumulate`
2. `hwop-0075-01` / `RequantizeUint8`

物理物化覆盖为 `24` stages：

- accumulate：8 pass；
- FP32 scale：8 pass；
- exact UINT8 round/saturate：8 pass。

按 materialized-consumer signature 划分 `6` 个等价类：

- `accumulate_full128`：7；
- `accumulate_tail104_pad24`：1；
- `scale_full128`：7；
- `scale_tail104_pad24`：1；
- `round_full128`：7；
- `round_tail104_pad24`：1。

`stage_inventory.json` 对每个物理 stage 给出 op、dtype、shape、layout、qparams、padding/tail、DAG、lifetime、地址和地址 owner。最后一 pass 的 logical N 为 `104`、physical N 为 `128`、padding N 为 `24`；UINT8 tail padding value/zero-point 为 `60`。

## 3. authority 与 handler 能力边界

- 原生 FP16 GEMM/GEMV 仅为 `C` 级拓扑参考；其 pinned Git tree/commit/blob/pointer 已记录，未作为 INT8 numeric、dtype、shape、qparam、layout、lifetime 或地址 authority。
- 当前 MatMul/Scale/Round JSON 属于项目新增/untracked `D` 级对照资产，未标为 upstream authority。
- 本族 handler 为 `AUTHORIZED_PATCH`：
  - 对 24 个 exact target stage 的正控均通过；
  - exact replay、固定 target layout、固定 target cross-stage schedule 有覆盖；
  - shape、dtype、qparam、address 泛化均未声明；
  - shape、dtype、scale qparam、round qparam 四类越界负控全部 fail closed。
- 候选 `11,568` 个 leaves 均有一对一 provenance entry；`UNRESOLVED=0`。
- origin 只使用 `ADDRESS_PLANNER_DERIVED`、`ENCODER_DERIVED`、`EXPLICIT_DISABLED`、`MODEL_DERIVED`、`RTL_DERIVED`、`SCHEDULE_DERIVED`。
- `17` 个 composition boundaries 全部静态 resolved：1 个 node0071 A alias/eight-pass 输入边界、8 个 accumulate→scale、8 个 scale→round。静态 composition 不声称服务器 actual ordering/barrier。

## 4. candidate 与 current v9 逐 leaf 对比

总 leaves：`11,568`。

- `SAME`：`11,432`
- `INTENTIONAL_DERIVATION`：`16`
- `SUSPECTED_CURRENT_DEFECT`：`120`
- `NEW_CANDIDATE_DEFECT`：`0`

候选修正只发生在 8 个 accumulate stage：

1. current stream1 `buf_spatial_stride=[0,1,0,1,...]` 改为唯一 byte lane `[0..15]`。  
   current 重复地址会在 `Memory_Req_Manager` ascending bank-byte 写入中形成 last-writer-wins；SA 的行/列广播发生在完整 Buffer row 之后，因此重复 MSE byte 地址不是合法广播。
2. current ping-pong peer lifetime `buffer0=1, buffer1=16` 改为 `16/16`。每个 weight panel 服务 16 个 M rows，peer lifetime 必须一致。
3. inactive write stream2 的 `mem_idx_mode[2]` 与 `mem_idx_keep_last_index[2]` 从整数 `0` 规范化为 explicit `null`，共 16 leaves。

候选 24/24 strict JSON 全部通过。三类 current 反例负控分别精确触发：

- `STREAM.SPATIAL_ALIAS`
- `VALUE.ENUM`
- `BUFFER.PINGPONG_PAIR_MISMATCH`

卡点归因：

- v5 的旧 `0x01706400` invalid bank/row 停在 node0075 stage00 之前；v9 已做低 bank-row relocation。本候选 lane/lifetime 修正不能解释已观察到的 v5 停机，故该历史卡点为 `CONFIG_EXCLUDED`。
- lane/lifetime 是 v9 将来进入 accumulate 后的 `CONFIG_CONTRIBUTES` 风险。
- producer acceptance→pass00 first read、实际 8-pass/8192×32B accepted reads 与 hash、natural terminal、144 formal D 均为 `DYNAMIC_ONLY`，静态 JSON 不冒充 actual 证据。

## 5. fresh validator 结果

公共 candidate validator：

- report：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinear_matmul/candidate_validation.json`
- SHA256：`7373ccc930ec9b622949c7b482b29ce847575c3fdc671ca9dcb3104727afc951`
- `candidate_status=COMPLETE`
- `pass=true`
- `contract_valid=true`
- `blocked_valid=false`
- `errors=0`
- `completion_blockers=0`
- candidate leaves=`11,568`，ledger leaves=`11,568`

本地组合验证：

- report：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinear_matmul/local_validation.json`
- SHA256：`ee46e50deb1ae96d7f980b0264278bf6fc9ed60cd0eb3ba47a5e604b6c6dea45`
- strict/schema/handler/formula/negative-control 均 `PASS`
- forbidden outputs=`0`

公共 family-set auditor：

- exact manifest：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinear_matmul/family_set.json`
- manifest SHA256：`a54800f1d115248d96c14a04e54979281f013a83c59184ce86d20865617eab43`
- `target_hw_op_types=["MatMulInt32Accumulate","RequantizeUint8"]`
- 本族合同不含、也不需要包含 `ConvInt32Accumulate`。`hwop-0075-00` 的真实 type 是
  `MatMulInt32Accumulate`；`hwop-0075-01` 的真实 type 是 `RequantizeUint8`。
- `family_scope.mode=PINNED_EXACT_STAGE_IDS`
- `family_scope.lowering_sha256=bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- `family_scope.expected_stage_ids=["hwop-0075-00","hwop-0075-01"]`
- report：
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinear_matmul/family_set_audit.json`
- SHA256：`cdcdd8391599a99d35207c4d93b62daa40c758d4c3a4a080537ed863afa2b904`
- `pass=true`
- `scope_mode=PINNED_EXACT_STAGE_IDS`
- `legacy_scope_compatibility=false`
- expected/covered=`2/2`
- missing/duplicate/unexpected/errors 均为空。
- exact receipts：
  - `hwop-0075-00 / MatMulInt32Accumulate / QLinearMatMul`
  - `hwop-0075-01 / RequantizeUint8 / QLinearMatMul`

六类 exact 负控由 public final logic
`test_matmul_exact_scope_requested_positive_and_negative_controls` 执行并全部 fail closed：

1. 缺 `hwop-0075-01`
2. 重复 `hwop-0075-00`
3. `hwop-0075-01` type 错绑
4. 额外 Conv `hwop-0001-01`
5. lowering SHA 漂移
6. stage ID 漂移

## 6. 输出身份

根目录：
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinear_matmul/`

- `candidate_contract.json`：`ee2a6289ca8992b31188d3ed32095a571542e817e78a25e2d298a6e4741d3156`
- aggregate complete JSON：`beca4d05644ae42c102c57ed0a7cf199ff4b6315b64227edda107622f6e4530e`
- `field_provenance_ledger.json`：`4b9323c2b2244ea3f8fbc5f6325f4ee6e9cd8ae8f4f73727cd2238e3f262a003`
- `reference_applicability.json`：`65179ac894f962697a3866755874e20ed05f62af70c7859b73799474a23c7b92`
- `handler_capability.json`：`15e4d5c53dee0731c0c67a3a920da5c64e2e95e035d0747f92ae5ea6dd7f6e01`
- `current_test_diff.json`：`043bbce1864fb7f3a36f538ccf2f731450bf480c813fbffd027cfc54c4c37fdf`
- `composition_boundary.json`：`b1e41020704ab84e9b1aa3e7f865f079016846b8c12865446a251f3c89d28c43`
- `family_set.json`：`a54800f1d115248d96c14a04e54979281f013a83c59184ce86d20865617eab43`
- `report.json`：`7802ea219c529b4e6393b11699f4a33099dbd1216f681943a84a3f79e69be9a7`

owner tools：

- `tools/build_qlinear_matmul_complete_json_regeneration_v1.py`：
  `1ca9cb8030c6ed8a3cc9846e871a80e57a6b9949fef641a362d22bbd35b211cf`
- `tools/validate_qlinear_matmul_complete_json_regeneration_v1.py`：
  `c16ccd63e3641ead718f9246f5163229dc33a9327d4adb780472f7cca64c4e08`

## 7. 规则反馈

`RULE_CONFIRMATION`：

- ID：`CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001`
- 权威 selector 已在 manifest 中实现为
  `expected_stage_ids=["hwop-0075-00","hwop-0075-01"]`，并把该集合绑定
  lowering SHA256=`bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`。
  `target_hw_op_types` 继续负责每个 ID 的真实 type 绑定，不再单独承担 family
  membership 选择。
- selector 必须验证：
  1. 每个 expected ID 在 pinned lowering 中恰好存在一次；
  2. candidates 与 no-config receipts 对 expected set 恰好覆盖一次；
  3. 每个 ID 的实际 `hw_op_type` 被对应 candidate contract 声明；
  4. 不允许 candidate/no-config receipt 包含 expected set 之外的 stage。
- 最小负控：
  - 删除 `hwop-0075-01` → missing stage，fail closed；
  - 重复 `hwop-0075-00` → duplicate coverage，fail closed；
  - 把 `hwop-0075-01` 错绑成 `MatMulInt32Accumulate` → type mismatch，fail closed；
  - 加入 Conv 的 `hwop-0001-01` → unexpected/cross-family stage，fail closed；
  - lowering SHA 漂移或 expected ID 重命名/消失 → authority identity mismatch，fail closed。
- 证据：本族 node-scoped coverage 为 `hwop-0075-00`、`hwop-0075-01` 恰好各一次；公共 auditor 却要求 `55` stages 并列出其他 family 的 `53` 个缺失项。

公共 exact-stage scope 已关闭原 family selector blocker；族级交付为 `COMPLETE`。
候选本身继续保持无 unresolved leaf、无 handler capability blocker、无结构错误。
