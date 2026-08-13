# ConvInt32Accumulate 53-stage complete-JSON regeneration audit

- family owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- upper task: `019fd276-14c5-7800-94db-87ebfb9ce632`
- unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- family: `conv_int32_accumulate`
- target hardware type: `ConvInt32Accumulate`
- status: `HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`
- strict complete JSON materialized: `0`
- server package generated or modified: `false`
- mapping/bitstream/execplan/SCA generated: `false`
- server upload/run/lease: `false`
- numeric/W3/golden repeated: `false`
- functional RTL, plan or public rule modified: `false`

## Current read receipts

- `.agents/agent.md`: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md`: `325be21aec6d57880c08a4e5f50d9effb83a8ad5e0e9c6bb579b175dc0e4e021`
  (mutable provenance only)
- `.agents/rules/生成前必读索引.md`:
  `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6`
- `.agents/rules/算子配置规则.md`:
  `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`
- `contracts/operator_config/complete_json_generation_contract_v1.json`:
  `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746`
- shared candidate validator:
  `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- shared family-set auditor:
  `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`
- shared candidate-validator tests:
  `d51ab72366735b5e7f3039c72cc47b4d28fcb3f92747bae878ccaee03589a717`
- lowering bundle:
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- pinned ndp-sim commit:
  `ec12424516ae0304228dd2321d4e604fe225e04e`

## Family census and signatures

The lowering bundle contains exactly 53 requests whose
`identity.hw_op_type` is `ConvInt32Accumulate`.  The catalog records each
stage's op, dtype, complete logical shapes, NCHW/OIHW logical layout,
x/w-zero-point and bias descriptor, padding/stride/dilation/group, logical K,
dot4 tail, node DAG, typed predecessor/consumer, logical tensor owner,
required visibility barrier and conservative release condition.

Bias payload identity remains per-stage ownership and is not part of the
materialized-consumer schedule key.  The exact consumer-signature census is:

- target stages: `53`
- signature classes: `20`
- missing stage IDs: `0`
- duplicate stage IDs: `0`
- unexpected stage IDs: `0`

The public family-set manifest binds
`target_hw_op_types=["ConvInt32Accumulate"]` and contains all 53 real lowering
`hw_op_id` values exactly once.  Conv does not use the View-only
`METADATA_ONLY_ALIAS_NO_COMPUTE` exception.

## Native reference and handler capability

The pinned upstream Git tree contains FP16 GEMM/GEMV SA JSON instances but no
`QLinearConv` or `ConvInt32Accumulate` JSON registry or handler.  The current
ndp-sim working tree also has no Conv handler; project-added MatMul registry
and JSON assets do not authorize Conv.

Reference classification:

- A exact replay: `0` stages
- B same primitive with target-shape variation: `0` stages
- C same SA hardware but different FP numeric/operator semantics: `53` stages,
  structure/rule extraction only
- D project-added node0004/current configs: comparison and field inventory
  only, never target-value authority

The instance-specific node0004 materializers can replay their frozen instance
but prove no generic shape, dtype, qparam, layout, address or cross-stage
schedule capability.  The remaining-52 asset is list-only and explicitly
leaves physical address/lifetime pending.  The generic mapper/encoder can
encode a supplied complete JSON; it cannot derive missing semantic leaves.

First missing capability:

`no generic QLinearConv/ConvInt32Accumulate semantic materializer before the mapper/encoder`

## Leaf-complete fail-closed result

The detailed ledger covers the union of the pinned upstream SA JSON surface
and the current serialized/native node0004 comparison surfaces:

- strict-surface pointers per stage: `657`
- stages with complete pointer coverage: `53`
- detailed ledger entries: `34,821`
- `SOURCE_ABSENT_NOT_APPLICABLE`: `159`
- `SOURCE_ABSENT_UNKNOWN_FOR_TARGET`: `34,662`
- strict JSON files emitted under `complete_json/`: `0`

