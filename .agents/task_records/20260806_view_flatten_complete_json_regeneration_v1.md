# 2026-08-06 View/Flatten complete-JSON regeneration v1

## Task identity and scope

- family: `view_flatten`
- owner stage: `hwop-0073-00` / request `r5:hwop-0073-00`
- source task: `019fd276-14c5-7800-94db-87ebfb9ce632`
- unique mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- disposition: `COMPLETE`
- materialization: `METADATA_ONLY_ALIAS_NO_COMPUTE`
- hardware JSON count: `0`
- server package generation/modification/upload/run/lease: `false`
- mapping/bitstream/execplan/SCA generation: `false`
- functional RTL, plan, public-rule, other-family modification: `false`

The family-specific requirement is decisive: node0073 is a physical metadata
view and must not be converted into an arithmetic or register JSON merely to
satisfy a file-count convention.

## Current generation receipts

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` mutable provenance:
  `8b90b764707907b3f3eb52c0ff2bf680c71321aa0afac34c15d19be3512429b2`
- `.agents/rules/生成前必读索引.md`:
  `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6`
- `.agents/rules/算子配置规则.md`:
  `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820`
- `.agents/rules/Flatten_View算子配置规则.md`:
  `28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee`
- public policy:
  `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746`
- fresh public candidate validator:
  `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- fresh public family auditor:
  `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`
- lowering bundle:
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`

## Full family inventory and equivalence partition

The current lowering bundle contains exactly one `View` stage:

- `hw_op_id=hwop-0073-00`
- `request_id=r5:hwop-0073-00`
- `onnx_name=flatten_473`
- `onnx_op_type=Flatten`
- `hw_op_type=View`
- `axis=1`
- original typed geometry:
  `float32[16,2048,1,1] C/[8192,4,4,4] -> float32[16,2048]
  C/[8192,4]`
- qparams: `SOURCE_ABSENT_NOT_APPLICABLE`
- padding/tail: `SOURCE_ABSENT_NOT_APPLICABLE`
- original logical DAG:
  `node0072.D -> node0073 metadata View -> node0074.A`
- allocation/address owner:
  producer allocation plus cross-stage address planner; View owns no allocation
  and no release

It forms one materialized-consumer equivalence class:

`view_flatten:uint8_identity_alias:node0075_A:v1`

The current approved overlay removes node0072 Dequant, node0073 View and
node0074 Quant together and binds the existing node0071 final UINT8 D storage
to node0075 accumulation pass00 A:

- source: `uint8[16,2048,1,1]`, strides `[2048,1,1,1]`
- alias: `uint8[16,2048]`, strides `[2048,1]`
- order: C
- offset: 0
- owner: `r5:hwop-0071-01:D`
- storage:
  `r5:activation:node-0071:D:tensor-ab32f279540568c3:batch-slice-sharded-16x2048-v1`
- per-slice base:
  `0x000a2000 + (slice_id << 25)`, `0 <= slice_id < 16`
- coverage: 2048 bytes/slice, 32768 unique bytes total
- View instruction/request/config/execplan-line count: 0
- host copy/precompute/relayout/replay: false

The existing frozen 32768-element address proof was consumed, not recomputed.
No operator numeric analysis or golden tensor analysis was repeated.

## Native reference and handler boundary

Pinned `ndp-sim` commit:
`ec12424516ae0304228dd2321d4e604fe225e04e`.

The pinned Git tree has no View/Flatten/Reshape hardware JSON and no registered
View handler. Dirty or untracked project additions were excluded from native
authority. Template classes are:

- A exact replay: none
- B same primitive, shape differs: none
- C same block, numeric/dtype differs: none
- D project-added exact-instance evidence:
  the approved fusion contract and current composite alias materialization

The public handler matrix uses `kind=NONE`; all seven capability axes are
false. No project overlay is used to infer generic shape, dtype, qparam,
layout, address or cross-stage scheduling support.

## Outputs

Root:
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/view_flatten`

- no-config machine contract:
  `complete_json/no_config_contract.json`
  `754af068effe0b80e3657b73d94380789e95f0c446cd7da9bdc823eb5bd02f60`
- public candidate contract:
  `candidate_contract.json`
  `e430d8c06452d1247d65daab03041fa834120e8e8a1f3a841cf8a72fe5e0af1f`
- 100% field ledger:
  `field_provenance_ledger.json`
  `6e60a32c395dfed362f3fe6e8342df08f36ad67afdd055ff7a55f0fceee6fba9`
- reference applicability:
  `reference_applicability.json`
  `8406fdfcb83c24df8b33f1638e7ce99dc0eccdbbfbe86db8dab1bbfab1939a61`
