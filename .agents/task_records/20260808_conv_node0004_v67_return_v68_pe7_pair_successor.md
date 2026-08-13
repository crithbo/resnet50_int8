# Conv node0004 v67 return -> v68 physical PE7 pair successor

- Formal return SHA: `1ac57340c9c37adae664be47d21364a9011a229ee440509a610238c087257c9b`; exact source v67 SHA: `be8fb8fd8cda13282cc1d740a837325ce811f7c1ad52d7efd096d71d56c0e83e`; execution `r1786169108703435693_3996582`.
- CRC/exact-set/source/preflight and compile/run/signal: PASS, `0/0/NONE`.
- Corrected-width shadow: PASS. Natural terminal false; formal D `320/0/320/0`; E3/E4/E5 `true/false/false`.
- LPG: `PHYSICAL_LC17_AND_LC18_REACH_PE7_MATCH_OUTPUT_AND_MSE4_INPUT1_FOR_NINE_TRANSACTIONS`.
- FD: `AFTER_NINTH_PE7_OUTPUT_PHYSICAL_LC17_LC18_REMAIN_PRESENT_BUT_TENTH_PE7_PAIR_MATCH_DOES_NOT_OCCUR`.
- v67 package-local observer target bug: mapper binds logical PE1/LC15/LC9 to physical PE7/LC17/LC18, while v67 sampled physical PE1 and LC9. Its all-zero PE1 record is withdrawn as causal evidence.
- Retained physical PE7 observer proves nine complete LC17+LC18 match/output/MSE4 input1 handoffs; the tenth pair boundary remains unresolved.
- v68 retargets and renames the feature to physical PE7 and adds inbuffer mode/keep/enable/clear/bp-mask state. Numeric/workload/config/golden/timeout/backpressure/RTL are byte-frozen.
- v68 ZIP SHA `372c6135f064dfb5847bedfea3741b8724113eb8e3b0c7f644e87f4fa877fdee`; deterministic double build PASS; final ZIP audit PASS/errors0.
- Storage: v67 moved to tested; v68 is the sole serialized-Conv pending ZIP.
- Command: `bash r5_n4_hw_v68_pe7_pair_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v68_pe7_pair_diag_r<epoch-ns>_<pid>_return.zip`.
- RULE_CONFIRMATION: current rules are sufficient when actual-consumer proof includes mapper logical-to-physical binding; no public-rule delta.
