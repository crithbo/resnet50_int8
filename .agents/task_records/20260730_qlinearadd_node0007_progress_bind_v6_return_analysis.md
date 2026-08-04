# QLinearAdd node0007 progress-bind v6 return analysis

## Scope

This analysis consumes only the user-supplied immutable return ZIP and its
adjacent sidecar, the frozen source v6 ZIP, its final package manifest and
the already-frozen v4 workload/config/RTL semantics. It does not inspect any
other server path and does not repeat the 17-instance, W3 arithmetic,
qparam, golden or workload analysis.

## Formal receipt

```text
return:
  r5_qadd_n7_nested_lc_progress_bind_v6_return.zip
  bytes=146724
  SHA-256=07f04062b6d970fb0f1dd0d8e84a64a8c71429a2f4b90b3aadd00e904aed36c1
sidecar:
  present=true
  declared return SHA/name match=true
  file SHA-256=95d2123cf30f7f782a2142ab270e47e03ccef2e60f78171fa95884b85d173417
source package:
  r5_qadd_n7_nested_lc_progress_bind_v6.zip
  SHA-256=9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90
```

CRC, ZIP exact-set, per-record size/hash, manifest allowlist, source-package
exact-set and embedded/source manifest binding all pass. Package and
installed preflight pass; all 28 runtime D targets were absent before run.

Compile exited 0. Simulation was actually started and was externally
interrupted with `INT`, yielding status 125. Natural terminal was absent;
all 28 formal D readbacks are missing. `mismatch=0` is not evaluable and is
not a numeric pass.

## Qualified progress adjudication

The package-bound observer source and compile/runtime argv are present:

```text
time0 marker=true
observer binding=true
heartbeat=262144 active cycles
stall_window=1048576 active cycles
host simulation wall time=5326.679589581 seconds
EXEC_START count=1
heartbeat count=90
COMP_FINISH count=0
```

The first heartbeat is at active cycle 262144 and the last at 23592960.
Across 89 consecutive heartbeat deltas:

```text
qualified advancing windows=0
flat qualified active cycles=23330816
complete declared stall windows=22
final gexec/req/rdata/wdata=3/0/0/0
addr_enqueue/GA input/GA output/buffer activity=0/0/0/0
```

The observer counts `gexec2slice_fire`, `local_req_hs`, `local_rdata_hs`
and `local_wdata_hs`; raw levels do not establish progress. Therefore this
is not a slow-but-progressing run.

v6 has no canonical decision parser/contract/return target, so its formal
package status remains quarantined. A defensive manual adjudication of the
raw qualified counters is:

```text
LONG_RUNNING_HANG_AT_OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST
```

## First divergence and root-cause boundary

Last good:

```text
observer line 7
simulation time 16125913000
op_a_dequant EXEC_START accepted
gexec=3
```

First bad boundary:

```text
no DRAM LC address enqueue or MSE request handshake after Start_Comp
first observed active cycle=262144
conservative full-window confirmation active cycle=1310720
observer line=27
```

The frozen final `op_a_dequant` configuration does contain a shared-root
topology:

```text
read:  LC0 -> LC1 -> LC2 -> stream0(read A) -> buffer0 -> GA
write: LC0 -> LC3 -> LC4 -> stream2(write D from GA/buffer5)
LC1.src_id=DRAM_LC.LC0
LC3.src_id=DRAM_LC.LC0
```

RTL fixes the shared-root ready equation as:

```text
iga_lc_connect2ob_bp_post = &iga_lc_outport_bp_post
```

However, a further RTL review refutes that topology as a sufficient proof of
the zero-request root cause:

```text
Memory_AG_Idx_Queue.sv:
  mse_mem_queue_bp_pre =
    (!mem_ag_idx_queue_full && mem_idx_bp_pre_mask) || disabled_operand
  mse_mem_ag_tag_valid = !mem_ag_idx_queue_empty

WR_Data_Channel.sv:
  wr_data_chl_req_ready = !wr_chl_queue_full
```

The initially empty write-side index/request queues can therefore accept
initial address work without waiting for GA payload data. The shared LC0
AND-ready topology remains a candidate interaction, but it does not by
itself establish the alleged read/write combinational cycle. The defensible
root-cause status is:

```text
UNRESOLVED_WITHIN_OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST
```

The run is still a proven hang rather than an undersized timeout: 22 complete
qualified stall windows elapsed with no request/read/write progress. What is
not yet proven is the exact internal handshake that first blocks.

## Control delta

- Close the observer-binding and slow-vs-stall ambiguity.
- Open
  `B_QADD_NODE0007_START_COMP_TO_FIRST_MSE_REQUEST_HANG_ROOT_CAUSE`.
- v6 remains quarantined because canonical/self-audit is absent.
- v7 remains quarantined after rule drift.
- v8 also becomes
  `QUARANTINED_NOT_RUN_SAME_FROZEN_WORKLOAD_HAS_PROVEN_DYNAMIC_HANG`;
  it fixed diagnostic packaging but intentionally preserved this workload.
- No successor package is generated from an unproven address-only rewrite.
  The next diagnostic boundary must expose the active LC enable/output
  handshake and selected MSE index-queue input/match/full/request-ready
  signals. A functional successor then requires a proven cause, empty-state
  remapping and full local E2.

## Proposed rule delta

Proposed mainline-only rule:
`CDA-QADD-FIRST-REQUEST-HANG-INTERNAL-READY-OBSERVABILITY-001`.

A diagnostic package for a Start_Comp-to-first-request stall must qualify
and return the active LC enable/output handshake plus the selected MSE
index-queue input, match, full and request-ready boundary. Shared-LC topology
and AND-backpressure alone must not be reported as the root cause when an
empty MSE queue can accept initial work.

## Reproduction

Working directory:
`C:\Users\15383\Desktop\Codex\project\resnet50_int8`

```text
python tools/analyze_qlinearadd_node0007_nested_lc_progress_bind_v6_return.py
exit=0

python -m unittest
  tests.test_qlinearadd_node0007_progress_bind_v6_return_analysis -v
exit=0
tests=3/3 PASS
```

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-progress-bind-v6-return-analysis/report.json`

Report SHA-256:
`9252437ccfc3d4dfb62a3cddf5e9a9a378441637f1c808508beb8b4b7d230bca`
