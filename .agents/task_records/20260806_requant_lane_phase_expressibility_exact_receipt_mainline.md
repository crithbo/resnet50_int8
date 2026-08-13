# Requant lane-phase expressibility exact receipt — mainline

Date: 2026-08-06

Mainline task: `019fbec2-fe93-7e03-9314-cff6f222f33d`

Source owner task: `019fd276-14c5-7800-94db-87ebfb9ce632`

## Adjudication

Status:

`CURRENT_FIELDS_EXPRESSIBLE_PROOF_CONSUMED_STRICT_MATERIALIZER_RUNNING`

The optimizer isolated-worktree proof is accepted for the narrow claim that
current JSON-visible hardware fields can express the Requant Conv53
per-channel multiplier lane-phase mechanism. It is not copied into the
mainline workspace and is not promoted to strict JSON, backend, mapping,
bitstream, execplan, SCA, package, server, dynamic, E4, or E5 evidence.

`B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY` is closed only at JSON field
expressibility level. The active replacement blockers are:

- `B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION`
- `B_REQUANT_CONV53_SCALAR_PHASE_BACKEND_AND_DYNAMIC_EXECUTION`

## Exact proof semantics

- 53 per-channel Conv stages have an exact
  `shard → phase0..7 → N-inner` bijection.
- B uses `idx_size=[3,0,null]`, total size `4B`, stride `4`,
  `buf_spatial_size=4`, spatial strides `[0,1,2,3]`, and lane-0-only masks.
- PE00 input1 keep retains the multiplier through the N-inner occurrences.
- A and D use
  `base + 4*((shard*N+n)*8+phase)`.
- `hwop-0075-01` consumes the separately proven scalar supply, has
  `phase_count=0`, and is not counted as false lane-phase coverage.

## Isolated-worktree receipts

The following files were independently read and hashed in
`C:\Users\15383\.codex\worktrees\532a\resnet50_int8`:

1. `resnet50_pipeline/requant_lane_phase_serialization_proof_v1.py`
   - bytes: `26482`
   - SHA256:
     `a17e0a1bcb5f501ec56256f08348dea7c49f0af54302fc83f6fa4e271a2f81fa`
2. `tools/build_requant_lane_phase_serialization_proof_v1.py`
   - bytes: `1329`
   - SHA256:
     `a799853aee905c1c150fe5d1497588547a036b9a7546560e29a77a4e3d38ef9e`
3. `artifacts/operator_config_validation/r5_requant_lane_phase_serialization_proof_v1/report.json`
   - bytes: `206014`
   - SHA256:
     `dcaebda9691bee613163ca3f5504764599c38c865bbee0bc414166533526e469`
4. `tests/test_requant_lane_phase_serialization_proof_v1.py`
   - bytes: `4284`
   - SHA256:
     `90c022ffdcbc006d594c242ec85c8305f57bb17b56a3d70eaadb78488b49da4b`
5. `.agents/task_records/20260806_requant_lane_phase_serialization_expressibility_v1.md`
   - bytes: `4729`
   - SHA256:
     `1ef6917a40421fc5623e47f7a3f54d0127e9add6b2c6f732d30f2f92e73ebbe9`

Validation receipt:

- direct tests: `5/5 PASS`
- negative controls: `9/9 PASS`
- `py_compile`: `PASS`

All five isolated files are absent from the mainline workspace at receipt
time. Their identities are recorded here without duplicating proof assets or
creating a second executable implementation.

## Authorized continuation

The optimizer owner may continue the already authorized isolated Requant
strict materializer and must return exact candidate/ledger/handler/current
diff/shared candidate/exact family-set receipts.

QLinearAdd remains waiting until the Requant strict complete-JSON gate closes.
The dependency order remains:

`Requant/Quant shared tail → QAdd → Conv`

## Claim boundary

No functional RTL, ISA, hardware, active ndp-sim, current config, mapping,
bitstream, execplan, SCA, ZIP/package, upload, server run, or lease action is
authorized or claimed by this receipt.

