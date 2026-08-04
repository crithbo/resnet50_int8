# QLinearAdd node0007 nested-LC v4 return analysis

## Scope and immutable inputs

- Raw return: `r5_qadd_n7_nested_lc_v4_return.zip`
- Raw return SHA-256: `fe05a503a27f202e7befad7893c61c89701bf526f0b01f00af5eecc88b8690e1`
- Raw return bytes: `137313`
- Adjacent sidecar: present and exact
- Frozen source package: `r5_qadd_n7_nested_lc_v4.zip`
- Frozen source SHA-256: `dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361`
- `numeric_analysis_repeated=false`
- `consumed_reuse_assets=true`

The raw return and v4 source package were analyzed read-only. The 17-instance
inventory, W3 numeric order, six qparams, exact tail, final workload and golden
were not rebuilt.

## Return integrity and result conjunction

- Direct sidecar, ZIP CRC, path safety, exact-set, record SHA/size and package
  allowlist all pass.
- Embedded package manifest equals the frozen source ZIP manifest and the
  local frozen package manifest.
- Package and installed preflight pass; all formal runtime D targets were
  absent before simulation.
- `compile_exit_status=0`
- `simulation_exit_status=125`
- 85 preloads, exec transport, `Reg Started` and the first `slice start` are
  present.
- Natural terminal is absent.
- Formal D is `observed=0`, `missing=28`, `mismatch=0`. Zero mismatch is not
  evaluable when every formal readback is missing.

## Progress adjudication

The first slice start occurs at simulation time `16125911000 ps`; the external
interrupt is reported at `35507846250 ps`, for a computation interval of
`19381935250 ps`. Simulation time advancement does not prove transaction
progress.

The v4 package did not enable or return accepted/completion counters, stage
heartbeats, host wall-clock samples or a declared stall window. Consequently:

```text
execution_state = LONG_RUNNING_HANG_PENDING_ROOT_CAUSE
progress_adjudication = INSUFFICIENT_TO_DISTINGUISH_PROGRESS_FROM_STALL
hang_root_cause = UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT
```

The unique remaining interval is:

```text
op_a_dequant first Start_Comp
  -> LC/read accepted progress
  -> GA/buffer5/write completion
  -> LC last
  -> slice_cmpt_finish
```

## Static audit

- v4 removes the v2/v3 flat signed-feedback wrap; all positive LC ends are at
  most `18816`.
- All derived `dim_stride` values fit unsigned 20-bit.
- The final execplan contains six Start_Comp operations in the frozen order.
- The focused SEM holds `sem2iga_exec_start` throughout CMPT, so nested LC
  capture is not limited to one pulse.
- Shared LC backpressure remains the RTL AND of downstream readiness.
- Final address, nonalias, accepted lifetime, barriers, request coverage and
  golden are consumed from the accepted v4 closure.
- First stage request multiplicity is `5268480`; all six stages total
  `37352448`. This is a large node, so elapsed wall time alone cannot decide
  completion.

## Diagnostic-only next identity

No functional configuration or RTL root cause is proven. A next package, if
generated, is restricted to:

```text
DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
```

It must preserve the v4 workload and enable a read-only low-overhead observer
in the actual simulator argv. The return allowlist must recover host wall
clock, simulation time, stage/Start_Comp boundaries, accepted/completion
monotonic counts, last/terminal state and a declared stall window.

Analysis report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-nested-lc-v4-return-analysis/report.json`

Analysis report SHA-256:
`678122baa575c45d276758e7e5fd91cbf9c51ba1c2582083c2ecb2eb8a5ad3fa`

## Diagnostic package release

The unique diagnostic-only identity is:

```text
r5_qadd_n7_nested_lc_progress_v5.zip
SHA-256=f184410ced99830d4737bea58ccd0590e87ae0525c77d95265b0ef756a184a8e
status=PACKAGE_READY_NOT_RUN
claim=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
functional_fix=false
```

The workload is byte-identical to frozen v4 after only normalizing the install
namespace. Final JSON, mapping, bitstream, execplan, arithmetic SCA, golden,
six qparams and W3 order are unchanged. No numerical analysis was repeated.

The actual simulator argv enables the read-only observer for slice 0, with
`heartbeat_cycles=262144`, `stall_window_cycles=1048576`, and the observer
output bound to the fresh run root. The compile invocation explicitly defines
`NATIVE_RETURN_OBSERVER_ENABLE` for the server's already-installed optional
TB include; no TB or observer source is carried by the package. A 60-second
host sampler records the most recent observer line together with wall-clock
nanoseconds. The existing 12-hour simulator timeout is unchanged.

Seven diagnostic records are required by the exact return allowlist:

```text
evidence/progress_contract.json
evidence/actual_simulator_argv.txt
evidence/host_timing.txt
evidence/signal_status.txt
evidence/progress_samples.log
evidence/observer_binding.txt
runs/return_observer.log
```

If accepted/completion counts advance across two consecutive windows, the
interruption occurred while the simulation was still progressing. If all
counts remain flat beyond the declared stall window, the last observer
boundary localizes the hang. If observer binding is absent, the package fails
closed without a functional inference.

Independent validation passes with no errors and one non-blocking warning:
`mutable read receipt drift: .agents/plan.md`. The plan is provenance-only;
the active server-package, NDP-field and QLinearAdd rules remain current-match
hard gates.
