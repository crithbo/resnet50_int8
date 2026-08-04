# ResNet50 node-0002 MaxPool CONFIG_ONLY_CORRECTNESS_BASELINE

## RETURN_ANALYSIS

- task: unique ResNet50 MaxPool node `node-0002` / `r5:hwop-0002-00`
- result: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- evidence: local `E2`
- formal target instance: not allowed
- server/package/lease: none
- functional RTL changes: none
- forbidden-path changes by this task: none under `.agents/plan.md`, `.agents/rules/**`,
  or `rtl/**`
- active audited oracle:
  `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`
  @ `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- active reuse audit:
  `contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json`
  @ `ca3daf485f4098793e1c4544139c22e62119dbe5743e0db02e4e07d7c301c7c5`
- typed lowering:
  `contracts/resnet50_r5_lowering_bundle.json`
  @ `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- typed request:
  `6126a69fcd131b9fe3e12450acb2d54c5b6f93e91779a44150bf302ece018578`

The local chain is:

```text
typed node-0002
  -> guarded strict static MaxPool JSON
  -> native model_execplan planner/base binder
  -> three final address-bound JSONs
  -> current native mapper revalidation (penalty 0, no fallback)
  -> per-op 64b/128b bitstream and cfg_pkg
  -> 129-command Load_Config/Write_Reg/Start_Comp execplan
  -> SCA/SCA_D (28 + 28 + 8 = 64 occurrences)
  -> final-address/lifetime/coverage validator
  -> config-bound NDPFuncModel GeneralPEA
  -> W3 independent golden
```

Final materialization:

| op | active slices | A base | D base | final JSON SHA-256 | 128b bitstream SHA-256 |
|---|---:|---:|---:|---|---|
| op0 | 28 | 0 | 201168 | `f5ae3d62eba31d734561050365e39745fd5929759710d24f998fd7ff5c7d1e7b` | `f7dd01b39f03121b4512affd99b63f383c66e02f1a0e4e55c9cec9525b6e7f90` |
| op1 | 28 | 251344 | 452512 | `fdbffa712e8d27c0ed20c7d40aefe24b74b39770ec37d962ac2122bb7ce167d3` | `4ff4a3b5af97d09232e93944a433f239770babe38fa9a1a22edcc3117e2613a9` |
| op2 | 8 | 502688 | 703856 | `d7234bc66de82cd4a97245d472300e256007d5f608e6e3c6131a8e13ccd7dd0a` | `b0ab6bd119632cbc276c91f08a92fea502837676acd69fb79dcb747f121ae000` |

All three final configs independently passed native mapper recomputation with
`penalty=0.0` and `fallback_used=false`.  The mapping placement hash is equal
because only planner-owned bases differ; each address-bound JSON produced its
own bitstream identity shown above.  Two isolated locked-tool runs compared 35
native output files byte-for-byte after excluding only `config/*/placement.png`;
their deterministic tree identity is
`0d1b060012c72f81a22aa14fe85293752458d9ae9358984be3cf5bd7dac8b157`.

The final source-to-materialized leaf diff contains only:

- op1 `stream0.base_addr: 0 -> 251344`
- op1 `stream1.base_addr: 201168 -> 452512`
- op2 `stream0.base_addr: 0 -> 502688`
- op2 `stream1.base_addr: 201168 -> 703856`

op0 has no leaf diff.  No loop, `dim_stride`, transaction, connection, terminal,
constant, CONFIG, padding/tail or other non-base leaf changed.  Each allowed
base leaf has a unique planner/address-binder owner, graph input, formula, old
value, expected value and authorization in the machine contract.

Formal D coverage was recomputed from every final occurrence:

```text
address = D_base + channel_group*12544 + y*224 + x_pair*32
channel_group in [0,4), y in [0,56), x_pair in [0,7)
```

Each occurrence has 1,568 ordered 32-byte writes and exactly covers the
contiguous 50,176-byte D region.  Across 64 occurrences, formal written bytes
are 3,211,264, equal to the typed output element/byte count.  SCA_D contains
64 matching regions, each with 3,136 128-bit lines.

The config-bound simulator consumed only the formal W3 producer output
`tensor-f6c1a8fb6fd529e8` as its typed input.  It performed only index/address
selection and guarded C4HWC4 packing; it did not host-precompute or replay any
scaled, rounded, saturated, pooled, final-output or internal MaxPool tensor.
`tensor-8d2f28c80ac24676` was read only as an independent post-execution golden.
Results:

- logical elements: 3,211,264
- logical mismatches: 0
- physical mismatches: 0
- physical occurrences: 64
- ordered physical output SHA-256:
  `9185859e1b3437e9058a4cc9347b7b490e220aa188d84ba920c64be188d4a13f`
- complete output payload SHA-256:
  `e0e9a33d50f65c9a3a19f98926adb7767b07edc5783a5297ffbc73bec7368323`

The template remains an oracle/reuse source and is not treated as an automatic
target pass.  `target_simulator_validated=false`,
`formal_target_execution=false`, and `formal_target_instance_allowed=false`.

## BYPASS_ANNOTATION

