# Conv node0004 v66 return -> v67 PE1 pair successor

- Formal return SHA: `c7dc6b54a7a2c47ca538cb99232b452377996fd5d1bc2558f7a0f4468261d80d`; source v66 SHA: `b0f4a0d83a82ccd1b039247da09318a1d9121ae08a9857f268a8568538050d1e`; execution `r1786159968158262861_3953004`.
- Receipt/CRC/exact-set/source/preflight: PASS; compile/run/signal `0/0/NONE`.
- Natural terminal: false; formal D expected/present/missing/mismatch `320/0/320/0`; E3/E4/E5 `true/false/false`.
- LPG: `LOGICAL_LC9_TO_PE1_INPUT2_ACCEPT_TWICE_AND_THIRD_DESCRIPTOR_TERMINAL_DELTA_RECOVERS_TO_ZERO`.
- FD: `PE1_RECEIVES_LC9_INPUT2_BUT_NEVER_FORMS_A_MATCH_OR_OUTPUT_FOR_MSE4_INPUT1`.
- Root status: `UNRESOLVED_AFTER_V66_EPOCH_OWNER`.
- v66 observer escape: 128 records contained only 14 distinct printed tuples because 23-bit LC values were compared through 21-bit shadows. v67 corrects shadow widths and observes the complete LC15/LC9 -> PE1 match -> ALU/outbuffer -> MSE4 input1 chain.
- v67 ZIP `5170405` bytes, SHA `be8fb8fd8cda13282cc1d740a837325ce811f7c1ad52d7efd096d71d56c0e83e`; deterministic double build PASS.
- Focused HDL/scope positive, missing declaration and actual-consumer typo negatives, predicate trace, install-only family harness, shared runtime layout, runner visibility, return conjunction, and final ZIP audit: PASS/errors0.
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`; no numeric/workload/config/golden/RTL/server action.
- Command: `bash r5_n4_hw_v67_pe1_pair_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v67_pe1_pair_diag_r<epoch-ns>_<pid>_return.zip`.
- RULE_CONFIRMATION: current rules sufficient; no non-synonymous delta.
