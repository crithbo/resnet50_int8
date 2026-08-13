# Conv node0004 v41 return → v43 WRTERM2 compile fix

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Result: `PACKAGE_READY_NOT_RUN`
- Package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`

## RETURN_ANALYSIS

Formal return SHA256:
`b351089eb76255f23f8190e181a05cbe9bbac1d01c16b555b6eaa3af4424b011`.
Frozen source v41 SHA256:
`e314dfb65b1bc7b8ad0403aa559a79508073092988a45e20b8637f21917933b0`.

CRC/root/path, exact set, allowlist, per-file receipts, source binding,
package/install preflight, runtime-D-absent and observer identity pass. Actual
VCS is invoked, but compile exits 2 and run remains 125. Simulation never
starts, natural terminal is absent and formal D is `0/320`; E3/E4/E5 are false.

- LAST_PROVEN_GOOD:
  `PACKAGE_AND_INSTALL_PREFLIGHT_PASS_AND_VCS_PARSES_FINAL_OBSERVER`
- FIRST_DIVERGENCE:
  `VCS_SCOPE_RESOLUTION_FAILS_ON_OBSERVER_LINE_5974_TOKEN_MEM_IDX_GOTTEN`

The exact package-local observer line references nonexistent private leaf
`u_Memory_AG_Idx_Queue.mem_idx_gotten[1]`. The active module declares
`mem_idx_gotten_bit`, not `mem_idx_gotten`. Because compile fails before
simulation, v41 contains no corrected true-final or post-terminal chronology;
the DUT hang cause is not evaluated in this return.

The minimum repair removes this nonessential display-only private XMR. Existing
module-port tag/backpressure surfaces and qualified `wt_addr1` retain the
candidate split, so v43 does not introduce a replacement private XMR.

## Successor

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v43_wrterm2_compilefix.zip`
- bytes: `5855871`
- SHA256:
  `ba3c2df775c8f7f7bef47eec15d079651eb7c60e20145aca7dedef7345fe54e2`
- Sidecar bytes: `102`
- Sidecar file SHA256:
  `7f4fbd1f53f94bf7aa2eabef1cb7ea340f2550c26e6e4dbf3eef1776f539eb61`
- Command:
  `bash r5_n4_hw_v43_wrterm2_compilefix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- Expected return: `r5_n4_hw_v43_wrterm2_compilefix_return.zip`

The earlier v42 intermediate was generated before a material server/config
rule update and is `QUARANTINED_RULE_DRIFT_NOT_RELEASED`. It is not a runnable
identity.

## Current-rule validation

The final audit publishes one nine-row `release_gate_matrix`. Package/bootstrap,
runner/finalizer, actually referenced package-local HDL, changed observer and
return/result gates are blocking/applicable. Materialized config is not
applicable because final JSON, mapping, bitstream, execplan/SCA and runtime
payload are byte-equal after identity normalization:

- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`:
  `RECEIPT_REUSE_BYTE_EQUAL`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`: `NOT_APPLICABLE`

The final-exact predicate trace emits only `true_final`; stable count-one and
simultaneous push/pop do not emit events. Dropping `!push` and changing the
threshold both fail closed.

For the changed surface, no private XMR is required. Exact active
`Memory_AG_Idx_Queue.sv` bytes, filelist, instance, width three, clock and reset
are bound. Reinserted missing leaf, renamed public tag and wrong sibling path
all fail closed. The exact WRTERM2 span has 74 XMR occurrences, 37 unique real
consumers, 37 classified and zero uncovered. Actual-leaf deletion, actual
consumer typo and wrong sibling negatives fail closed.

The syntax frontend positive exits zero. Five syntax/scope/declaration
negatives exit `1/5/6/1/1`. The safe runner reaches the compile stub and exits
the expected 74; TERM harness exits zero while the runner returns 143 and
preserves partial evidence. Deterministic double build is byte-identical.
Final ZIP audit passes with zero errors.

## BLOCKER_DELTA and rule feedback

- Closed by v43: `B_CONV_NODE0004_V41_OBSERVER_MEM_IDX_GOTTEN_XMRE`
- Preserved but not reached:
  `B_CONV_NODE0004_WRTERM_FINAL_DESCRIPTOR_PREDICATE_AND_POST_TERMINAL_OWNER_UNRESOLVED`,
  natural terminal and formal D 320
- Not reopened:
  `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. The current impact matrix,
predicate trace, public-surface/XMR, causal-ledger and boundary-microtrace rules
are directly exercised; no non-synonymous rule delta is required.

Key receipts:

- `outputs/conv_node0004_v41_return_analysis/report.json`
  SHA256 `2e81a8ca65bb929f10ba8997b8e87c4f806318670a805211c6cea2ce5dd164a6`
- `outputs/conv_node0004_v43_package_validation/predicate_public_surface.json`
  SHA256 `01e67fa592f5206429ffb61e0a1c3b71c0fbdaebf091b325c260a24166077462`
- `outputs/conv_node0004_v43_package_validation/actual_hdl_consumers.json`
  SHA256 `566020040c4deae1b9972c9ba77d5902e74a4cdabb3130f36cff9f9e6799151f`
- `outputs/conv_node0004_v43_package_validation/observer_syntax.json`
  SHA256 `53aae8fc8e3799b3fdab1ff5cdf94dff1cee6ffd807a6dfe5faf0f50357cde04`
- `outputs/conv_node0004_v43_package_validation/runner_controls.json`
  SHA256 `494e26df4de259ac2679a15c3572de2d3962d11c744a048cc32a96dbad6e67b2`
- `outputs/conv_node0004_v43_package_validation/final_zip_audit.json`
  SHA256 `bdcfba2efd0cbbecb7aebffc0df064f87087ebbf867e1c3cec70b9e50f77b431`
