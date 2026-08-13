# Conv node0004 v43 return → v47 LC9 split successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Result: `PACKAGE_READY_NOT_RUN`
- Package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`

## RETURN_ANALYSIS

The formal v43 return ZIP has SHA256
`5ed315d6121dba0a7e2bc81b9672ab8604c66a5b32b280b647dbc2e5af6b4e11`;
the frozen v43 source package has SHA256
`ba3c2df775c8f7f7bef47eec15d079651eb7c60e20145aca7dedef7345fe54e2`.
CRC/root/path, exact set, allowlist, per-file receipts, source binding,
package/install preflight, runtime-D absent and feature binding pass.

Production VCS compile/elaboration/link succeeds with exit zero, proving the
v41 private-XMR compile escape is closed. Simulation starts and the diagnostic
runner exits zero without a signal, but the DUT does not reach natural
terminal. Formal D is `0/320` present, `320` missing and `0` mismatch; therefore
`E3=true`, `E4=false`, `E5=false`.

`LAST_PROVEN_GOOD` is
`32_MEMORY_DESCRIPTORS_CONSUMED_AND_DESCRIPTOR_FIFO_DRAINS_WHILE_BUFFER_DATA_PATH_REMAINS_ACTIVE`.
The descriptor FIFO one-to-zero pop carries `last=1,last_index=5`, so it is not
the global `last_index=0` transaction. After that pop, the Buffer path continues
with 19 source pushes, three tag pushes and two prepare events until
source/tag/prepared state reaches capacity, while the MSE4 Memory buffer carrier
does not return.

`FIRST_DIVERGENCE` is
`MSE4_MEMORY_BUFFER_CARRIER_STOPS_BEFORE_GLOBAL_LAST0_WHILE_BUFFER_AG_SOURCE_CONTINUES_TO_CAPACITY`.
The return does not expose the first non-acknowledging consumer on the shared
LC9 branches. Root cause therefore remains
`UNRESOLVED_REQUIRES_SHARED_LC9_BRANCH_DIAGNOSTIC`.

## Cloud RTL causal-cone refresh

The successor binds cloud authority commit
`0ccae916ef61904a64d6cf8ec1d1931b45e428d8`. Only the serialized Conv causal
cone was revalidated: the updated ROW-LC FIFO, Buffer-AG index depth, request
queues and SA ping-pong valid qualification. Seventeen actual observer consumers
are classified and covered, with `uncovered=0`. The local/cloud identity
difference is reported but does not block compile or simulation.

## Successor

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v47_lc9_split_cloudrtl.zip`
- bytes: `5860314`
- SHA256:
  `516173e54132e2ee31cf2d4f750c46a595bb0bf31afb7f5b6661fc5a0ed6a015`
- Sidecar bytes: `102`
- Sidecar SHA256:
  `15ba6b9c7ada9a81e76aff98c6c464eb3006b1965cc7aa44463595fd4873b39c`
- Command:
  `bash r5_n4_hw_v47_lc9_split_cloudrtl/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- Expected return:
  `r5_n4_hw_v47_lc9_split_cloudrtl_return.zip`

The one low-cost feature `RETURN_OBS_LC9_SPLIT` records only qualified
handshakes and bounded edges for LC9 advancement/backpressure, PE1 input-2
accept/match/output, Memory MSE4 port-1 accept, ROW4 accept/output, Buffer source
push and global-last0 propagation. It distinguishes shared-branch backpressure,
PE1 internal match, Memory port-1 acceptance, Buffer row-pipeline acceptance and
loss of terminal metadata. Count/empty/level values remain state corroboration,
not progress.

v44/v45/v46 are intermediate quarantined identities and are not runnable.
v47 is the unique successor.

## Current-rule final audit

Deterministic double-build is byte-identical. The nine-row release-gate matrix
marks only changed causal surfaces as blocking. Frozen numeric/W3/golden and
materialized config/mapping/bitstream/execplan/SCA are receipt-reuse or not
applicable; no numeric, workload or config analysis was repeated.

The cloud causal-cone check passes with 17 actual consumers and zero uncovered.
Focused compatible-front-end HDL positive exits zero; declaration/task/consumer
negatives exit `6/1/1`. Predicate trace and all feature fail-closed negatives
pass. Safe compile runner reaches the compile stub and exits the expected `74`;
TERM finalizer returns `143` while preserving partial evidence.

The first final-audit run rejected the feature marker because the validator
compared the SystemVerilog source format string (`%0d`) with the runtime-expanded
literal (`128`). The validator was corrected to verify both representations
separately. No ZIP byte changed. The final independent ZIP audit now has
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`.

## BLOCKER_DELTA and rule feedback

- Closed:
  `B_CONV_NODE0004_V41_OBSERVER_MEM_IDX_GOTTEN_XMRE`,
  `B_CONV_NODE0004_WRTERM_TRUE_FINAL_DESCRIPTOR_IDENTITY_UNOBSERVED`
- Opened:
  `B_CONV_NODE0004_SHARED_LC9_TO_MEMORY_AND_BUFFER_BRANCH_ACCEPT_UNOBSERVED`
- Preserved:
  `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`,
  `B_CONV_NODE0004_FORMAL_D_320`
- Invalidated and not reopened:
  `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. The current release-gate,
predicate-trace, actual-consumer/XMR, cloud-authority, causal-ledger and
boundary-microtrace rules directly produced executable evidence; no
non-synonymous rule delta is required.

Key receipts:

- Return report:
  `outputs/conv_node0004_v43_return_analysis/report.json`,
  SHA256 `c0cf6cfaa028288f066d6d9f9f86e52829e19319e23a017d3ede1e4c68099541`
- Cloud causal cone:
  `outputs/conv_node0004_v47_package_validation/cloud_rtl_causal_cone.json`,
  SHA256 `80649faa65b33ec22119ba7d159936396cac44a7488b956a47c1c045eebf7869`
- Observer syntax:
  `outputs/conv_node0004_v47_package_validation/observer_syntax.json`,
  SHA256 `892be69696212a2f91ac4a806d2137dee069b37a692a5b538e7776104e282731`
- Predicate trace:
  `outputs/conv_node0004_v47_package_validation/predicate_trace.json`,
  SHA256 `c39eeb9a4c1f3b5968ce9d39a067c815d4be089a947fe7f520fcbe616a5d5a31`
- Runner controls:
  `outputs/conv_node0004_v47_package_validation/runner_controls.json`,
  SHA256 `4fcd2c968f4d3788a970fe578f8a4083de7165e0aa84181807916c18bc01ea0b`
- Final ZIP audit:
  `outputs/conv_node0004_v47_package_validation/final_zip_audit.json`,
  SHA256 `f30ffbba3a1fe002ba5ca80ab4a49c96e02e16db684cb0d22f5b86646f44b599`
