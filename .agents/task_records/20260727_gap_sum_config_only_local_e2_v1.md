# ResNet50 GAP sum-stage pure-config local E2 v1

Date: 2026-07-27

## RETURN_ANALYSIS

- Status: `CONFIG_ONLY_CORRECTNESS_BASELINE`.
- Scope: real `r5:hwop-0071-00` / node-0071 INT32 sum stage only.
- Functional RTL changes: none. `repair_v9`, `RTL_CONTROL`, and
  `CONFIG_SEMANTICS` repair routes were not consumed.
- Exact UINT8 tail: not materialized. The shared decision remains
  `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`; this record is not a complete
  QLinearGlobalAveragePool target.
- The six-stage tree is `49→25→13→7→4→2→1`, using serialized non-transout
  `int32_mac(A,1,C)` with explicit INT32 scratch and a same-mask barrier after
  every stage.
- Stage-1 uses aligned A/C bases and independent LC branches. A emits element
  indices `0,2,...,62`, C emits `1,3,...,63`; both use 8-byte transactions.
  Padding replaces indices outside the real 0..48 domain. This avoids the
  impossible `base+8` materialization because RTL discards the low four base
  bits.
- Stage-1 buffer spatial columns are `[0,4,8,12,16,20,24,28]` for the eight
  C8 lanes. A/C/D use independent roots (`LC0/LC2/LC4`) in every stage.
- Per-slice occurrences are `8192,4096,2048,1024,512,256`. Output byte
  coverage recomputed from each final JSON is respectively
  `262144,131072,65536,32768,16384,8192`; every region has exact, contiguous
  coverage.
- The config-bound simulator consumes all six final JSONs and the frozen W3
  input. Its INT32 output SHA-256 is
  `f838df652cadb27110ed79084f49fd7e80445277d497e0d6e019c49132b73117`,
  exactly matching the independent node-0071 sum golden; observed range is
  `[0,2477]`.
- Input replay is noncomputational: it replays only the formal output of
  `r5:hwop-0070-00`, tensor `tensor-55360f2ec724d2f3`, uint8
  `[16,2048,7,7]`, SHA-256
  `17751d21f3ece3ba1ba03eb9f54494ede7c9ccc2d4f915854ca76c4006a1fe3a`.
  Only the index/address view changes. The internal sum golden is comparison
  evidence and is never a replay source; no scaled, rounded, saturated, or
  final tensor is host-precomputed for replay.
- Logical JSON and final address-bound JSON have a leaf-complete diff for all
  six stages. The only differences are planner-owned `base_addr` leaves; every
  non-base diff count is zero. The validator recomputes this diff and the final
  occurrence/address coverage.
- Two isolated mapping runs produced identical core products for every stage:
  source config, mapping review, parsed bitstream, 64b/128b dumps, detailed
  dump, encoder source manifest, native mapping state, and stderr. Path-bearing
  diagnostic/evidence files are explicitly excluded and annotated in the
  validation report.

## Rule receipt

- `.agents/rules/算子配置规则.md`:
  `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc`
- `.agents/rules/生成前必读索引.md`:
  `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19`
- `.agents/plan.md` mutable provenance recorded at final artifact generation:
  `ff8180a9b90d8155d1ed63e3aa7480a69e67b21d3a54a95ecc95f2a744db100e`.
  It later drifted to
  `37fca5772e820c4a4c5cdefad05ae586e11fd7a963e4d340c177c80602440293`
  during validation and is intentionally excluded from semantic drift gates.
- The machine receipt includes
  `CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001` and
  `CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`.

## BYPASS_ANNOTATION

- `bypass_reason`: The real node-0071 sum must remain numerically runnable
  while all functional RTL repair routes are frozen.
- `contradicted_or_missing_native_path`: Native int32_sum/transout is
  contradicted by occupancy underflow, invalid-slot stale-C, and D-index
  coverage evidence. The old int32_mac v1 also materialized a 16B stream for an
  8B contract and placed C in an unrelated region. Repair routes remain frozen.
