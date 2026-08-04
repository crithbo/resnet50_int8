# GAP node0071 old-v10 run snapshot analysis

- Date: 2026-07-31
- Owner thread: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- Family: QLinearGlobalAveragePool / node0071
- Claim boundary: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- Final receipt classification: `RETURN_SNAPSHOT_NONAUTHORITATIVE`

## RETURN_ANALYSIS

Input:

```text
C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\run_r5_n71_gap_v10_return.zip
bytes=107914483
sha256=16c85049ea361134892d228b5ad618f0f810c2c1bda21fa7e503bddafa79a50c
adjacent .zip.sha256=ABSENT
```

All 251 ZIP entries streamed without CRC error; unsafe paths, duplicates and
symlinks are all zero. The archive has two roots:

```text
run_r5_n71_gap_v10_runner_guard/
evidence_r5_n71_gap_v10_runner_guard/
```

It includes `csrc/`, `simv.daidir/`, libraries and a complete `sim_results`
tree. Compressed size is 107,914,483 bytes and uncompressed size is
525,944,887 bytes. This is a manually archived run/evidence directory
snapshot, not a manifest-allowlist return.

The internal package identity is nevertheless determinate. Its
`PACKAGE_MANIFEST.json` SHA-256 is
`778812941033e82b0af133be6cef2ba24fe4bc3ea2a9859aaf2a64a7f9608ff3`,
byte-identical to the manifest in:

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v10_runner_guard.zip
source ZIP sha256=1293d2f3868974edefad562bc28d9128a23bf3ff609df096bd68c11fd6a3a2b8
```

Therefore this is an old `r5_n71_gap_v10_runner_guard` run snapshot, not a
formal return and not current v12 evidence. Current control already
quarantines v10.

The manifest declares 70 allowlist entries, 68 required. Only 13 source
artifacts are present in snapshot form, of which 11 are required. Missing are
57 required items, including:

- `RETURN_MANIFEST.json` and `SERVER_RESULT_GATE.json`;
- compile/simulation/runner exit status and signal status;
- runtime observer-binding result and canonical decision;
- SCA/SCA_D accepted copies;
- all 48 formal D readbacks.

The formal conjunction is false/unevaluable. `E3=false`, `E4=false`,
`E5=false`.

## Diagnostic evidence extracted from the snapshot

- Installed preflight says valid, 25 preloads, 48 declared readbacks,
  runtime D initially absent and no server source files inspected.
- Observer precompile binding is valid. Its source SHA is
  `0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8`;
  actual compile/simulator argv are present and simulation prints
  `[0] [RETURN_OBSERVER] enabled for slice 0`.
- Compile log naturally reaches `Compilation completed!`, with VCS reporting
  0 errors and 1 warning. Formal compile exit status is absent.
- Simulation starts, loads 25 matrices from the v10 SCA namespace and starts
  execution at `702681000 ps`. It has no natural terminal and no formal exit
  or signal receipt.

Qualified last-good events:

```text
702764000 ps  MSE3_TO_BUFFER4 accepted, count=1
702772000 ps  MSE0_TO_BUFFER0 accepted, count=1
```

Across 169 heartbeat windows through `56080599000 ps` and
`44302336` active cycles:

```text
ga_operand0_capture=0
ga_operand2_capture=0
ga_joint_accept=0
ga_output=0
mse4_write_data=(0,0)
terminal=0
```

This is at least 42.25 declared `1048576`-cycle stall windows after the
initial producer acceptances. Raw buffer/ready levels are excluded from
progress.

The host sampler covers 8581.701 seconds. Observer output stops growing at
`56080599000 ps`, then remains byte-identical for at least 3541.259 seconds.
Because the manual snapshot lacks signal/finalizer/canonical records, this is
only a sim-time/output-freeze witness; it cannot distinguish process
suspension, zero-time/tool stall or another execution-layer stop.

## FIRST_DIVERGENCE

Receipt layer:

```text
MISSING_ADJACENT_SIDECAR
+ MANUAL_RUN_TREE_SNAPSHOT
-> FORMAL_RETURN_GATE_UNAVAILABLE
```

Execution layer, diagnostic-only:

```text
MSE3_TO_BUFFER4_ACCEPTED
+ MSE0_TO_BUFFER0_ACCEPTED
-> ANY_GA_INBUFFER_CAPTURE_ABSENT
```

The v9 local exhaustive audit remains applicable and was not repeated:

```text
outputs/gap_node0071_v9_local_reaudit/local_exhaustive_reaudit_report.json
sha256=bf86b2f11041c3d758ae7ee8f8f0e5893fd27f1b968648be0ca1f042df6b3d6b
```

It excluded a deterministic static stream-number, MSE-to-buffer,
buffer-to-GA-port, pingpong, lifetime, SA-backpressure, one-sided GA accept,
output route or early-terminal error. The new snapshot narrows the former
unobserved MSE3 branch by proving its producer-to-buffer acceptance, but it
does not prove the next buffer-read/inbuffer-ready/tag boundary.

## HANG_ROOT_CAUSE

```text
UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT
diagnostic class:
LONG_RUNNING_HANG_AT_BOTH_BUFFER_ACCEPTS_BEFORE_ANY_GA_OPERAND_CAPTURE
WITH_LATER_SIM_TIME_FREEZE
```

Remaining narrow gap: Buffer0/Buffer4 post-write valid and qualified read
acceptance, GA per-operand inbuffer ready/enable/tag match immediately before
capture, and independent simulator-liveness/finalizer status. No
deterministic configuration, RTL or package-runner error is proven by this
snapshot.

## BLOCKER_DELTA

Closed:

- the archive identity is old v10, not current v12;
- source package and manifest binding;
- install/preflight, compile completion, simulation/config start;
- both MSE0 and MSE3 producer-to-buffer qualified acceptances.

Still open:

- buffer accepted to GA inbuffer capture transition;
- cause of the later sim-time/output freeze;
- formal signal/exit/canonical/natural-terminal evidence;
- all 48 formal D.

## RULE_DELTA_PROPOSAL

No public-rule change. Current snapshot, hang-first, qualified-progress,
result-conjunction and observer-liveness rules cover this case. Mainline
should preserve separate receipt-layer and execution-layer first-divergence
fields and never promote snapshot diagnostics to E3/E4/E5.

## PACKAGE_RELEASE

```text
new package generated=false
v10 rerun authorized=false
current v12 modified=false
status=NO_PACKAGE_RELEASE_FROM_NONAUTHORITATIVE_SNAPSHOT
```

The old-v10 snapshot lacks formal finalizer/signal evidence and current
control already quarantines v10. It does not justify modifying or
superseding current v12 by itself.

No GAP sum/tail numeric analysis or workload was rerun. Frozen contracts,
the old-v10 source package and the v9 exhaustive local RTL audit were
consumed. No server outside the supplied ZIP was inspected; nothing was
uploaded or run. No plan, public rule or functional RTL was modified.

