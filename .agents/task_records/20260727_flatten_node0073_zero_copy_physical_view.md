# Flatten node0073 zero-copy physical View contract

Date: 2026-07-27  
Test ID: `r5-flatten-node0073-zero-copy-view-v1`  
Family: `Flatten / View`  
Representative: `node-0073 / r5:hwop-0073-00 / flatten_473`  
Status: `ENDPOINT_BINDING_PENDING`

## RETURN_ANALYSIS

The typed chain is:

```text
node0072 DequantizeLinear D
  tensor-50c285690f899b1b float32[16,2048,1,1]
    -> node0073 View(axis=1)
  tensor-9b1363d3baf474c8 float32[16,2048]
    -> node0074 QuantizeLinear A
```

Node0073 is materialized as `execplan_metadata_zero_copy_alias`, not as an
arithmetic operator JSON. It emits zero View hardware configuration, zero View
instruction and zero View memory request. Logical tensor IDs remain distinct,
while the physical storage ID, allocation base and byte offset must be identical.
The allocation remains owned by the node0072-D activation allocation; View never
allocates or releases it, and node0074-A is a read-only borrower.

For C-order float32 tensors:

```text
input byte strides  = [8192,4,4,4]
output byte strides = [8192,4]
addr_in(n,c,0,0)
  = allocation_base + byte_offset + 4*(n*2048+c)
  = addr_out(n,c)
```

The validator exhaustively enumerated all 32,768 elements. The relative first
address is 0, the last element address is 131,068, and the required byte span is
131,072 bytes. Frozen W3 input/output `.npy` files are C-contiguous, byte-exact
equal and reshape-elementwise equal.

Accepted-handshake lifetime is ordered as:

```text
allocation.bind_accepted
< node0073.view_alias_bind_accepted
< node0072.final_output_write_accepted
< node0072.completion_accepted
< node0074.first_input_data_accepted
< node0074.final_input_data_accepted
< allocation.release_accepted
```

Release additionally requires no pending or replayed node0074 input read. If
final input-data acceptance is not observable, the conservative lifetime-only
fallback retains the allocation through `node0074.completion_accepted`; this
does not copy or replay data.

The public rule
`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001` is enforced. The logical
projection and final symbolic materialization have five changed leaves:
two non-base fields (`storage_id`, `allocation_owner_request_id`) with explicit
activation-allocator ownership and three planner-owned base/offset fields.
There are zero undeclared non-base changes. Since View owns no write stream,
formal output coverage is inherited from the node0072-D final written byte set.
The endpoint certificate must recompute and bind both the producer written-byte
set and consumer read-byte set from their final occurrence/address equations.

`CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001` is also enforced:
input/constant replay, copy and host-precomputed internal/scaled/rounded/
saturated/final tensors are all disabled. The only allowed data source is the
formal node0072-D producer output through the physical alias; calculation
ownership is unchanged.

Independent target local E2 is impossible by construction: View owns neither
endpoint allocation. Integrated target local E2 is currently false because no
final node0072-D/node0074-A addressed binding certificate exists. The machine
validator is ready to close it once the five source bindings and exact address,
stride, coverage and accepted-handshake fields are supplied.

## BYPASS_ANNOTATION

```text
bypass_reason:
  Flatten is an ONNX physical view; a computational operator would add
  non-semantic work, and functional RTL changes are frozen.

contradicted_or_missing_native_path:
  The legacy execplan intentionally excludes Flatten and the native
  operator-JSON/mapper path has no View computation to encode.

exact_equivalence_scope:
  Frozen node0073 axis=1 float32 C-contiguous
  [16,2048,1,1] -> [16,2048] instance.

materialized_configuration_mechanism:
  Planner/execplan metadata alias with one storage identity, equal base+offset,
  zero View instruction and zero View memory request.

performance_and_resource_cost:
  Zero copy traffic and zero View compute. The node0072 allocation remains live
  through node0074 final accepted input data, increasing live-range pressure and
  potentially constraining scheduling.

unresolved_production_blocker:
  Node0072-D and node0074-A final addressed layout/execplan plus accepted-
  handshake lifetime and final occurrence/address coverage certificate.

claim_boundary:
  status=ENDPOINT_BINDING_PENDING, claim_label=null, claim_enabled=false.
  CONFIG_ONLY_CORRECTNESS_BASELINE is only the eligible label after endpoint
  binding passes. No production/performance/E4/E5 claim and no independent
  target local E2.
```

No copy or replay fallback was materialized.

## Precise endpoint dependency interface

Node0072 must supply:

- `r5:hwop-0072-00` D storage ID and allocation owner;
- final `allocation_base + byte_offset`;
- C-order byte strides `[8192,4,4,4]` and a 131,072-byte visible span;
- final output write accepted and completion accepted events;
- the final occurrence/address unique written-byte set;
- hashes for addressed execplan and producer layout contract.

