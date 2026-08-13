# RequantizeUint8 54-stage exact-scope migration

Date: 2026-08-06  
Family owner task: `019fa2bf-95cd-7502-82c8-6a48cf12d648`  
Dispatch source: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Unique mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

`PINNED_EXACT_STAGE_IDS_MIGRATION_PASS / FAMILY_STILL_BLOCKED_FAIL_CLOSED`

Only the existing Requant `family_set.json` scope surface was migrated. It now
pins the current lowering document SHA-256 and enumerates the 54 authoritative
`RequantizeUint8` hardware stage IDs in lowering order. The existing
`target_hw_op_types=["RequantizeUint8"]` remains and is used only to validate
the real type of each pinned ID.

Fresh audit result:

```text
scope_mode=PINNED_EXACT_STAGE_IDS
expected=54
covered=54
missing=[]
unexpected=[]
duplicate=[]
type_errors=[]
lowering_sha_errors=[]
candidate_contract_valid=54/54
candidate_blocked_valid=54/54
candidate_errors=0
complete_pass=0/54
family_audit_pass=false
family_audit_errors=54
nonblocked_family_audit_errors=0
```

The 54 family-audit errors are exactly one legal non-`COMPLETE` fail-closed
finding for each frozen BLOCKED candidate. No scope, identity, SHA, duplicate,
type, coverage, schema, ledger, or candidate-contract error remains.

## Exact identities

| Item | SHA-256 |
|---|---|
| Previous legacy-selector `family_set.json` | `a1040358e84a80444d4d58a91751cfa0329732aeb349ad8231e7b238060debcb` |
| Migrated exact-scope `family_set.json` | `957a4fed3f3a87faee62ff0021a53fab7d22f841350fba437e4cd8b0a7f8452a` |
| Current lowering bundle | `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432` |
| Current family-set schema | `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18` |
| Current family-set auditor | `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1` |
| Fresh exact-scope family audit | `ed0f388845d02a25be30feffd50a8a0eeab66735ee17fc54c85d64f86ffe75b9` |
| Fresh exact-scope migration report | `4ba97f78ddb6aa58b0f0c8b7479b99c772b39d09ba9ec5e39cd0fea364c81c89` |
| Family migration validator | `1e5a3b471d1612fed4a568765c564f66180caa13a1f616fbc6dbef2fd8df6d4a` |

The fresh authoritative migration overlay is
`validation/exact_stage_scope/report.json`. The earlier full-family
`report.json` remains the immutable historical numerical/capability analysis;
its legacy family-set receipt is superseded only for the scope surface by this
overlay.

## Frozen assertion

The frozen set contains the complete 54-stage `candidates/**` tree, aggregate
field ledger, reference applicability, handler capability, current-test diff,
stage inventory, complete-JSON blocked index, and all 54 existing candidate
validation reports.

```text
frozen_file_count=384
frozen_byte_count=44995846
before_tree_sha256=12d225cd9df45bc489b923b91c2b38ab55de4a644f6860751f5c6e32a841ed48
after_tree_sha256=12d225cd9df45bc489b923b91c2b38ab55de4a644f6860751f5c6e32a841ed48
byte_identical=true
```

Therefore all 54 candidate contracts, ledgers, blocked status, composition
evidence and current-test diff remain byte-identical.

## Current read receipts

| Path | SHA-256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` (mutable provenance only) | `db3394a1f902bc7426fa791ae0574464e9f972678ea7980bcadad2efb1f42102` |
| `.agents/rules/生成前必读索引.md` | `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6` |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |

## Validation

```powershell
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_complete_operator_json_candidate tests.test_complete_operator_json_family_set -v
# exit 0; 20/20 PASS

C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/validate_requant_exact_stage_scope_migration_v1.py
# exit 0; errors=[]; all 13 migration checks PASS
```

Public negative controls cover lowering SHA drift, duplicate stage, missing
stage, extra cross-family stage, stage-ID drift and type mismatch; all fail
closed.

## Structured return

`BLOCKER_DELTA`: no change. The existing 54 legal candidate completion
blockers remain open; exact-scope migration neither closes nor adds a numerical,
handler, address/schedule, dynamic-path, E4, or E5 blocker.

`RULE_CONFIRMATION`: current pinned exact-stage schema and auditor correctly
bind the lowering SHA, ordered exact IDs, per-ID real hardware type and exact
coverage while preserving legal BLOCKED semantics. No non-synonymous
`RULE_DELTA_PROPOSAL` is required.

`PACKAGE_RELEASE=NONE`.

Claim boundary: family-set scope metadata and local audit only. No candidate
JSON/contract/ledger/current diff was rewritten; no mapping, bitstream,
execplan, SCA, ZIP, server action, functional RTL, E4, or E5 was produced or
claimed.
