# ResNet50 node0071 complete GAP config-only local E2 and package-ready record

- date: 2026-07-29
- owner thread: GAP / QLinearGlobalAveragePool
- unique mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- status: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- package status: `PACKAGE_READY_NOT_RUN`
- functional RTL modified: false
- transout route consumed: false
- repair_v9 consumed: false
- server files/names/identity inspected: false
- uploaded/run/lease: false / false / false

## RETURN_ANALYSIS

The accepted `r5:hwop-0071-00` six-stage non-transout `int32_mac` sum tree
was consumed as `IMMUTABLE_FULL_BINDING`.  Its numerical analysis, validator,
mapping and simulator were not repeated.  Bound identities:

- sum contract file SHA-256:
  `15318caf31dc13e702b66c9b0e7849a844210a5a887ef52cf3d84610e04be697`
- sum semantic contract SHA-256:
  `6756d6ae282f21791273d87857e0717f8466b7397ff0f4a0f937a75ba4ba32d`
- sum artifact manifest SHA-256:
  `f11ef01a4d804cb58440fb90e45789cd351a405cae15dba37f05986fd9eefefa`
- sum validation report SHA-256:
  `b19157bc875d6d28b0ac8014e55abe94d0e6044227346019a64541b3d09bc019`

New work connected the shared ordered two-stage tail:

```text
sum stage-6 INT32 D @ 0x9c000, 8192 B/slice
  -> INT32-to-FP32 MUL, multiplier bits 0x3d878c94
  -> FP32 scratch @ 0xa0000, 8192 B/slice
  -> magic RNE + raw int32 subtract + uint8 saturation
  -> final uint8 D @ 0xa2000, 2048 B/slice
```

All producer/consumer aliases are exact, regions do not overlap, and a
same-mask barrier follows every one of the eight serialized stages.  Final
address equations prove 256 32-byte MUL reads, 256 32-byte FP32 writes, 256
32-byte FP32 reads and 64 32-byte packed UINT8 writes per active slice.
Formal final coverage is 2048 B/slice and 32768 B across 16 slices.

The config-bound complete-node executor consumed the frozen sum interface and
the final address-bound tail JSONs.  For 32768 outputs:

- sum range: `[0,2477]`
- scaled FP32 range: `[0.0,163.94297790527344]`
- scaled payload SHA-256:
  `8de2396abe4780a67a3deab90fd84cf04827047aa307d80375d6de380c917e04`
- final UINT8 payload SHA-256:
  `b0b78ce73942e90566b05edfe6bd5ca5e924d3865e0232b31a58d9ffabb41067`
- W3 mismatch count: `0`

Static-template to logical-config leaf diffs are explicit: MUL 171 changed
leaves, including 169 non-base semantic leaves; round 25 changed leaves,
including 23 non-base semantic leaves.  Every entry records owner, input,
formula, old value, expected new value and authorization.  Logical-to-final
binding changes exactly two base leaves for each tail stage and zero non-base
leaves.  Final coverage is recomputed from final occurrence/address equations.

Final receipts:

- operator rule:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- server package rule:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- GAP rule:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- plan mutable provenance:
  `65f8b1ab7ef14f68d0bf021fb8314d7f230869a351b41447431d108cf5e36a8e`

## BYPASS_ANNOTATION

1. `bypass_reason`: the real node0071 must remain numerically runnable while
   every functional RTL repair path is frozen.
2. `contradicted_or_missing_native_path`: the old `int32_sum`/transout route
   is contradicted by occupancy, stale-C and D-coverage evidence; repair_v9,
   RTL_CONTROL and CONFIG_SEMANTICS repairs remain frozen.  A fused
   multiply-plus-magic tail violates ordered FP32 materialization.
3. `exact_equivalence_scope`: only node0071
   `uint8[16,2048,7,7]`, `x_zp=0`, spatial count 49, sum `[0,2477]`,
   multiplier bits `0x3d878c94`, `y_zp=0`, and
   `uint8[16,2048,1,1]`.  No unconditional AverageRequant/Quantize capability
   is claimed.
4. `materialized_configuration_mechanism`: hash-bound six-stage sum reuse,
   explicit FP32 MUL scratch, independent magic RNE/subtract/saturation stage,
   eight config reloads and eight same-mask barriers.
5. `performance_and_resource_cost`: two extra `Start_Comp`, two extra
   barriers, 8192 B FP32 scratch per active slice and an extra full
   INT32/FP32 read-write pass; no throughput claim.
6. `unresolved_production_blocker`: final `Trassic2.0_RTL` commit is not
   bound; server dynamic execution/readback, E4/E5 and production
   timing/resource closure are absent.
7. `claim_boundary`: `CONFIG_ONLY_CORRECTNESS_BASELINE` for this exact
   node0071 local E2 only; not production, performance release or E3/E4/E5.

## BLOCKER_DELTA

Closed locally:

- exact UINT8 tail numerical ordering for this exact GAP instance;
- final JSON materialization and per-leaf ownership;
- sum-to-MUL and MUL-to-round address/lifetime/barrier chain;
- complete-node config-bound local E2;
- fail-closed package construction gates.

Still open:

- final `Trassic2.0_RTL` commit binding;
- actual dynamic dual-stream/barrier/readback behavior;
- compile/run/natural-terminal/formal-readback return;
- E4/E5, performance and production resource closure;
- GAP-to-node0072 whole-network binding.

No dynamic baseline is claimed.

## RULE_DELTA_PROPOSAL

No public rule edit is required.  This task consumed the new hard gates
`CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001`,
`CDA-SERVER-RESULT-GATE-CONJUNCTION-001`, and
`CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001` directly.  A future optional
operator-family rule may record this node0071-specific exact-tail instance,
but it must not generalize to full-domain AverageRequant or QuantizeLinear.

## PACKAGE_RELEASE

- install/package identity: `r5_node0071_gap_hw_v1`
- directory:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0071_gap_hw_v1`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0071_gap_hw_v1.zip`
- ZIP bytes: `1766963`
- ZIP SHA-256:
  `bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0071_gap_hw_v1.zip.sha256`
- validation:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0071_gap_hw_v1.validation.json`
- status: `PACKAGE_READY_NOT_RUN`
- intended compile count / simulation count: `1 / 1`
- actual compile/run count: `0 / 0`
- package preload entries / formal readbacks: `25 / 48`
- runtime readback targets in ZIP: `0`
- post-install target-absent negative control: pass
- two independent fresh package trees: byte-identical
- two deterministic ZIPs:
  `bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74`
  / same
- fresh-extract runtime preflight tree mutation: none
- return collector: manifest allowlist only
- PASS gate: compile 0 AND simulation 0 AND natural terminal AND loader/dump
  exact counts AND formal readback exact-set AND missing 0 AND mismatch 0
- sole server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

Machine contract:

- path:
  `contracts/operator_config/gap_node0071_complete_config_only_local_e2_v1.json`
- file SHA-256:
  `61c6c388b64621b1df81736d4a505072755672446c863e27d10f829e214ac2bf`
- semantic contract SHA-256:
  `5d98e0493eeb8c7caa9a34e8a3cc733db8def2b01de28698b0b05c4440ac4e90`

The protected node0004 v1 ZIP remains byte-identical with SHA-256
`335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989`.
