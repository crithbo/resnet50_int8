# Conv node0004 v72 return → v74 source-bound successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: serialized Conv node0004 correctness diagnostic only
- final status: `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

## RETURN_ANALYSIS

The v72 formal return passed internal ZIP/source/execution receipts and reached simulation with compile/run exit 0 and signal `NONE`, but had no natural DUT terminal and returned 0/320 formal D items. `mismatch=0` is not a numeric pass because all 320 items are missing.

The v71 write-attempt counting escape is closed: all 35 emitted records use accepted writes (`wr_en && !full`). The final qualified chronology is Memory queue write/pop 9/9 and empty, Buffer queue write/pop 27/23 with four live tokens, descriptor count 18, prepared count 20, input1 index 7. Therefore:

- LPG: `V72_ACCEPTED_WRITE_QUALIFICATION_CLOSES_V71_ESCAPE_AND_MEMORY_QUEUE_DRAINS_9_OF_9`
- FD: `POST_DESCRIPTOR18_MEMORY_QUEUE_EMPTY_AT_INPUT1_INDEX7_WHILE_BUFFER_QUEUE_HAS_27_ACCEPTS_23_POPS_AND_FOUR_RESIDENT_TOKENS`
- root: `UNRESOLVED_EXACT_SOURCE_TO_CONSUMER_TOKEN_OWNERSHIP`
- class: `MSE4_MEMORY_VS_BUFFER_POST_TERMINAL_EPOCH_SKEW`

No functional RTL defect or authorized config-leaf correction is proven by v72.

## Successor and local correction

The first generated v73 candidate was caught locally before server release because raw held `all_match/last` levels were marked as qualified progress. It was superseded without a server run. v74 corrects the semantics: raw match/last are state-only; only accepted enqueue (`wr && !full`), accepted dequeue (`rd && !empty`) and consumer handshake (`valid && ready`) advance qualified progress.

v74 contains the pinned source catalog, symbol-id-only plan, generated observer, generated parser, exact binding, generation report and final-ZIP contract. Exact regeneration of observer/parser/binding passes byte-for-byte. Four candidate signatures and the missing-enable/malformed-record negatives pass. The install-only runner opens 86/86 SCA inputs and passes normal/preflight-fail/compile-fail/HUP/INT/TERM publication controls.

## Release

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v74_sourcebound_epoch_diag.zip`
- bytes: `5210324`
- SHA256: `3a780d8e75768ee241c4cfca0ed738a97b691f6329d8ff247e5f5d4c96ef5400`
- command: `bash r5_n4_hw_v74_sourcebound_epoch_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v74_sourcebound_epoch_diag_<execution>_return.zip`
- final audit: `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`
- server action: none

## Rule feedback

`RULE_CONFIRMATION`: `CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001` is effective and non-redundant. It directly caught the held-level-as-qualified-progress escape before release. No public rule delta is proposed.
