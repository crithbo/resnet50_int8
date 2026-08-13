# Conv node0004 v74 recovered return to v75 collectfix

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

The recovered ZIP is the exact v74 execution `r1786246441849431853_141468`, not a rerun. CRC, root, exact-set, allowlist, per-file receipts, source package and publication path all pass. Compile and run exited zero with signal `NONE`, but the DUT did not naturally terminate and formal D is 0/320; E3/E4/E5 remain false.

The v74 source-bound parser rejected all 7280 valid records because its value alphabet omitted square brackets used by `%m` instance paths. Replaying the unchanged compact log with the current generated parser produces one decision: `POST_TERMINAL_TEMPORAL_OWNERSHIP_REQUIRES_RING`, with both Memory_AG and Buffer_AG terminal classes present. This refines, but does not close, the functional hang boundary.

v75 fixes only package-local diagnostics. It uses the current shared generated parser and converts simulator output automatically to a bounded causal projection containing ENABLE/SUMMARY/CLASS/TRIGGER/STALL/ring records. A 13,901,756-byte input becomes 2,701,756 bytes and retains the same decision. The new shared post-sim core helper persists simulator exit/finalizer state before the family plugin and publishes `EVIDENCE_INCOMPLETE` even if that plugin fails.

The final ZIP is deterministic across two builds. Shared source-bound exact regeneration, post-sim core-return scenarios and final ZIP self-audit pass with zero errors. Numeric, workload, configuration, golden, timeout, backpressure and RTL remain frozen.

- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v75_sourcebound_collectfix.zip`
- SHA256: `322214d94af5bdfe75e509612da190a205e7cf4324f9e31dcc6e052bb9b3126c`
- command: `bash r5_n4_hw_v75_sourcebound_collectfix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v75_sourcebound_collectfix_<execution>_return.zip`

Rule proposal: require an over-budget exact logger-to-collector-to-parser round trip for every changed source-bound return projection, including a negative that removes a legal `%m` instance character or restores full `sim.log` publication.
