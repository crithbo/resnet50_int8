# QLinearAdd complete-JSON regeneration v1

Date: 2026-08-06  
Analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`  
Upstream task: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`

The current lowering bundle contains exactly 17 `QLinearAddUint8` stages. The
family inventory covers all 17 once, expands each logical operator into the
frozen six-stage composite, and therefore covers 102 planned physical stages.
There are five structural shape classes and 17 materialized-consumer signature
classes after qparams, padding/replay and schedule are included.

No strict target hardware JSON was materialized. The blocked candidate schema
contains 47,123 leaves:

- 1,954 resolved typed-model/DAG/address-owner leaves;
- 45,169 exact unresolved target hardware leaves;
- 45,169 `SOURCE_ABSENT_UNKNOWN_FOR_TARGET` records;
- zero implicit zero/null promotions;
- zero native-reference promotion from project v35/v36 files.

The shared validator result is intentionally:

```text
candidate_status=BLOCKED
contract_valid=true
blocked_valid=true
pass=false
errors=0
completion_blockers=135598
```

`pass=false` and exit code 1 are the required fail-closed completion result, not
a structural validation error. The family auditor also exits 1 because the
single exact-coverage candidate is BLOCKED, while separately proving
expected/covered=`17/17`, missing=`[]`, unexpected=`[]`.

## Current receipts