```json
{
  "bypass_reason": "NONE_ARITHMETIC_REUSE_WITH_TARGET_BINDING_REQUIRED",
  "contradicted_or_missing_native_path": "the exact ndp-sim template is not an automatic target pass; native MaxPool handler registration and complete full-node dynamic target flow are missing, and the public GA INT8 max pipeline rule remains contradicted",
  "exact_equivalence_scope": "only frozen ResNet50 node-0002, batch16 uint8 [16,64,112,112] -> [16,64,56,56], 3x3 stride2 pads1, identical input/output qdomain",
  "materialized_configuration_mechanism": "three serialized native occurrences with 28+28+8 active slices, independent guarded C4HWC4 A/D allocations, native planner base binding, exact-zero mapper, bitstream, Load_Config/Write_Reg/Start_Comp execplan and SCA",
  "performance_and_resource_cost": "three config loads and Start_Comp stages; six independent physical allocations per slice address space; 64 tile occurrences; no throughput/resource-efficiency claim",
  "unresolved_production_blocker": "no authoritative target E4/E5 execution; no server identity or run; conflict between current isolated unsigned-byte-max evidence and public CDA-GA-INT8-MAX-PIPE-001 remains for mainline adjudication",
  "claim_boundary": "CONFIG_ONLY_CORRECTNESS_BASELINE; local E2 only; not production, performance, target-simulator, formal-D, E4 or E5 release"
}
```

## RULE_DELTA_PROPOSAL

1. No direct public-rule edit is requested from this task.
2. Mainline should adjudicate the scope conflict between
   `CDA-GA-INT8-MAX-PIPE-001` and the current hash-bound MaxPool isolated
   unsigned-byte comparison evidence.  This local E2 does not close the dynamic
   GA ready/flow or target-execution blocker.
3. The common `OperatorConfigExecPlanValidator` currently compares each native
   pipeline JSON byte-semantically against the static source and therefore
   rejects valid later-occurrence planner-owned base changes.  A future common
   validator change should allow only contract-declared planner-owned base
   leaves, check their values against `graph_withbaseaddr`, and continue to
   reject every undeclared non-base diff.  This task implements that stricter
   behavior only in the MaxPool family validator.

## BLOCKER_DELTA

Closed locally:

- exact frozen typed target binding
- 3-stage 28+28+8 occurrence closure
- guarded input storage and zero-padding identity
- final materialized leaf ownership
- final-address exact mapping and distinct bitstreams
- execplan/SCA/SCA_D occurrence and address binding
- per-occurrence D byte coverage and lifetime
- full-node config-bound local E2 mismatch=0
- deterministic native double run

Still open:

- authoritative target simulator/hardware execution
- E4/E5 and any three-party comparison
- dynamic GA ready/flow closure
- public GA INT8 max rule/evidence conflict adjudication
- production throughput/resource characterization
- native common-validator support for repeated planner-owned bases

## PACKAGE_RELEASE

```json
{
  "released": false,
  "package": null,
  "lease": null,
  "upload": false,
  "server_run": false,
  "reason": "local E2-only task; no server authorization and production blockers remain"
}
```

## Machine artifacts and verification

- machine contract:
  `contracts/operator_config/maxpool_node0002_config_only_e2_v1.json`
  @ `c9833c15844e17b17fbe492175c071d2cc3b19fbf749c6459f360b3ee67a02ce`
- graph:
  `configs/maxpool/node0002_config_only_e2_v1/graph.json`
  @ `ea475566692838281d448fb706d4e9d5d23ed19c0f3f64c22020594c0892269f`
- artifact bundle:
  `artifacts/operator_config_validation/maxpool-node0002-config-only-e2-v1`
  (88 files, 1,163,668 bytes)
- bundle manifest:
  `e8e8c7cf660ee6b30ba660e0f85d01de75959aa2c0e57c30340c23b8e959a28a`
- validation report:
  `5fb484e9c1bf40b86d68c21c8837e6a61978e63cac40e9e2f5b3b42ea3dd9a61`
- generator:
  `tools/build_maxpool_node0002_config_only_e2.py`
- validator:
  `tools/validate_maxpool_node0002_config_only_e2.py`
- directed tests:
  `tests/test_maxpool_config_only_e2.py`

Commands:

```powershell
.venv\Scripts\python.exe tools\build_maxpool_node0002_config_only_e2.py
.venv\Scripts\python.exe tools\validate_maxpool_node0002_config_only_e2.py `
  artifacts\operator_config_validation\maxpool-node0002-config-only-e2-v1
.venv\Scripts\python.exe -m unittest `
  tests.test_maxpool_config_only_e2 `
  tests.test_maxpool_config_bound `
  tests.test_maxpool_padding_contract
```

Result: validator `valid=true`; 14/14 directed and existing MaxPool tests passed.

Final public receipts:

- `.agents/rules/算子配置规则.md`
  @ `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc`
- `.agents/rules/生成前必读索引.md`
  @ `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19`
- `.agents/plan.md`
  @ `a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516`
  (mutable provenance only)
- config-only mainline policy task record:
  delegated identity `b73f528f...`; current generation-time identity
  `b7ec52e4f57dad22b1dbbe8a556f15d3aa8ea49a7a559c3968622e23d03b7b54`
  (receipt drift recorded; neither used as the semantic gate)