- `exact_equivalence_scope`: Frozen uint8 `[16,2048,7,7]`, x zero-point 0,
  C8HW8 node-0071 instance, exact INT32 sum of 49 values. All intermediate sums
  are in `[0,12495]`, so pairwise reassociation has no INT32 wrap.
- `materialized_configuration_mechanism`: Six serialized non-transout
  int32_mac stages, aligned even/odd 8B stage-1 reads, explicit 32B INT32
  scratch later, independent A/C/D branches, reload plus barrier at every
  boundary.
- `performance_and_resource_cost`: Six starts, six barriers, 16,128 GA output
  occurrences and 1,155,072 aggregate input/scratch traffic bytes per slice;
  647,168 bytes of addressed footprint through final D; no throughput claim.
- `unresolved_production_blocker`: No dynamic skew/stall/resume, normal-FIFO
  drain, formal 16-slice readback, E4/E5, native composite GAP handler, or
  exact UINT8 tail closure.
- `claim_boundary`: Sum stage only; not a complete GAP target, production or
  performance release, server identity, E3, E4, or E5.

## RULE_DELTA_PROPOSAL

Propose `CDA-GAP-INT32MAC-STAGE1-ALIGNED-EVEN-ODD-001`:

- For an 8B C8 pair read, do not express the right operand as `C_base=A_base+8`;
  the hardware consumes only a 16B-aligned stream base.
- Use the same aligned A/C base and independently owned LC item branches:
  A `start=0,stride=2`, C `start=1,stride=2`, with byte stride 8.
- Prove equal occurrence cardinality, ordered A/C pairing, padding bounds,
  independent branch roots, `[0,4,...,28]` buffer columns, and final D byte
  coverage from the final materialized JSON.

No shared rule file was modified by this task.

## BLOCKER_DELTA

- Closed locally: `B_GAP_INT32MAC_SUM_STAGE_MATERIALIZED_E2` for this exact
  identity, including typed input, six configs, mapping/bitstreams, static
  lifecycle, final-address coverage, and independent golden comparison.
- Closed locally: noncomputational W3 input replay ownership.
- Still open: `B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM`.
- Still open: `B_GAP_INT32MAC_STAGE_BARRIER` dynamic drain/visibility proof.
- Still open: `B_GAP_INT32MAC_FORMAL_READBACK` and all E4/E5 gates.
- Still open: native composite six-stage handler / approved native-pipeline
  integration. The local schedule uses the locked instruction encoders and is
  not a production pipeline release.
- Still open unchanged: exact UINT8 tail ordered-rounding topology, complete
  shape/full-domain proof, native transport, terminal, typed binding, and
  mapper registration. AverageRequant and singleton Quant diagnostics do not
  release these blockers.

## PACKAGE_RELEASE

- `candidate_release=false`
- `formal_target_instance_allowed=false`
- `server_package_allowed=false`
- `dynamic_baseline=NO_DYNAMIC_BASELINE`
- `complete_gap_target=false`
- `quant_tail_materialized=false`
- No server package was created, uploaded, run, or authorized.

Primary identities:

- Contract:
  `contracts/operator_config/gap_sum_config_only_local_e2_v1.json`
  file SHA-256
  `15318caf31dc13e702b66c9b0e7849a844210a5a887ef52cf3d84610e04be697`;
  semantic `contract_sha256`
  `6756d6aeae24418847ad9fc32beaedb9826dd64699379e12ad5f18892a4ba32d`.
- Artifact manifest file SHA-256:
  `f11ef01a4d804cb58440fb90e45789cd351a405cae15dba37f05986fd9eefefa`.
- Validation report file SHA-256:
  `b19157bc875d6d28b0ac8014e55abe94d0e6044227346019a64541b3d09bc019`.
- Config manifest file SHA-256:
  `4f812ef2d13acf4920dfd30fa3bc67d5e5c4113fdbe9f7ec1a9baf472a32c445`.

Validation commands:

```powershell
& <python> tools/validate_gap_sum_config_only_local_e2.py
& <python> -m unittest tests.test_gap_sum_config_only -v
```

Both passed; unit tests: 6/6.