| Path | SHA-256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` (mutable provenance only) | `325be21aec6d57880c08a4e5f50d9effb83a8ad5e0e9c6bb579b175dc0e4e021` |
| `.agents/rules/生成前必读索引.md` | `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6` |
| `.agents/rules/算子配置规则.md` | `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820` |
| `.agents/rules/QLinearAdd算子配置规则.md` | `28bb859c5f9b8cb5ce5e7ac0dfd81bc06c8b24835d1d3fa4a6062c7c23c0800b` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| `contracts/operator_config/complete_json_generation_contract_v1.json` | `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746` |
| `tools/validate_complete_operator_json_candidate.py` | `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f` |
| `tools/audit_complete_operator_json_family_set.py` | `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82` |

The pinned upstream reference repository is
`uSFrances/ndp-sim@ec12424516ae0304228dd2321d4e604fe225e04e`.
Reference grades are A=`0`, B=`2`, C=`2`, D=`1`. Pinned Git-tree blob
receipts pass for all four native references. Windows working-tree SHA-256 is
recorded separately from the pinned Git blob OID.

## Family inventory

| Structural shape | Count |
|---|---:|
| `[16,256,56,56] + [16,256,56,56]` | 3 |
| `[16,512,28,28] + [16,512,28,28]` | 4 |
| `[16,1024,14,14] + [16,1024,14,14]` | 6 |
| `[16,2048,7,7] + [16,2048,7,7]` | 3 |
| node0076 `[16,1000] + [1000] -> [16,1000]` | 1 |

Every target carries the six typed qparams
`a_scale/a_zero_point/b_scale/b_zero_point/y_scale/y_zero_point`. Node0076
retains the hardware replay contract: B typed bytes=4,000, physical
bytes=4,032, padding=32 bytes, replay count=16 and modulo-1000 address
selection.

The six planned physical stages per target are:

```text
op_a_dequant
op_b_dequant
op_relocation_pad
op_fp32_add
op_tail_mul
op_tail_round
```

The public composition contract records 85 target-specific adjacent DAG
boundaries. All 85 remain unresolved in target hardware carrier/address/
accepted-handshake/visibility/terminal terms.

## Handler capability

There is no native composite `QLinearAddUint8` registry/handler. The native
add-dequant and prefill handlers are placeholders; the decode handler is a
conservative example; the quant primitive is not a QLinearAdd exact tail.
Existence/importability therefore proves neither new shape nor dtype, qparam,
layout, address or cross-stage schedule support.

All six changed capability axes are false and all 45,169 dependent hardware
leaves are explicitly `UNCOVERED`. This is the precise capability blocker; the
current v36 project JSON is comparison evidence only.

## Current-test comparison

The shared current projection is read-only and binds node0007 v36. Other 16
targets have no current tested strict configuration and are classified
`CURRENT_ABSENT`.

Leaf counts:

```text
SAME=878
NEW_CANDIDATE_DEFECT=1894
CURRENT_ABSENT=44351
```

`NEW_CANDIDATE_DEFECT` means the blocked candidate hardware leaf is null/
unresolved while node0007 v36 contains a project value. It does not mean the
v36 value is authorized for the other targets.

Current blocker attribution:

- `CONFIG_EXPLAINS`: v35 FP32 GA supplied four lanes × 4B = 16B while Buffer5
  required a physical 32B row. This directly explains the v35 return stall.
- v36 intentionally adds PE10/PE12/PE30/PE32, supplying eight lanes × 4B =
  32B, but remains `PACKAGE_READY_NOT_RUN_SPLIT_C_ONLY`.
- `DYNAMIC_ONLY`: v36 Buffer5 accepted write, MSE4 wdata, natural terminal,
  stage-local D and full-chain 28D require a formal return.
- `CONFIG_EXCLUDED`: historical observer, runner, transport and cloud-RTL
  identity issues do not explain the v35 consumer-equation byte-supply
  mismatch.

## Validation commands

All commands used:

```powershell
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/build_qlinearadd_complete_json_regeneration_v1.py
# exit 0

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/build_qlinearadd_complete_json_public_contract_v1.py
# final exit 0; the first attempt stopped before contract creation on the
# display-ID/real-lowering-ID mismatch and was corrected to hwop-0007-00.

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/validate_complete_operator_json_candidate.py artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/candidate_contract.json --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/shared_candidate_validation.json
# exit 1, expected BLOCKED; contract_valid=true, blocked_valid=true, errors=0

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/audit_complete_operator_json_family_set.py artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/family_set.json --output artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/shared_family_set_audit.json
# exit 1, expected BLOCKED family; 17/17 exact coverage, missing/unexpected=[]

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_complete_operator_json_candidate tests.test_complete_operator_json_family_set -v
# exit 0, 11/11 PASS

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/validate_qlinearadd_complete_json_regeneration_v1.py
# exit 0, valid=true, errors=[]
```

Family-specific in-memory negative controls all exit 1/fail closed:

1. delete one required leaf;
2. promote a project-comparison leaf to `REFERENCE_EXACT`;
3. fill an unknown target leaf with implicit zero;
4. materialize while unresolved leaves remain;
5. misclassify a required unknown target leaf as not applicable.

The two historical family validators were also executed receipt-only. They
remain exit 1 only because their frozen provenance/current-rule SHAs are stale.
That fail-closed historical receipt was not promoted to a target-config pass.
No numeric, W3, qparam, tail, workload or golden analysis was repeated.

## Machine artifacts

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/stage_inventory.json` | 159585 | `84f0977caab5838013fbcdff9036d91802e5c6582cbc83ab23b55e0d8f7d9476` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/field_provenance_ledger.json` | 85339154 | `ff6acd25aec3044a4c3c2d493a444350b039654fefb0396e21ed0d2a769bbec0` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/reference_applicability.json` | 4240 | `13315c0d667975b09d9e8543f10fa10ed76e0b65184969d56fef22c9922da88d` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/handler_capability.json` | 3952 | `b367b49009e879db7b4a44b48b3632eb014041417d3a7ab833e8766233b3a0b5` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/current_test_diff.json` | 2892 | `b9529ff81d1f97e31cbf1c3f2b148f6add68fdb999fb469e0b454423f2c9725b` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/blocked_candidate_schema.json` | 2162295 | `bde3397ebe27c8c686fd3ddecf70c1f8baef2b22fe0aaf315998f070168e5784` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/public_field_provenance_ledger.json` | 81347263 | `ddbe8acdd16049caf2b9d83d21a5e680ce544476779f53a72a8bf871816e1515` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/public_handler_capability.json` | 17310122 | `62a78813dd4a680a8d6be9d9f99749eb5ad0d125304927ab555525fb3c1a0f39` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/public_current_test_diff.json` | 31581261 | `d49f37477990a230767f587029411d9c7b4f6c61c855e7318d11cd4084a693dc` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/composition_boundary.json` | 87064 | `a9951ff00be7a6c6e370bcf72e0b1c6d45e82b00b6335b4d878400302b260816` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/candidate_contract.json` | 2246 | `e7068e1931e001f7e92958a3334d761a1ff2603fbf9d4715408c560122abbfe5` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/family_set.json` | 577 | `7c3082340700f1ab40bb6a6bf2e0422dd4e1a8bb7a86e2e70bfbb3730e546db9` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/complete_json/shared_candidate_validation.json` | 20542019 | `d8ef7287b3916f47b3bc1637294538798ddecdf0024abc767b3664d495f695c7` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/shared_family_set_audit.json` | 21084383 | `aab7003efe49d486daee979f0da7fab7944584c5b0f01cff45585e2e8f4e8caf` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/validation.json` | 9167 | `42af9c0c0466aa41bd4c24acf6344216b86d320093b4c5145084935803f22f4e` |
| `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/qlinearadd/report.json` | 9646 | `2ae1bf92242cfc70cce12d64d881589492270d05cebdcc1ad0d0393f959daf50` |

Artifact-root forbidden-output scan found zero ZIP, sidecar,
`PREPARE_AND_RUN.sh`, `TEST_PACKAGE_MANIFEST.json` or
`SERVER_RESULT_GATE.json`.

## Rule feedback

`RULE_DELTA_PROPOSAL`:

```text
ID: CDA-QADD-COMPLETE-STRICT-COMPOSITE-TYPED-HANDLER-001

A complete QLinearAdd strict emitter must expose one typed six-qparam
composite handler covering all six physical stages, all five structural shape
classes including node0076 replay, per-edge address/lifetime ownership,
accepted 16B/32B transaction supply, exact UINT8 tail and terminal.
Primitive placeholder/example handlers and project-generated JSON cannot
satisfy missing composite leaves.
```

Evidence: 17/17 lowering stages currently share the same two emission blockers,
and the public validator reports all 45,169 target hardware leaves unresolved
and uncovered by a handler.

Claim boundary: proposal only. This task did not modify
`.agents/plan.md`, public rules, functional RTL, current v35/v36 assets, or any
other family.
