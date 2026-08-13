# MaxPool node0002 complete-JSON regeneration v1

## Provenance

- analysis owner: `019fbe9f-3f2d-7071-806c-1ae72ae96391`
- upstream task: `019fd276-14c5-7800-94db-87ebfb9ce632`
- return target/mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- family: `maxpool_uint8`
- lowering stage: `hwop-0002-00`
- lowering hardware type: `MaxPoolUint8`
- status: `COMPLETE`

## Authority and coverage

- authoritative source:
  `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`
- source SHA256:
  `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- pinned ndp-sim commit:
  `ec12424516ae0304228dd2321d4e604fe225e04e`
- pinned Git blob:
  `4e8f7bb8906ab58f54f4c6507d2b94822f71bf04`
- reference class: `A`
- covered lowering stages: `1/1`
- materialized-consumer equivalence classes: `1`
- complete JSON leaves: `461`
- origins:
  - `REFERENCE_EXACT=458`
  - `ADDRESS_PLANNER_DERIVED=2`
  - `RTL_DERIVED=1`
  - `UNRESOLVED=0`

The sole target is the exact ResNet MaxPool instance:
`uint8[16,64,112,112] -> uint8[16,64,56,56]`,
kernel `3x3`, stride `2`, pads `1`, same qdomain, one native stage.

## Materialized target differences

The strict candidate differs from the pinned upstream source at exactly:

1. `/stream_engine/stream0/base_addr`: planner-owned input address.
2. `/stream_engine/stream1/base_addr`: planner-owned output address.
3. `/stream_engine/stream0/padding_reg_value`: `null -> 0`, because enabled
   excluded UINT8 border bytes require the Max identity value `0`.

Against the actual v5 consumed final JSON, only the padding leaf differs.
It is classified `SUSPECTED_CURRENT_DEFECT`, but the frozen return does not
contain a qualified boundary proving that this strict JSON defect caused the
dynamic stop. The current stop therefore remains `INSUFFICIENT_EVIDENCE` with
respect to that leaf.

The current non-config boundary remains `B_GA_INT8_MAX_FLOW`: current
`GA_PE_Inbuffer` pipeline0 readiness has INT32/FP32 branches but no INT8
branch. The complete-JSON result does not claim to repair hardware.

## Machine artifacts

- root:
  `artifacts/operator_config_validation/r5_complete_json_regeneration_v1/maxpool_uint8`
- strict JSON:
  `complete_json/node0002_hwop-0002-00_maxpool_uint8.json`
  SHA256 `0348ead26469b8ebda0df03979d38f8436bc9f1f6903bafed078b0547d682335`
- candidate contract:
  `candidate_contract.json`
  SHA256 `0096f0f507a3ad7281c07d443c548e1786a47cbf6820f0a1b194972d298518d6`
- field ledger:
  `field_provenance_ledger.json`
  SHA256 `c6678d18b5d6a8caada28f405fa7ec333ed0f5987a77331b078998e3e3abfa19`
- handler capability:
  `handler_capability.json`
  SHA256 `8d21198d40dc695e32c26d9790c3e91e7af660ad921ab670e45fd5da74f32f15`
- current-test diff:
  `current_test_diff.json`
  SHA256 `eff77c32fa844b94d51a0ca5963bcf41430bde25d40f3d06ea06bb54fd983e09`
- family set:
  `family_set.json`
  SHA256 `f4dba082192bbb425fcd4cbf693815cb8b606a88205f5319dffc2f38a282809c`
- shared candidate report:
  `shared_candidate_validation_report.json`
  SHA256 `87c9632e31517e1a5c646f4f1b8a0ca12788118d63d7447edf12c4dc9e8c6ffc`
- family-set report:
  `family_set_audit_report.json`
  SHA256 `65d75ca53e9fe6ad6d3c1e3125beeb99d63f19b8c3992f9a37231c248c28a342`
- local validation:
  `local_validation_report.json`
  SHA256 `02db07df7c319253e6abc774c33500614d7bf8307dece7a99c0ee2f6090712f6`
- machine report:
  `report.json`
  SHA256 `28863a00d47cbd99502019b8b3e2e778ecec28897075703ef33e322d16664d8b`

## Validation

- current candidate validator SHA:
  `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- candidate result:
  `pass=true`, `contract_valid=true`, `errors=0`,
  `completion_blockers=0`
- current family auditor SHA:
  `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`
- family result:
  `pass=true`, `expected_stage_count=1`, `covered_stage_count=1`,
  `missing=[]`, `unexpected=[]`, `errors=0`
- strict operator-config shadow validation: `valid=true`, `issues=0`
- five public JSON schemas: all PASS
- family negative controls: `8/8` fail closed
- shared driver regression: `11/11 PASS`
- forbidden server-package outputs under artifact root: `0`

## Rule feedback

1. `REFRESH_MAXPOOL_PADDING_RTL_EVIDENCE_CURRENT_IDENTITY`
   - The legacy padding contract binds a pre-current `RD_Data_Channel` SHA.
   - Current RTL still contains the same padding-mask substitution equation.
   - This is receipt drift, not a candidate leaf error.
2. `ALIGN_OPERATOR_CONFIG_VALIDATOR_GA_INT8_MAX_NUMERIC_FACT_WITH_CURRENT_RULE`
   - Current NDP field rule says
     `CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS`.
   - The generic shadow validator still emits the superseded
     `unsigned bytewise min / CONTRADICTED` fact.
   - Its strict validity result is still true; the stale fact was not used for
     this candidate or blocker adjudication.

## Hard boundary

No mapping, bitstream, execplan, SCA/SCA_D, server package, upload, server run,
lease, numeric/golden rerun, functional RTL edit, plan edit, public-rule edit,
or other-family edit was performed. Read-only hashes of the current v5
mapping/bitstream/execplan were used only for current-test comparison.
