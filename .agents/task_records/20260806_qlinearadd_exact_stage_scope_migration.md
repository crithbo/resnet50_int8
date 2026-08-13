# QLinearAdd complete-JSON exact-stage scope migration

Date: 2026-08-06

Owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`

Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

Upstream task: `019fd276-14c5-7800-94db-87ebfb9ce632`

## Outcome

Only the QLinearAdd `family_set.json` scope was migrated from
`LEGACY_HW_OP_TYPE_SELECTOR` to `PINNED_EXACT_STAGE_IDS`. The current lowering
bundle is pinned by SHA-256 and the ordered list contains exactly the 17
QLinearAdd stages already covered by the frozen candidate contract.

Fresh family audit result:

```text
scope_mode=PINNED_EXACT_STAGE_IDS
expected_stage_count=17
covered_stage_count=17
missing_stage_ids=[]
unexpected_stage_ids=[]
scope_errors=[]
```

The audit exits `1` and overall `pass=false` only because the sole candidate is
the existing legal capability-blocked candidate:

```text
contract_valid=true
blocked_valid=true
candidate_errors=0
completion_blockers=135598
```

This is expected fail-closed behavior, not a family-scope error and not a
promotion to `COMPLETE`.

## Current identities

| Item | Bytes | SHA-256 |
|---|---:|---|
| `schemas/operator_config_complete_json_family_set_v1.schema.json` | 2,719 | `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18` |
| `tools/audit_complete_operator_json_family_set.py` | 13,363 | `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1` |
| `contracts/resnet50_r5_lowering_bundle.json` | 1,971,200 | `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432` |
| migrated `family_set.json` | 1,138 | `4eaad42c0c4108e44f7e7cbfec3a0cac2a64a4f651d4a9f16c39454e1a008e75` |
| fresh exact-stage audit | 21,086,978 | `a2e56f503b93a39c7cc95ff99a1477311712065df1cc60dac5811d26690750ef` |
| migration machine report | 10,250 | `5fb06a11bbc5199a4d682d35f45e14fb46738a60af2e91473fec8766eb4b5ba9` |

Manifest pre-migration identity:

```text
bytes=577
sha256=7c3082340700f1ab40bb6a6bf2e0422dd4e1a8bb7a86e2e70bfbb3730e546db9
```

The only changed manifest surface is `/family_scope`.
`target_hw_op_types=["QLinearAddUint8"]` is unchanged and now serves only as
the per-ID type binding.

Ordered exact stage IDs:

```text
hwop-0007-00
hwop-0011-00
hwop-0015-00
hwop-0020-00
hwop-0024-00
hwop-0028-00
hwop-0032-00
hwop-0037-00
hwop-0041-00
hwop-0045-00
hwop-0049-00
hwop-0053-00
hwop-0057-00
hwop-0062-00
hwop-0066-00
hwop-0070-00
hwop-0076-00
```

Ordered-ID receipt SHA-256:
`8bb09e9e7b919e802e0a3c96c8be335538b2334e5fa6dd4ef43953657406afeb`.
All 17 IDs exist exactly once in the bound lowering and each has
`hw_op_type=QLinearAddUint8`.

The mutable plan changed during the audit from
`db3394a1f902bc7426fa791ae0574464e9f972678ea7980bcadad2efb1f42102`
to `6d5ab609474d2caeaf5f2fc016378e406d8669f797c86f6d668f28953bd3f1e4`.
This task did not modify it. The drift is recorded as nonblocking mutable
provenance; the immutable index/common/QAdd/tail rule receipts did not drift.

## Validation

```powershell
python tools/audit_complete_operator_json_family_set.py `
  artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/family_set.json `
  --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/shared_family_set_audit_exact_stage_scope.json
```

Exit `1`, expected legal BLOCKED. The sole audit error is:

```text
candidate contract did not pass complete-JSON validation:
artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/candidate_contract.json
```

It is classified as `EXPECTED_LEGAL_BLOCKED_CANDIDATE_NOT_SCOPE_ERROR`.

Shared regression:

```powershell
python -m unittest tests.test_complete_operator_json_family_set -v
```

Exit `0`, `11/11 PASS`. Scope negative controls for missing, duplicate,
cross-family extra stage, lowering-SHA drift, stage-ID drift and per-ID type
mismatch all fail closed.

## Frozen asset assertions

The following identities remain byte unchanged:

- candidate contract: `e7068e1931e001f7e92958a3334d761a1ff2603fbf9d4715408c560122abbfe5`
- blocked candidate schema: `bde3397ebe27c8c686fd3ddecf70c1f8baef2b22fe0aaf315998f070168e5784`
- detailed 47,123-leaf ledger: `ff6acd25aec3044a4c3c2d493a444350b039654fefb0396e21ed0d2a769bbec0`
- public ledger: `ddbe8acdd16049caf2b9d83d21a5e680ce544476779f53a72a8bf871816e1515`
- candidate validation: `d8ef7287b3916f47b3bc1637294538798ddecdf0024abc767b3664d495f695c7`
- handler capability: `62a78813dd4a680a8d6be9d9f99749eb5ad0d125304927ab555525fb3c1a0f39`
- current-test diff: `d49f37477990a230767f587029411d9c7b4f6c61c855e7318d11cd4084a693dc`
- composition boundary: `a9951ff00be7a6c6e370bcf72e0b1c6d45e82b00b6335b4d878400302b260816`
- original family report: `2ae1bf92242cfc70cce12d64d881589492270d05cebdcc1ad0d0393f959daf50`
- v36 ZIP: `b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382`

The frozen findings are unchanged: 47,123 leaves total, 1,954 resolved
logical/DAG/owner leaves, 45,169 unresolved target-hardware leaves; v35
`16B→32B` is still `CONFIG_EXPLAINS`, while v36's eight-lane 32B correction
still awaits dynamic Buffer5/MSE/natural-terminal/formal-D proof.

## Claim boundary and rule feedback

This work proves only exact QLinearAdd family scope coverage. It generated no
mapping, bitstream, execplan, SCA, ZIP or server action and changed no plan,
public rule, functional RTL or other family asset.

`RULE_CONFIRMATION`: current
`CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001`, schema and
auditor are sufficient; no QLinearAdd-specific duplicate rule is required.
