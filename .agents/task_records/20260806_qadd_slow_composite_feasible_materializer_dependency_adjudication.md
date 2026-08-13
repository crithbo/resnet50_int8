# QAdd slow-composite feasibility and materializer dependency adjudication

Date: 2026-08-06

Owner task: `019fd276-14c5-7800-94db-87ebfb9ce632`

Status:
`QADD_EXISTING_PRIMITIVE_COMPOSITE_FEASIBLE_NO_STRICT_JSON`

## Numeric proof

Owner-worktree reachable-domain DP artifact:

`artifacts/operator_config_validation/r5_existing_primitive_slow_composite_proof_v1/qlinearadd/reachable_domain_sfu_segment_dp.json`

- bytes: `453795`
- SHA256:
  `d11a8109bdcd5edb342b5575024c30ae2981798bf348ed73661828bc127d563e`
- coverage: `17 × 65536 = 1,114,112` pairs
- minimum/maximum segments: `1 / 3`
- stages requiring more than current capacity 66: `0`
- twelve stages require one segment
- stages `0011`, `0049`, `0053`, `0057`, and `0070` require three segments
- padded coefficients/breakpoints: `66 / 65`
- `x >= breakpoint` dispatch mismatch: `0`

Single-FMA dequant remains invalid with `2888 / 8704` bit mismatches. The
reciprocal counterexample remains preserved.

## Read-only topology proof

Owner-worktree 9PE topology artifact:

`artifacts/operator_config_validation/r5_existing_primitive_slow_composite_proof_v1/qlinearadd/one_lane_rtl_topology_audit.json`

- bytes: `6916`
- SHA256:
  `90ce8c4ce016e987954be6980edd0ceb7c945b9a0db5c5490cc844de6d74b4e5`
- selectors: `4,4,1,3,4,3,4,3`
- final route: `PE32 → outport6 / src1`

The old four-lane pending state is explicitly superseded. Any stale use must
fail closed.

## Report and validation

Owner-worktree report:

`artifacts/operator_config_validation/r5_existing_primitive_slow_composite_proof_v1/qlinearadd/report.json`

- bytes: `18691`
- SHA256:
  `2759381f660496d57be7891efd2716c253276d13256b1fe22ccabdeae0e5e491`
- `valid=true`
- `errors=0`
- strict JSON count: `0`
- forbidden outputs: `0`
- direct tests: `10/10 PASS`
- negative controls: `7/7 PASS`

Owner task record SHA256:
`6d837f117674131bb25bb05b122f69e226933ff8e3f48712fc7966143c5aa992`

## Mainline adjudication

An isolated six-qparam typed materializer is within the user's previously
authorized existing-primitive B path. It must not start until the preceding
Requant/Quant shared-tail physical proof closes, because the user fixed the
dependency order as:

`Requant/Quant shared tail → QAdd → Conv`.

When that dependency closes, the materializer remains limited to local strict
JSON and shared complete-JSON gates. Mapping, bitstream, execplan, SCA,
ZIP/package, server action, functional RTL, ISA, hardware, and active
`ndp-sim` changes remain forbidden.

This proof establishes reachable-domain numeric feasibility and read-only
topology only. It does not claim generic Quant capability, strict
address/lifetime closure, backend E2, natural terminal, formal D, E3, E4, or
E5. Existing v36 server-package status is unchanged.
