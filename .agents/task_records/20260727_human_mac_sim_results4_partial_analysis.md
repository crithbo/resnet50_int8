# Human MAC `sim_results(4).zip` partial-return analysis

## Return identity

- absolute path:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\sim_results(4).zip`
- bytes: 71872360
- SHA256: `7516eaee2ae82625c4a2d5e0eed10e79acdf9fe9be36f81a54fbaeCA1ff551f8`
- contents: raw `sim_results/` snapshot, including compile products,
  `compile.log`, and `sim.log`.

This is not the package's expected formal return ZIP and has no SHA256
sidecar, package receipt, run-status receipt, identity gate, result gate, or
formal readback files. It therefore fails closed as a partial snapshot.

## Observed execution

- compilation completed:
  - compile/elaborate/link CPU timing present;
  - VCS reports 0 errors and 1 warning.
- workload load completed:
  - 30 matrices loaded;
  - 28 A matrices, one config bitstream, and the execution plan are visible;
  - `Exec_Base=0x00001800`, `Exec_Length=29`;
  - all load/readback consistency checks printed PASS.
- execution started:
  - `Reg Started.`
  - `INFO: slice start` at 58,838,000 ps.
- no normal completion was observed.
- log termination:
  - `Interrupt at time 6072101975`
  - `Received SIGHUP (signal 1), exiting.`
  - VCS final CPU time 588.680 seconds.

## Adjudication

- current-process state represented by this archive: **EXITED**, not running.
- deadlock: **not established**.
  The process advanced from slice start at 58,838,000 ps to interruption at
  6,072,101,975 ps, but the snapshot contains no same-cycle observer/control
  evidence proving whether useful work continued or control was stalled.
- numeric correctness: **not adjudicable**.
  All 28 formal D readbacks and the result gate are absent.
- classification:
  - `PARTIAL_SNAPSHOT`
  - `EXTERNAL_SIGHUP`
  - `FIRST_DYNAMIC_FAILURE`
  - `NO_DYNAMIC_BASELINE`

The first proven failure is infrastructure/lifecycle termination by SIGHUP
before completion and readback, not a proven JSON, datapath, or RTL-control
failure.

