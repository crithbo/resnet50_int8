# Serialized Conv node0004 v112 tuple-leaf TB-VCD package

Status: `PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE`

## Previous-version progress

v111 production compile/simulation/target entry succeeded and reproduced the same residual 32-unit prepared-data drain hold. Its 153-signal catalog mapped only 102 entries because 51 source-bound Memory_AG packed-vector bit-select leaves were absent from the VCD header.

## Current-version purpose

Preserve every v111 functional/config/workload surface while replacing those 51 unmappable identities one-for-one with passive actual-source leaf aliases, so input0 KEEP-last, input2 KEEP-last, prepared-data over-generation, downstream drain and successful completion are pairwise distinguishable in one return.

## Result

- Fresh package identity: `r5_n4_hw_v112b_tupleleaf_tbvcd`.
- Diagnostic mode: `TB_VCD_BOUNDED_CAUSAL_CONE`.
- Exact final ZIP: `outputs/conv_node0004_v112_tupleleaf_20260822/r5_n4_hw_v112b_tupleleaf_tbvcd.zip`.
- ZIP bytes: `6174828`.
- ZIP SHA-256: `e3430d478852f54ec164fa00407e3e9ef2032fded6857e6e842f87523efed6ec`.
- All 102 already mapped causal signals remain present; the 51 missing packed-vector bit-select identities are replaced one-for-one by passive bind-input aliases. The catalog remains 153 signals, covers 41 roles, and the 16 candidates × 4 boundaries matrix is complete and pairwise distinguishable.
- Actual successful v111 VCS argv/filelist/include/define/source identity is embedded. Predecessor catalog hashes that intentionally remain stable are explicitly reconciled to returned actual-compiled source hashes; every fresh leaf binds the returned actual Memory_AG source bytes.
- Workload, materialized config/mapping/bitstream, numeric, golden and functional RTL are byte-frozen. The retired derived ACK comparator remains absent.
- Deterministic ZIP, clean exact extraction, package preflight positive and pending-status negative, Python exact-set compile, HDL lexical/focused frontend, source-bound, TB-VCD semantic-v8, runner resilience, native-flow preflight, post-sim core, first-fresh and release admission all pass.
- The only warning is that 153 signals exceed the soft reference range; this is explicitly justified by retaining all prior evidence and replacing all 51 missing leaves. It is not a hard limit or release blocker.
- Managed storage was not written. No upload, lease, connection or server execution occurred.

Unique future command:

```bash
bash r5_n4_hw_v112b_tupleleaf_tbvcd/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01
```

## Claim boundary

This receipt proves only local package construction and exact gate completion. It does not claim production compile, simulation, target completion, natural terminal, Formal-D/E3/E4/E5, or root cause.
