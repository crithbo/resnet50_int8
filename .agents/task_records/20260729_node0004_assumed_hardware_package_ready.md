# node0004 assumed-hardware package ready

Date: 2026-07-29

## Control decision

The user directed the mainline to assume that the server-side hardware is
compilable and that the required repaired semantics are available. This
assumption unlocks fresh local materialization and package generation. It does
not constitute a verified RTL identity, E4, E5, or a formal three-party pass.

Historical node0004 materialized assets remained forbidden. The fresh build
consumed only the typed request/lowering, formal ONNX/W3 inputs, active rules,
locked native templates/tool sources, and newly generated artifacts.

## RETURN_ANALYSIS

- Status: `PACKAGE_READY_NOT_RUN`.
- Target: `node-0004 / r5:hwop-0004-00 + r5:hwop-0004-01`.
- Logical operation: complete QLinearConv output, including INT32 accumulate
  and INT32-to-UINT8 per-channel requantization.
- Accumulate route: three normal four-lane SA waves.
- Tail route: 24 independent two-stage pairs:
  `FP32 MUL -> explicit FP32 scratch/barrier -> RNE/saturation`.
- Materialization: 51 mappings, three Conv execplans and 24 tail execplans.
- Package execution model: one compile and 27 simulations.
- Hardware-produced Conv INT32 readback is mechanically relaid out from HWC16
  to the selected HWC8 half for the tail. No arithmetic is performed by this
  relayout and no host-precomputed scaled, rounded, saturated or final tensor
  is supplied to the target computation.

## Local evidence

- Full frozen W3 elements: 3,211,264.
- Actual dot4 groups: 51,380,224.
- Observed dot4 range: `[-25736, 20597]`.
- Accumulate mismatch: 0.
- Tail mismatch: 0.
- Accumulator SHA-256:
  `1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`.
- Output SHA-256:
  `2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e`.
- Scaled FP32 SHA-256:
  `0c60286a1c5b3124386d828d7e5539277fef9790c68ded85131f0244d7d007ff`.
- Multiplier SHA-256:
  `e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2`.
- Magic-domain proof: finite, scaled range
  `[-395.55010986328125, 177.30532836914062]`.
- Local numeric report:
  `artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1/local_numeric_report.json`,
  SHA-256=`cf653e51d388c5194aea8ee66db9594dcbb90dd35a1f1a75244757a1d28fbc42`.

The final packaged runtime was checked locally against 320 readback records:
320 present, zero missing and zero mismatching bytes. A missing-readback
negative control produces `NODE0004_SERVER_FAILURE` and a nonzero process exit.

## Package release

- Directory:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1.zip`
- ZIP SHA-256:
  `335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989`
- Sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1.zip.sha256`
- Validation receipt:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1.validation.json`
- Package files: 1,147 including `package_manifest.json`.
- Manifest: one compile, 27 simulations, 128 hardware-output relayout records,
  320 readback checks.

No server file, server name, Makefile/filelist or RTL identity was inspected.
No upload or server run occurred. There is no `SERVER_RUNNING` lease.

## BLOCKER_DELTA

Closed for the local assumed-hardware profile:

- Fresh node0004 configuration materialization.
- Normal four-lane accumulate full-W3 software/config-bound comparison.
- Direct signed two-stage tail full-W3 software/config-bound comparison.
- Mapping, bitstream, execplan/SCA and package assembly.
- Package immutable exact-set preflight and result-gate behavior.

Still open:

- Real server compile/simulation/readback.
- E4 and E5.
- Verified repaired server RTL identity, if later required by hardware handoff.
- Expansion to the remaining 52 Conv instances.
- Whole-network allocator/address/lifetime and 133-stage integration.

## Claim boundary

This result is a fresh complete-node local configuration baseline under the
explicit hardware-available assumption. It is not a server pass, not E4/E5,
and does not change the formal ResNet50 three-party count.
