# GAP node0071-D to Dequant node0072-A producer endpoint record

- date: `2026-07-29`
- unique mainline:
  `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- scope: owner-partition canonical shared endpoint, GAP producer section only
- status: `PARTIAL_GAP_PRODUCER_SECTION_READY`
- integrated endpoint closed: `false`
- claim: existing node0071 `CONFIG_ONLY_CORRECTNESS_BASELINE` reused;
  this task is not a new E2

## Control-plane and rule receipt

- mutable plan SHA256 at generation:
  `ca96023deebdc274d052fb3248143a5b8a3fa3c9ba5de0bee9d793bb0fcac54d`
- mutable plan SHA256 at final validation:
  `c19363826061ac6842f1946a1fd860d87917902f3fad199d589a739ab0003b03`
- plan role: mutable provenance only, not a semantic gate
- generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- common operator-config rule SHA256:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- GAP rule SHA256:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- Dequant operator rule SHA256:
  `f8cf7d2a041426f2b3348f3d02b570e3e559fe1a77c643a8393e77a2583e15a1`
- Dequant atomic dynamic contract SHA256:
  `cc9e5215d92e55b7440a07954503586c9a6d50f56fe505595341c0ba71358d85`

## RETURN_ANALYSIS

- Canonical manifest:
  `contracts/operator_config/resnet50_node0071_node0072_shared_endpoint_v1.json`
- canonical manifest SHA256:
  `43d144582f9231c720e385687ebcac064174737861cbd48e8520523c8bb5fcd5`
- GAP owner section content SHA256:
  `ba892ba6d1fc4b066e8258fe8cdb6e54b4e68e1dd0eadd9a56f18dd2f566e548`
- validator:
  `resnet50_pipeline/gap_node0071_dequant_node0072_shared_endpoint.py`
- validator SHA256:
  `935cb33da5c0cfc8a5c17f64b8cf86548590b554559e7be61e0f6b7fce38d33e`
- build/validate CLI:
  `tools/build_gap_node0071_dequant_node0072_shared_endpoint.py`
- CLI SHA256:
  `d856775c94d27fa1d5fe821aa366be817ced6c5c250aed4683a5b3f33a82f6c1`
- tests:
  `tests/test_gap_node0071_dequant_node0072_shared_endpoint.py`
- test SHA256:
  `8bc3552ed7473c4d1d8e5bee1b7dbe2f5d7c18ffaf9dbed99632cb944aae7e85`
- validation report:
  `artifacts/operator_config_validation/r5-gap-node0071-dequant-node0072-shared-endpoint-v1/validation_report.json`
- validation report SHA256:
  `4b2f936265e5051e4be25cdfb1be139514c390e12448e7a6243649bc05897daa`
- test result: `8 tests`, all passed
- numeric analysis repeated: `false`
- GAP sum/tail numeric reexecuted: `false`
- node0071 complete local E2 retested: `false`
- accepted reuse assets consumed: `true`
- package rebuilt or modified: `false`
- server inspected/uploaded/run: `false`
- lease acquired: `false`

The typed lowering bundle proves node0071-D and node0072-A share
`tensor-ab32f279540568c3`,
`resnetv17_pool1_fwd_quantized`, `uint8[16,2048,1,1]`, and identity SHA256
`70e76086c96394b1cc0a50cf316663b4ea1def7f0d0b73568dd83662d6556b55`.

The GAP producer-owned physical endpoint is frozen as:

- storage ID:
  `r5:activation:node-0071:D:tensor-ab32f279540568c3:batch-slice-sharded-16x2048-v1`
- allocation owner: `r5:hwop-0071-01:D`
- physical address space: `NDP_PER_SLICE_DDR`
- active slices: `0..15`; target slices `16..27` are inactive and are not
  endpoint padding
- active-slice base:
  `D_base(slice)=0x000a2000+(slice_id<<25)`
- allocation/view byte offset: `0`
- each active slice: `2048` valid/written bytes, `0` padding bytes
- each active slice occurrence:
  `addr=base+32*occurrence`, `0<=occurrence<64`
- aggregate written and valid bytes: `32768`
- producer visibility event: final uint8 D byte-set accepted and node0071
  completion/final barrier accepted
- release requirement: node0072 final A input-data accepted with no pending or
  replayed read; fallback is node0072 completion accepted

Only `owner_sections.QLinearGlobalAveragePool` is present.
`required_missing_owner_sections=["DequantizeLinear"]`. The Dequant owner must
either bind the exact storage/base/offset/coverage and materialize the
first-read/lifetime gate, or explicitly own a bridge. No differing consumer
layout is declared equivalent by this producer record.

Counts remain:

- complete ONNX local config-only E2: `3/78`
- fail-closed packages at `PACKAGE_READY_NOT_RUN`: `2`

## BYPASS_ANNOTATION

1. `bypass_reason`: preserve the accepted node0071 configuration-only producer
   while binding its D output into the whole-network endpoint.
2. `contradicted_or_missing_native_path`: repair_v9, transout, RTL_CONTROL and
   CONFIG_SEMANTICS repair routes remain frozen; no accepted native integrated
   node0071-to-node0072 lifecycle contract exists.
3. `exact_equivalence_scope`: only this accepted
   node0071 `uint8[16,2048,1,1]` D storage, active-slice bases, byte set and
   visibility/lifetime requirements.
4. `materialized_configuration_mechanism`: owner-partition canonical metadata
   binds the existing address-bound GAP D allocation; it adds no compute stage
   and does not replay an internal or final tensor.
5. `performance_and_resource_cost`: the manifest adds no compute or scratch,
   but the producer allocation must remain live through node0072 input
   acceptance. Any future bridge would add separately owned copy/relayout
   latency and storage.
6. `unresolved_production_blocker`: Dequant consumer section, integrated
   first-read/barrier/completion acceptance, native integration and E4/E5
   remain open.
7. `claim_boundary`: producer reuse is still only
   `CONFIG_ONLY_CORRECTNESS_BASELINE`; this is not a closed shared endpoint,
   new E2, E3/E4/E5, performance release or production release.

## BLOCKER_DELTA

Closed in the producer-owned section:

- typed node0071-D/node0072-A tensor identity equality;
- producer storage identity and allocation ownership;
- active/inactive slice partition;
- per-slice base and zero offset;
- exact occurrence equation and 32768-byte coverage;
- accepted local producer completion/visibility evidence;
- required live interval and release condition;
- immutable node0071 complete-E2 and existing package identities.

Still open:

- `B_GAP_NODE0071_TO_NODE0072_DEQUANT_CONSUMER_SECTION_MISSING`
- `B_GAP_NODE0071_TO_NODE0072_STORAGE_BASE_OFFSET_COVERAGE_MATCH`
- `B_GAP_NODE0071_TO_NODE0072_FIRST_READ_VISIBILITY_GATE`
- `B_GAP_NODE0071_TO_NODE0072_RELEASE_AND_NO_REPLAY_READ`
- `B_GAP_NODE0071_TO_NODE0072_INTEGRATED_CONFIG_BOUND_E2`
- native integration, final Trassic2.0_RTL commit binding and E4/E5

## RULE_DELTA_PROPOSAL

No public rule delta is proposed. The current owner-partition, reuse-first,
config-only replay boundary and GAP rules are sufficient. If the Dequant owner
later requires a differing physical layout, that branch must propose or bind an
explicit consumer-owned bridge contract; this producer task does not authorize
one.

## PACKAGE_RELEASE

- existing identity: `r5_node0071_gap_hw_v1`
- existing ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0071_gap_hw_v1.zip`
- existing ZIP SHA256 before:
  `bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74`
- existing ZIP SHA256 after:
  `bb5818c4071eacd220c669941169e181b51018d0591d85d51b01f0a7bd732b74`
- existing status: `PACKAGE_READY_NOT_RUN`
- new package generated: `false`
- existing package rebuilt or modified: `false`
- package count increment: `0`
- server run performed: `false`