The exact blocked leaf families are CONFIG topology, DRAM LC chains, LC-PE
source/mode/keep, buffer loops, buffer mode/mask/capacity/lifetime, all MSE
target/base/index/stride/padding/tail/ping-pong leaves, N2N routing, SA
ping-pong/terminal leaves, physical bank/row/address allocation, and
cross-stage visibility/barrier/release.

No unresolved leaf received an implicit zero, null, nearest-template value,
old failed-package value or server residual value.  The public-schema BLOCKED
blueprint contains 615 null leaves only to make the unresolved set
machine-readable; it is outside `complete_json/`, is explicitly not a strict
target, and has no current-test identity.

## Current serialized/native comparison

Logical node0004 op/dtype/shape/qparams/padding-tail entries are equal in the
new lowering, serialized current and native-four-lane current: `5/5 SAME`.

For 615 current physical leaves:

- serialized/native equal: `614`
- route-specific difference: `1`
- new strict candidate value available: `0`
- suspected current config defect: `0`
- new candidate defect: `0`

The single route-specific physical difference is intentional route schedule
derivation, not evidence that either current route is wrong.  The historical
serialized `special_array.transout_last_index 2→5` correction is already
present in current config and is recorded as closed, not rediscovered.

Current gaps excluded from configuration attribution:

- serialized v47 actual-consumer observer misbinding; v48 changes observer
  only and has no formal return yet;
- serialized v48 natural terminal and 320 formal-D remain pending;
- native p7 timed out while 28 qualified windows continued to grow;
- native p8f natural terminal and 320 formal-D remain pending;
- the old outbuffer occupancy claim remains `INVALIDATED_NOT_RTL_BUG`.

Therefore current stalls/results cannot be explained by a newly generated
configuration difference, because no legal new physical target exists.

## Validation commands and exits

Bundled Python:

`C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

1. Build:
   `python tools/build_conv53_complete_json_regeneration_v1.py --project-root .`
   → exit `0`
2. Family validator:
   `python tools/validate_conv53_complete_json_regeneration_v1.py --project-root .`
   → exit `0`, `valid=true`, errors `0`
3. Family unittests:
   `python tests/test_conv53_complete_json_regeneration_v1.py`
   → exit `0`, tests `2/2`
4. Public regression:
   `python -m unittest tests.test_complete_operator_json_candidate tests.test_complete_operator_json_family_set`
   → exit `0`, tests `11/11`
5. Shared candidate validator on the BLOCKED contract:
   `python tools/validate_complete_operator_json_candidate.py <blocked-contract> --workspace-root .`
   → exit `1`, candidate status `BLOCKED`, real stage count `53`,
   candidate leaves `615`, `contract_valid=true`, `blocked_valid=true`,
   errors `0`, machine `completion_blockers=1851`, origin
   `UNRESOLVED=615`, handler `NONE`, uncovered dependent leaves `615`,
   forbidden server outputs `0`.  Exit `1` is the deliberate
   `candidate_complete=false` release result, not a structural-contract error.
6. Shared family-set auditor:
   `python tools/audit_complete_operator_json_family_set.py <family-set> --workspace-root .`
   → exit `1`, expected/covered `53/53`, missing `0`, unexpected `0`;
   the embedded candidate report remains `contract_valid=true`,
   `blocked_valid=true`, errors `0`, but the family cannot be COMPLETE while
   its only candidate has `pass=false`.

Deterministic primary-output double build mismatch count is `0`.
Forbidden ZIP/PREPARE_AND_RUN/TEST_PACKAGE_MANIFEST/SERVER_RESULT_GATE count
under the artifact root is `0`.

Negative controls, all fail closed:

1. unresolved leaf assigned implicit zero;
2. project D reference promoted to `REFERENCE_EXACT`;
3. source provenance removed;
4. invented origin enum.

## Public driver refresh and RULE_CONFIRMATION

The public driver was mechanically synchronized after the initial run.  The
new candidate validator now classifies the 615 unresolved leaves and
unsupported/uncovered handler dependencies as `completion_blockers`, rather
than incorrectly appending a structural error.  The refreshed result is:

- `contract_valid=true`;
- `blocked_valid=true`;
- `errors=[]`;
- `completion_blockers=1851`;
- `pass=false` because the candidate is intentionally incomplete.

The family auditor independently proves exact stage accounting
(`expected=covered=53`, missing/unexpected `0`) and correctly keeps family
release blocked because no COMPLETE candidate exists.  Public regression is
`11/11 PASS`.

`RULE_CONFIRMATION`: the synchronized public-driver semantics plus the
existing native-reference applicability, handler-capability, strict
completeness, semantic ownership and current-consumer rules are sufficient
for this family.  The earlier
`CDA-COMPLETE-JSON-BLOCKED-CANDIDATE-FAMILY-COVERAGE-001` proposal is
withdrawn as implemented/superseded.  No public rule or shared validator was
modified by this owner.

## Artifact identities

Root:
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/conv_int32_accumulate`

