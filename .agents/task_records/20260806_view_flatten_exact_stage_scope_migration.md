# 2026-08-06 View/Flatten exact-stage family-scope migration

## Dispatch

- source task: `019fd276-14c5-7800-94db-87ebfb9ce632`
- unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- family: `view_flatten`
- action: migrate only the family-set selector to
  `PINNED_EXACT_STAGE_IDS`
- package/server authorization: none

## Read receipts

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` mutable provenance:
  `db3394a1f902bc7426fa791ae0574464e9f972678ea7980bcadad2efb1f42102`
- `.agents/rules/生成前必读索引.md`:
  `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6`
- `.agents/rules/算子配置规则.md`:
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- `.agents/rules/Flatten_View算子配置规则.md`:
  `f5c5ffbefb1e2515f0676fc5134bfeaf8ee1455562638f615a94e0fa598bc005`
- current family-set schema:
  `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18`
- current family-set auditor:
  `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1`

## Exact scope

Bound lowering:

- path: `contracts/resnet50_r5_lowering_bundle.json`
- SHA-256:
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`

Manifest scope:

```json
{
  "mode": "PINNED_EXACT_STAGE_IDS",
  "lowering_sha256": "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432",
  "expected_stage_ids": ["hwop-0073-00"]
}
```

The unique lowering identity is:

- `hw_op_id=hwop-0073-00`
- `request_id=r5:hwop-0073-00`
- `request_sha256=6ad8751fdab5f31fac84c8092964a60b6eab284e408aa458955cbddd0dab91e0`
- `node_id=node-0073`
- `onnx_name=flatten_473`
- `onnx_op_type=Flatten`
- `hw_op_type=View`
- `stage=view`

`target_hw_op_types=["View"]` is retained only as a per-ID type check. It no
longer constructs or expands the expected stage set.

## Changed artifacts

- family-set manifest:
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/view_flatten/family_set.json`
  - previous SHA:
    `b6d02072a018250971815e80e15a04ca761a3c13c72edfeae25a0673405b227f`
  - migrated SHA:
    `25cfc3cf46f3b59398a2f2aeddd7627f128082663dad25488fa6f460f6927bfb`
- fresh audit:
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/view_flatten/family_set_validation.json`
  - SHA:
    `96bc99cd51cc504b7694ea607dfe20acfcd2e608fa194acffe850560a11f8de9`
- migration report:
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/view_flatten/exact_stage_scope_migration_report.json`
  - SHA:
    `95dafb1aaba80a04bfee7e2ce84bd3609e7451927c48661819a4e8e3065b6cb8`

## Fresh audit result

- `pass=true`
- `scope_mode=PINNED_EXACT_STAGE_IDS`
- `legacy_scope_compatibility=false`
- `migration_recommended=false`
- `expected_stage_count=1`
- `covered_stage_count=1`
- exact-scope receipt:
  `hwop-0073-00 / View / Flatten / present=true`
- `errors=[]`
- `missing_stage_ids=[]`
- `unexpected_stage_ids=[]`

## Frozen assertions

The migration did not invoke the complete generator and did not rewrite the
following:

- no-config contract:
  `754af068effe0b80e3657b73d94380789e95f0c446cd7da9bdc823eb5bd02f60`
- 161-leaf ledger:
  `6e60a32c395dfed362f3fe6e8342df08f36ad67afdd055ff7a55f0fceee6fba9`
- handler matrix:
  `c3d450ddbb23e382d1c978c93cb0cae7d98c66fd47a2cf6902bafff8a9cc46a9`
- current-test diff:
  `fcabf28236c150619a4508947f673f2ae5d612ab15c9ca050b8cf7393925665f`

The following conclusions are unchanged:

- `METADATA_ONLY_ALIAS_NO_COMPUTE`
- hardware JSON count `0`
- current route:
  `UINT8 node0071D -> node0073 metadata View -> node0075A`
- byte coverage `32768`
- view offset `0`
- byte strides `[2048,1,1,1] -> [2048,1]`
- no mapping/bitstream/execplan/SCA generation
- accepted lifetime, actual reads, natural terminal and formal-D remain dynamic
  integration gates

## Rule feedback

`RULE_CONFIRMATION`:

`CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001` is
confirmed by this migration. The pinned lowering SHA and exact stage ID
produce one authoritative expected stage; the retained hardware type verifies
that exact identity without widening the family.

The current Flatten/View rules are also confirmed for the frozen
metadata-only/no-hardware-JSON and dynamic-lifetime claim boundary. No rule
delta is proposed.

## Package release

`PACKAGE_RELEASE=NOT_GENERATED_NOT_MODIFIED`

No mapping, bitstream, execplan, SCA, ZIP, upload, server execution or lease
was generated or performed.
