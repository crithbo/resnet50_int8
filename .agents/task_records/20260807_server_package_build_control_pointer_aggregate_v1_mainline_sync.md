# SERVER_PACKAGE_BUILD_CONTROL_V1 mainline sync

Date: 2026-08-07

Status: `IMPLEMENTED_MAINLINE_SHADOW_ONLY_NEXT_FRESH`

## Scope

- Narrowly merged the shared causal blocking classification, one-pass aggregate build control,
  and current-family pointer semantics into the current mainline rules.
- Preserved the install-only V2 runtime-layout rule and all parallel rule edits.
- Did not edit `.agents/plan.md`, rebuild or mutate a current ZIP, rotate package storage,
  change a family release, or perform any server action.

## Current rule receipts

- `.agents/rules/服务器测试包生成规则.md`
  SHA256 `89d27141f1a151ef5e6cc98603238050c9b0442a3d1937b2ec23cf92e55a27a2`
- `.agents/rules/生成前必读索引.md`
  SHA256 `3c2bd9017f351b6456eac49c966063cc9b76e96420d71162a1ca57d1b62b552c`
- `.agents/rules/整网测试收敛优化专项规则.md`
  SHA256 `12340cd5e619e1923c74e8853006ee21bce8a7a07b0538e9a5196d7800638cd7`

Implemented rule IDs:

- `CDA-SERVER-PACKAGE-BLOCKING-CAUSAL-CLASS-001`
- `CDA-SERVER-PACKAGE-CURRENT-FAMILY-POINTER-001`
- `CDA-WHOLE-NET-CURRENT-FAMILY-POINTER-AND-PLAN-DRIFT-001`
- `CDA-WHOLE-NET-BLOCKING-CAUSE-OR-RECORD-ONLY-001`
- tightened `CDA-SERVER-PACKAGE-AGGREGATE-PREFLIGHT-001`

## Validation

- Combined unit tests:
  `tests.test_server_package_pipeline`,
  `tests.test_current_family_pointer`,
  `tests.test_current_pending_one_return_matrix`,
  `tests.test_server_package_runtime_layout`
  = 24/24 PASS.
- `py_compile` PASS for the shared build-control, pointer, one-return matrix, runtime-layout,
  and exact-ZIP layout validator tools.
- `git diff --check` PASS.

## Current pointer

Machine pointer:
`artifacts/operator_config_validation/r5-server-package-build-control-v1/current_family_pointer.json`

- bytes: 5467
- SHA256: `1f275ea4e1f6a0974b6e80baab1c3061161ccd7c16b91eaa9d9b23a30571ff90`
- pointer ID: `1ef7e4c031c3feeff5b4931cad6f8fd30926d2ff6a0efce4487e68f7e65e653f`
- pass: true
- exact current packages:
  - `r5_n4_0cc_p16_b5port`
  - `r5_n4_hw_v61_lcmap_argv_fix`
  - `r5_n71_gap_v48_multislice_pipeline_diag`
  - `r5_qadd_n7_fullchain_v45`
- plan coherence: false, record-only; no plan edit, package hold, or rebuild.

The historical one-return matrix still binds native Conv p15. Its fresh read-only audit correctly
fails on storage-index and native-package drift; it is retained as historical evidence and is not
promoted as a current p16 matrix.

## Claim boundary

The shared control remains `SHADOW_ONLY_NEXT_FRESH`. This receipt proves local rule/tool/schema/test
coherence and current pointer selection only. It does not prove family package correctness,
production compile/simulation, natural terminal, formal D, E3/E4/E5, or server execution.
