# Requant strict completion and QAdd dependency release — mainline

Date: 2026-08-06

Mainline task: `019fbec2-fe93-7e03-9314-cff6f222f33d`

Requant owner: `019fa2bf-95cd-7502-82c8-6a48cf12d648`

Optimizer owner: `019fd276-14c5-7800-94db-87ebfb9ce632`

## Final adjudication

The authoritative Requant status is:

`COMPLETE_LOCAL_STRICT_JSON_54_OF_54`

This supersedes the optimizer's earlier
`PASS_54_OF_54_EXACT_MULTIPLIER_PAYLOADS / strict candidate IN_PROGRESS`
interim receipt. The interim payload receipt remains valid provenance, but it
cannot regress the later strict candidate and exact family-set completion.

## Exact final receipts

Machine report:

`artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/report.json`

- bytes: `6607`
- SHA256:
  `9b426c6731be52e5a68eec300d6765cc1589cec2c1a3decea66fad107cdf9ddf`

Owner task record:

`.agents/task_records/20260806_requant_scalar_phase_strict_json_complete.md`

- bytes: `7611`
- SHA256:
  `9373ab2ef453fb9c87bbdb69b6ce7fe9f1f8656117e5c9533f70b0fc1a9323ed`

Coverage:

- strict JSON: `54/54`
- Conv per-channel stages: `53`
- MatMul scalar stages: `1`
- multiplier float32 elements: `26561`
- provenance leaves: `50095`
- unresolved leaves: `0`
- shared candidate validator: `54/54 PASS`
- candidate errors: `0`
- completion blockers: `0`
- exact family-set expected/covered: `54/54`
- family-set missing/unexpected/duplicate/type/SHA errors: all empty
- final tests: `23/23 PASS`

## Blocker delta

Closed:

- `B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION`
- `B_COMPLETE_JSON_REQUANT_SEQUENTIAL_RNE_ZP_SATURATION_COMPOSITE_CAPABILITY`

Preserved:

- `B_REQUANT_CONV53_SCALAR_PHASE_BACKEND_AND_DYNAMIC_EXECUTION`
- `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`
- `B_REQUANT_SERVER_E4_E5`

## Dependency release

The QLinearAdd dependency on Requant strict complete-JSON is closed.
QLinearAdd owner `019fa2c0-b647-7a91-93bf-d21a173487e3` has been reactivated
for the already authorized isolated six-qparam typed strict materializer.

The QAdd task remains restricted to local strict JSON plus shared candidate and
exact family-set gates. It may not generate mapping, bitstream, execplan, SCA,
ZIP/package, or perform server actions.

## Claim boundary

No native backend JSON, uniform backend rebase, mapping, bitstream, execplan,
SCA, package/ZIP, upload, run, lease, formal D, E3, E4, E5, functional RTL,
ISA, hardware, or active ndp-sim change is claimed.