- `report.json`: bytes `6579`, SHA
  `99642520fe9954f785cf36e2acce50f7d434c1a5e33185d9721dab89d848cf7f`
- `stage_catalog.json`: bytes `326879`, SHA
  `bd481dbe574b2945e25f9af6f1abf66ef1f275baf4260861ecd012642931cb55`
- `equivalence_classes.json`: bytes `44540`, SHA
  `7761469e87cc69abb941bd8255e67710a9cb61cdb83d285c86a12499d452e0cf`
- `field_provenance_ledger.json`: bytes `41145282`, SHA
  `6f35e0cb513894a20d11a5b3b6d78a01cf0a916c418f600fcad0f38c9d633a22`
- `reference_applicability.json`: bytes `4220`, SHA
  `6c16ed0a57c4e980f15099be4bc25dd782e6c437e33910eef41cc9e20251e57d`
- `handler_capability.json`: bytes `3216`, SHA
  `3a20562abbaa2ab9a6c6b01463125c8137249a1064e9355ee81dafe56d0a0f23`
- `current_test_diff.json`: bytes `393592`, SHA
  `44715227ab5fc4e065cd6a518da811a3fa5a0766d83933827267a8ed8f3d7a11`
- `validation.json`: bytes `469`, SHA
  `5323239737a93bedffbd01f356861b0b1e3fe85ccf0356efbca0131b94b7133e`
- `negative_controls.json`: bytes `1050`, SHA
  `38d6b400eb0456a8076b818daa14f3add4ca947ad5f83ce2c4498ad330a00954`
- `blocked_candidate_contract.json`: SHA
  `c7bc3aa5a5f29565db0ac2c9798b69893bfe5b57538f179e4f8208cf741694a9`
- `family_set.json`: SHA
  `7124928d606e87dc9e7361bc5330c1e681b6b3556570bc06c19a0541cd4f3fdf`
- `public_candidate_validation.json`: SHA
  `3d166d4c274b19b3fdf66b74cc165c61c9d20927647799dba78f209124e7f390`
- `public_family_set_audit.json`: SHA
  `5737fa8f238f3204d453e865a94a98057825f3eb5088267a8014cfd1bc6c5327`

Tools:

- builder SHA:
  `b35c1f0dc0460b9b9087da498792c8f640f1427a9f423c4fb6afb8d7094fb8fd`
- validator SHA:
  `4dbf29e51f029330f554d425bc4708cad6900fc22d7cf684e6d57e18066f17eb`
- test SHA:
  `33eec8ea02129941ccdd389d21ec3530775e5e2450b5ba27cd71d3d5015ced80`

## Claim boundary

This task proves the complete 53-stage logical census, 20 consumer-signature
classes, exact native-reference applicability boundary, handler capability
absence, declared strict-surface provenance coverage, exact-once family
enumeration, local fail-closed behavior, and current serialized/native
read-only comparison.

It does not produce a strict target JSON, mapping, bitstream, execplan, SCA,
server package, server result, natural terminal, formal D or E2–E5 evidence.
The next legal action is to authorize and implement a generic,
equation-backed ConvInt32Accumulate semantic materializer (or per-signature
materializers) and then regenerate from the typed lowering.  It is not legal
to fill the 34,662 unknown target leaves from current packages or nearest
FP16 templates.
