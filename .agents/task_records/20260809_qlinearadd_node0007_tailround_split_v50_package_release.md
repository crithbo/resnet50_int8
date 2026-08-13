# QLinearAdd node0007 isolated tail_round v50 package release

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN`
- evidence: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY`

## Scope

This is a real one-stage split workload containing only `op_tail_round`. It consumes 28 explicitly host-precomputed FP32 diagnostic boundary tensors. `host_precomputed_internal_tensor=true` and `producer_evidence_claimed=false` are part of the package contract. A pass proves only isolated tail-round natural terminal plus exact stage-local UINT8 28D. It does not prove `op_tail_mul`, upstream producer/barrier/lifetime behavior, the corrected six-stage chain, E3, E4 or E5.

The changed config is limited to `op_tail_round` `GROUP2.COL_LC.end: 32 -> 4` and `stride: 16 -> 2`. The accepted windows composed with the native interleaved spatial stride are disjoint and exactly cover the physical 32-byte Buffer5 row. Seven overlap/gap/alias negative controls fail closed.

## Package

- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_split_v50.zip`
- bytes: `70642481`
- SHA256: `c8d1b3c4d43e1a4ec2360226d882881413de6da4739b20a08df43aa70fa6cad3`
- sidecar receipt SHA256: `53d9b641ef6ca2e64054af7b7d391fbe01afd0d82281bd204554ae4e7d00339e`
- command: `bash r5_qadd_n7_tailround_split_v50/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- expected return: `/home/panqs/ndp/simresult/r5_qadd_n7_tailround_split_v50_r<execution>_<attempt>_return.zip`

Storage rotation moved the formally consumed v49 source to `tested`; QAdd has exactly one pending ZIP, v50.

## Validation

- deterministic double build: PASS
- family validation: PASS, errors=0, SHA `fd294e692c5055b0e1dc86b8a6832e8d4e261537d1df79e9764ff5ea35ec45ff`
- shared install-only/runtime layout: PASS, errors=0, SHA `99863234653d5c22f7a7fc98193ce3b9af73ff73acda9009e84318fb299c7ca7`
- final ZIP rule self-audit: PASS, errors=0, SHA `d941ccadb9b1267fc85fc309f2e991783d1153357de3582f756c548bb2652ac5`
- exact package runtime preflight: PASS
- canonical parser self-test, including zero-padded decimal `02`: PASS
- package-local HDL compatible frontend, declaration/use/update closure, XMR scope and three negative classes: PASS
- runtime D initially absent: PASS
- storage audit: PASS
- server action: false
- numeric/workload analysis repeated: false

## Blocker delta

Closed locally: `B_QADD_NODE0007_TAILROUND_COL_SPATIAL_STRIDE_ALIAS`.

Open pending return: isolated tail-round natural terminal and stage-local exact 28D. Even after that passes, corrected six-stage natural terminal and formal 28D remain required.

## Rule delta proposal

Refine `CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001` to reconstruct the accepted byte set from COL occurrence bases composed with the full encoded spatial-stride sequence modulo physical buffer-row bytes. COL stride 2 is not intrinsically invalid: with native interleaving, bases 0 and 2 exactly cover `[0,32)`, while bases 0 and 16 alias the same 16-byte set.

Machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-v50-package/release_report.json`.
