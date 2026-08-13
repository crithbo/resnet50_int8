# MaxPool node0002 complete-JSON exact-stage scope migration

## Scope

- Family: `maxpool_uint8`
- Authorized change: migrate only the family-set selector from legacy `target_hw_op_types` inference to current `PINNED_EXACT_STAGE_IDS`.
- Prohibited and not performed: candidate/current-v5/current-diff/padding mutation; mapping, bitstream, execplan, SCA, ZIP, server action, plan/public-rule/functional-RTL/other-family changes.

## Current authority

- Family-set schema: `schemas/operator_config_complete_json_family_set_v1.schema.json`, SHA256 `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18`.
- Family-set auditor: `tools/audit_complete_operator_json_family_set.py`, SHA256 `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1`.
- Lowering bundle: `contracts/resnet50_r5_lowering_bundle.json`, SHA256 `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`.
- Target request: `r5:hwop-0002-00`; identity `hwop-0002-00` / `node-0002` / `MaxPool` / `MaxPoolUint8` / `pool`; request SHA256 `6126a69fcd131b9fe3e12450acb2d54c5b6f93e91779a44150bf302ece018578`.

## Migration

- Manifest: `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/maxpool_uint8/family_set.json`.
- Before SHA256: `f4dba082192bbb425fcd4cbf693815cb8b606a88205f5319dffc2f38a282809c`.
- After SHA256: `45a98041893526f5bf9466168371523a0d23c264e8c9c9ef80bdc2564a464729`.
- Added only:
  - `family_scope.mode=PINNED_EXACT_STAGE_IDS`
  - `family_scope.lowering_sha256=bf661e4e...45432`
  - `family_scope.expected_stage_ids=[hwop-0002-00]`
- `target_hw_op_types=[MaxPoolUint8]` remains only as the per-pinned-ID hardware-type check.

## Fresh validation

- Audit: `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/maxpool_uint8/family_set_audit_report.json`, SHA256 `6a2649aeba2249ad724aececf53701fc7525875c8485e4df63aaf2ac0fa42418`.
- Result: `pass=true`; `scope_mode=PINNED_EXACT_STAGE_IDS`; expected/covered `1/1`; `errors=[]`; `missing_stage_ids=[]`; `unexpected_stage_ids=[]`; exact receipt is `hwop-0002-00 / MaxPool / MaxPoolUint8`.
- Current candidate validator: exit `0`, `candidate_status=COMPLETE`, `pass=true`, `errors=[]`, `completion_blockers=[]`.
- Shared regression: `tests.test_complete_operator_json_candidate` + `tests.test_complete_operator_json_family_set`, 20/20 PASS.
- Exact-scope negative controls covered by the shared regression include lowering-SHA drift, missing/duplicate/drifted stage ID, cross-family extra stage, and hardware-type mismatch; all fail closed.
- Forbidden downstream artifacts under the MaxPool complete-JSON artifact root: `0`.

## Frozen assertions

- Strict candidate JSON SHA256 `0348ead26469b8ebda0df03979d38f8436bc9f1f6903bafed078b0547d682335`.
- Candidate contract SHA256 `0096f0f507a3ad7281c07d443c548e1786a47cbf6820f0a1b194972d298518d6`.
- Current v5 consumed config SHA256 `b1d0bb4e8f0aeb59253dfc2b3e73c3731f7b4bb1712998ccb845fa34c34f6c77`.
- Current diff SHA256 `eff77c32fa844b94d51a0ca5963bcf41430bde25d40f3d06ea06bb54fd983e09`.
- The only non-`SAME` leaf remains `/stream_engine/stream0/padding_reg_value`, current `null` to strict `0`; canonical tuple SHA256 `09f5f72a48d65c3f044337c9e625122f96cc2aa7bef22477c3ddb4000fefe7f1`.
- Padding RTL current receipt SHA256 `3228e677cb1c7767e0ee68256db524e6ee9d25ff648916f1b05a6d4a46650e75`.
- Tool-rule coherence report SHA256 `c1fa7ec76862204d06512841a184f55f3fe3cedd728a4365edd51160bc05e556`, `status=PASS`, `errors=[]`.
- Tool-rule task record SHA256 `ffe6d34d8d77a425ad2bc1b2c91deefc8a398f3c885cd1b4cd26ba9dc87a7cc0`.

## Machine report

- `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/maxpool_uint8/exact_stage_scope_migration_report.json`
- bytes `6035`
- SHA256 `c87b33a7af598b1ef2f26d8ee8ce93c18d5ad2692b5495a099cdba123f413dc4`

## Disposition

- MaxPool complete-JSON family remains `COMPLETE`.
- `PACKAGE_RELEASE=NOT_APPLICABLE_NO_PACKAGE_TASK`.
- No rule delta proposed.