Node0074 must supply:

- `r5:hwop-0074-00` A bound to the same storage ID/base/offset;
- C-order byte strides `[8192,4]` and a 131,072-byte read span;
- first/final input-data accepted events and a no-pending/no-replay release proof;
- the final occurrence/address unique read-byte set;
- hashes for addressed execplan and consumer layout contract.

The binding certificate additionally requires a hash-bound allocator plan.
All five source files are opened and SHA-256 verified by the validator.

## RULE_DELTA_PROPOSAL

Mainline has published `Flatten_View算子配置规则.md` at
`28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee`.
The generator and validator now bind all five active View rule IDs:

1. `CDA-VIEW-METADATA-ONLY-001`
2. `CDA-VIEW-PHYSICAL-IDENTITY-001`
3. `CDA-VIEW-ENDPOINT-COVERAGE-001`
4. `CDA-VIEW-ACCEPTED-LIFETIME-001`
5. `CDA-VIEW-INTEGRATED-CLAIM-BOUNDARY-001`

No further rule delta is proposed.

## BLOCKER_DELTA

Keep open:

- `B_VIEW_PRODUCER_ALLOCATION`
- `B_VIEW_CONSUMER_ALLOCATION`
- `B_VIEW_BYTE_OFFSET_IDENTITY`
- `B_VIEW_BUFFER_LIFETIME`

The previous broad logical uncertainty is narrowed: shape, dtype, order, strides,
full element mapping, ownership, no-op materialization and release semantics are
closed locally. The remaining blockers are exact endpoint materialization inputs,
not View arithmetic.

## PACKAGE_RELEASE

```text
state: NOT_BUILT
server_package: false
rtl_entries: 0
lease: none
upload_or_run: false
reason: local metadata/contract task; exact endpoint binding is still pending
```

## Deterministic identities

| Asset | SHA-256 |
|---|---|
| `configs/view/node0073_zero_copy_view_v1.json` | `a63655c339ab68b7edad6d7c9a30776d369749dda80d3b5661152ec07582bddc` |
| `contracts/operator_config/flatten_node0073_physical_view_v1.json` | `067351563c40fb1b95e63f3b327e9758f19c49c72d3c48b348d223426ada9851` |
| `artifacts/operator_config_validation/r5-flatten-node0073-view-v1/validation_report.json` | `62b92ffad44bc89ea6e6a97c6f77110170e208ccefde0f63ffed1cabea61b13c` |
| `artifacts/operator_config_validation/r5-flatten-node0073-view-v1/manifest.json` | `078a3f6df952750684214a1e3db931eaf019b788c6dc6d7b7dbd4c5cc58285fb` |
| `resnet50_pipeline/flatten_physical_view.py` | `811032594396c552041c9f5b2ddf29cd27352b02da31288c8184dd3fdb93359c` |
| `tools/build_flatten_node0073_physical_view.py` | `14a9c80c70b2d79b45facb9e42a98d49364d0a2d26fb73e4465aa94bd785ec26` |
| `tools/validate_flatten_node0073_physical_view.py` | `e6744eccf10268d46efed829354228fc789326a36d0ed9acc68e7500dd58e4d6` |
| `tests/test_flatten_node0073_physical_view.py` | `6f5cf0980d4580e7c30234090b32310829dc5e8f3aa2712b5e52a0f87ad69686` |

## Validation

```text
.venv\Scripts\python.exe -m unittest \
  tests.test_flatten_node0073_physical_view -v
Result: 6/6 PASS

.venv\Scripts\python.exe tools\validate_flatten_node0073_physical_view.py
Result: valid=true, enumerated_element_count=32768,
        undeclared_nonbase_changed_leaf_count=0,
        integrated_target_local_e2=false

.venv\Scripts\python.exe -m py_compile \
  resnet50_pipeline\flatten_physical_view.py \
  tools\build_flatten_node0073_physical_view.py \
  tools\validate_flatten_node0073_physical_view.py \
  tests\test_flatten_node0073_physical_view.py
Result: PASS
```

`pytest` was not available in the local virtual environment, so no dependency
was installed; the same directed suite ran with the standard-library
`unittest` runner.

## Read receipt

- `.agents/agent.md`:
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- `.agents/plan.md`:
  `a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516`
  (`mutable_provenance=true`)
- `.agents/rules/生成前必读索引.md`:
  `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19`
- `.agents/rules/算子配置规则.md`:
  `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc`
- `.agents/rules/Flatten_View算子配置规则.md`:
  `28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee`
- mainline config-only policy:
  `b7ec52e4f57dad22b1dbbe8a556f15d3aa8ea49a7a559c3968622e23d03b7b54`
  (the original semantic policy plus the mainline task-roster append)

`NDP硬件字段语义.md` was omitted because View emits no LC/MSE/Buffer/SA/GA/N2N
field. The server-package rule was omitted because no package is generated or
authorized.
