# GlobalAveragePool complete-JSON exact-stage scope migration

- date: `2026-08-06`
- owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- upper task: `019fd276-14c5-7800-94db-87ebfb9ce632`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `COMPLETE_EXACT_STAGE_SCOPE_MIGRATION`
- package action: `NONE`

## Current receipts

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` (mutable provenance only):
  `db3394a1f902bc7426fa791ae0574464e9f972678ea7980bcadad2efb1f42102`
- `.agents/rules/生成前必读索引.md`:
  `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6`
- `.agents/rules/算子配置规则.md`:
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- family-set schema:
  `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18`
- family-set auditor:
  `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1`

## Exact lowering identity

Bound lowering:

- path: `contracts/resnet50_r5_lowering_bundle.json`
- bytes: `1971200`
- SHA256:
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`

The two IDs each occur exactly once:

- `hwop-0071-00 / GlobalAverageSumInt32 / QLinearGlobalAveragePool / node-0071`
- `hwop-0071-01 / AverageRequantizeUint8 / QLinearGlobalAveragePool / node-0071`

The manifest now uses:

```text
family_scope.mode=PINNED_EXACT_STAGE_IDS
family_scope.lowering_sha256=bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432
family_scope.expected_stage_ids=[hwop-0071-00,hwop-0071-01]
```

`target_hw_op_types` remains
`[GlobalAverageSumInt32,AverageRequantizeUint8]` and only checks each pinned
ID's actual type; it no longer defines or expands the family membership.

## Fresh audit

Command:

```powershell
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
  tools/audit_complete_operator_json_family_set.py `
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/global_average_pool/family_set.json `
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/global_average_pool/family_set_audit.json
```

Result:

- exit: `0`
- `pass=true`
- `scope_mode=PINNED_EXACT_STAGE_IDS`
- `legacy_scope_compatibility=false`
- expected/covered: `2/2`
- `missing_stage_ids=[]`
- `unexpected_stage_ids=[]`
- `errors=[]`
- both candidate reports remain `pass=true / contract_valid=true`.

Artifacts:

- manifest bytes/SHA:
  `1126 /
  a361e8d9f3d5d8a1aae5874f60e2095dc018320314122d6061627082653c9463`
- audit bytes/SHA:
  `2721 /
  115c69bd85f4f4f4b0bc4da67bdc23204d7f5c5fbf2de19187a73fe2096a9af1`
- migration report bytes/SHA:
  `6012 /
  650e45b67045ca1626e59a502faaee4124ef0980143b7fc80f40794dfa1cbdb6`

## Frozen assertions

No candidate, provenance, strict config, current diff, numeric, sum/tail,
workload, config, golden, mapping, bitstream, execplan, SCA, package, RTL, plan,
or public-rule bytes were changed by this migration.

- sum contract/candidate:
  `07d9b1b16d4ead79037b3faf1830d01ab790fda188b9114569e4b3bf75b21e0f /
  f9862b2ce862bfdabe72aa9a90fc98603ca0b05955283c5d862f744a87c33871`
- average/requant contract/candidate:
  `ebc90cbf070b6e1033eac600f5e4fcc08da06152387eceb3be928fed02614c49 /
  7979612756cbffa30c755c7a15e13a0363be9c235ad10ee757be085cb61f8461`
- 3754-leaf family ledger:
  `0adffeed4af57fac517929786ed7b0b515f3693644c748c2f47029a5761e5d1f`
- current-test diff:
  `7dfc97d3a0250fa8e9a57495d7a940236bf56ab171cba9b231bc8ed529144894`
- eight strict JSON SHA set:
  `e6d8f97103a2f224b5630472444169793d06ebfd3e8e7e03c507bb2755bd38c1`,
  `56fa8c40412b2c749f5964481a1f4e88dce0ed338044c91e3841cd7562b27291`,
  `64406bd4f635e1251dc5f0ea548b1c4f4851224af23e2a2489bc985f6f82c1cb`,
  `1fa03f104a391a7dee4d598f75d533010c8143b8c7c863e28e5cb4b2f556f6eb`,
  `bb1ee7813624dc2ce94a2a4e3b3bb691d7cfdc1c3c4f00e551432e4b5e51fed5`,
  `35b236a2d2baf75e1b692eb375e04b0b976e8a891ded0af576168f143f02aa94`,
  `b3bea50e017a4da6ea5a89b3563240c69bccb16ea9d28ff7a76d25c2b69d4609`,
  `b2969efd8c32ddd616b25676748594b1d7c811f1d8c0bb05927dd663b38881a0`.

The existing current-v40 conclusion remains unchanged: all 3754 candidate
leaves, all eight encoded configs, the execplan, and final-D index/coverage are
byte-equal; no current configuration difference explains the open dynamic
stall.

## Rule feedback and boundary

`RULE_CONFIRMATION`:
`CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001` correctly
binds family ownership to an immutable lowering document and exact stage set,
while using hardware types only as per-ID checks.

`RULE_DELTA_PROPOSAL=NONE`.

This migration is a static family coverage receipt only. It does not promote
the existing `CONFIG_ONLY_CORRECTNESS_BASELINE`, close natural-terminal/formal-D
blockers, or establish E3/E4/E5.
