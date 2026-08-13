# GAP node0071 v58 formal return: shared portable runtime escape

Date: 2026-08-12  
Role: `family.gap`  
Owner epoch: `2`  
Registry epoch: `6`

## RETURN_ANALYSIS

The exact user-supplied return is structurally safe and identity-bound to
`r5_n71_gap_v58_sum_s2_portable_vcd_query` execution
`r1786512387872266770_1425039`, attempt `a1425039`. CRC, duplicate/path/symlink checks pass, and the
returned package manifest is byte-equal to the preserved source ZIP manifest. The original return ZIP remains
unchanged in `C:/Users/15383/Downloads/`.

Production compile, elaboration and link succeeded under VCS `V-2023.12-SP2_Full64`. The simulator was invoked,
but DUT simulation did not advance: `logs/sim.log` shows the authoritative VPD initialized and the depth-0 top
scope added at 0 ps, followed by `PORTABLE_DUMP.tcl` line 3 requesting `dump -type VCD`. UCLI emits
`UCLI-DUMP-UNSUPP-FORMAT`, reports that only EVCD and VPD are supported, and exits at `Time: 0 ps` before the
remaining scope-add, `run`, and `quit` commands execute. The process exit code is zero, but the bound terminal
receipt correctly says `natural_terminal_observed=false`.

The raw VPD is transported with an identity-valid, unbounded receipt that labels it `COMPLETE`; that label only
reflects the zero-exit process closing the file and is a runtime-method misclassification. Since the only observed
time is 0 ps, the waveform is semantically `PARTIAL` for diagnosis. Local tool discovery
finds GTKWave and `vcd2fst`, but no `vpd2vcd`, Verdi or DVE, so the raw VPD cannot close local semantic decoding.
No direct VCD or registered query receipt exists. The 48-candidate generation catalog is exact and source-bound,
but runtime events and end states are absent because `run` never executed. Portable validation therefore correctly
returns `DIAGNOSTIC_EVIDENCE_INCOMPLETE`.

## Causal boundary

- Previous functional progress: v56 dynamically proved the slice-local-base workaround through `sum_s1` on all
  16 selected slices; v57 preserved it and localized the remaining target before the first `sum_s2` writeback.
- `LAST_PROVEN_GOOD`: v58 production compile/elaboration/link, then UCLI VPD initialization and full-hierarchy
  depth-0 add at 0 ps.
- `FIRST_DIVERGENCE`: package-owned `PORTABLE_DUMP.tcl` line 3, before any DUT time advance, rejects the requested
  direct VCD format.
- `HANG_ROOT_CAUSE`: `PACKAGE_PORTABLE_WAVEFORM_METHOD_INCOMPATIBLE_WITH_SERVER_VCS_UCLI`.
- Sum-s2 signal-level result: not evaluable. There is no DUT/RTL/config/numeric failure claim from v58.

Natural terminal is false, formal D is `0/48`, and E3/E4/E5 are all false. The portable return does not close the
prior decoder/parser gap.

## Explicit terminal and rule feedback

`SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE / DIAGNOSTIC_EVIDENCE_INCOMPLETE`;
`HOLD_PORTABLE_METHOD_RUNTIME_FIX`; `PACKAGE_RELEASE=NONE`; no fresh successor is published.

The exact shared escape signature is present: compile=`0`, simv=`0`, no DUT time advance/progress marker/rows,
direct VCD absent, query event count zero, and raw VPD semantically partial. The activated shared first-fresh method
requires exact UCLI `dump -type VCD`, while the production simulator proves that command unsupported. Reusing it
would deterministically fail at 0 ps, and hiding the command or weakening the validator would be an audit escape.
The optimizer owns the shared-method correction. Family scope will not patch shared tools and will hold any successor
until `CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_READY` is activated. A corrected shared method should use a
production-proven identity-bound portable mechanism and reject a zero process exit as a started DUT run when
simulation time never advances.

Config, numeric, workload, golden, functional RTL, the slice-local workaround and the `sum_s2` target diagnostic are
unchanged. No upload, run, lease or server action was performed.

Machine receipt:
`outputs/gap_node0071_v58_return_r1786512387872266770_1425039_analysis/formal_return_analysis.json`