- handler capability:
  `handler_capability.json`
  `c3d450ddbb23e382d1c978c93cb0cae7d98c66fd47a2cf6902bafff8a9cc46a9`
- public current diff:
  `current_test_diff.json`
  `fcabf28236c150619a4508947f673f2ae5d612ab15c9ca050b8cf7393925665f`
- detailed current comparison:
  `current_test_diff_analysis.json`
  `f19d99ab4a42abaf9729fe0e0f2203cd8ef3e0d70007aba6fefc3fa3e603c4af`
- family set:
  `family_set.json`
  `b6d02072a018250971815e80e15a04ca761a3c13c72edfeae25a0673405b227f`
- family report:
  `report.json`
  `650b9059ce2253231e446cdce5fe70d4c3af0fd20cfd9a2d322c85b2aecb0aac`

The public candidate exists to apply the shared leaf/capability/current-diff
gate to the no-config evidence. It is intentionally not listed as a hardware
candidate in the family set. The family set covers `hwop-0073-00` once, and
only once, through `no_config_stages` with
`METADATA_ONLY_ALIAS_NO_COMPUTE`.

## Validation

Fresh shared candidate report:

- path: `candidate_validation.json`
- SHA:
  `16e0e3410c8b2bebeff3ef5e3366b7963fa26860368bfc65d183625bb71493e2`
- candidate status: `COMPLETE`
- contract valid: true
- pass: true
- errors: 0
- completion blockers: 0
- blocked valid: false (not a BLOCKED contract)
- candidate leaves: 161
- ledger leaves: 161
- handler: NONE
- composition required: false
- forbidden server-package outputs: 0

Fresh shared family-set report:

- path: `family_set_validation.json`
- SHA:
  `c14221924db90a60c32224f0d9a82958db44e736cc0813e7164e1fac0b55c428`
- pass: true
- expected View stages: 1
- covered stages: 1
- missing: 0
- unexpected: 0
- no-config receipts: 1

Regression:

- fresh shared candidate/family tests plus family-directed tests: 15/15 PASS
- family negative controls: 5/5 rejected
  - hardware JSON required promotion
  - fabricated View register JSON
  - non-zero alias offset
  - nearest-template origin
  - dynamic accepted-lifetime overclaim

## Current-test comparison and blocker attribution

The current v9 package is read-only and contains zero node0073/Flatten/View
members. Therefore the public leaf-complete diff correctly treats the current
View hardware JSON as unavailable and classifies all 161 no-config contract
leaves `CURRENT_ABSENT`; it does not substitute another family's JSON as the
baseline.

The detailed comparison separately records:

- SAME: zero View config/stage, storage identity, owner, offset, shape/layout
  coverage, and no-copy/no-replay behavior
- INTENTIONAL_DERIVATION: legacy FP32 node0072-to-node0074 logical edge becomes
  the approved UINT8 node0071-to-node0075 alias; 131072 legacy FP32 bytes become
  32768 current UINT8 bytes
- SUSPECTED_CURRENT_DEFECT: the canonical node0072-node0074 endpoint top-level
  exact-division/endpoint-blocked gate is stale relative to its Quantize owner
  section and current overlay; this is a contract-coherence issue, not a
  current package View-config defect
- NEW_CANDIDATE_DEFECT: none
- DYNAMIC_ONLY: producer acceptance before consumer reads, actual 8192 reads
  and ordered hash, 32-stage/512-finish natural terminal, and 144 formal-D
  comparisons

Current View-config defect count is zero. The prior v5 bank/row defect belongs
to the node0075 address/config owner and was corrected in v9. Observer,
package, runner, RTL identity, terminal and formal-D blockers are not
attributed to View configuration.

## Claim boundary and local E2

- independent View local E2: false; View owns no executable stage
- integrated static alias/address closure: true for the current exact instance
- accepted runtime lifetime/release: not proven locally
- E3/E4/E5, production, performance and server execution: not claimed
- no `CONFIG_ONLY_CORRECTNESS_BASELINE` claim is emitted by this regeneration

## Rule feedback

`RULE_DELTA_PROPOSAL`:

Non-synonymous family-rule update proposed, not applied: add the approved
pair-elimination UINT8 alias route (`node0071D -> node0075A`) and explicitly
mark the legacy FP32 `node0072D -> node0074A` endpoint as off-path for this
adjudication. Preserve the metadata-only/no-arithmetic-JSON prohibition and
the requirement for exact consumer materialization plus accepted-lifetime
evidence before integrated runtime claims.

No public-rule change is proposed.

## Package release

`PACKAGE_RELEASE=NOT_GENERATED_NOT_MODIFIED`

No ZIP, `PREPARE_AND_RUN`, package manifest, mapping, bitstream, execplan, SCA,
server runtime artifact, upload, execution or lease was created by this task.
