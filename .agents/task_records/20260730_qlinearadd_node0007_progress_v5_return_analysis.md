# QLinearAdd node0007 progress v5 return analysis

## Bound receipt

- Return ZIP: `r5_qadd_n7_nested_lc_progress_v5_return.zip`
- Return SHA-256:
  `6cd65fef8b8486497d01b87bda887fe30b15c6dec024d626503db6a2fd18efcb`
- Adjacent sidecar: present and exact
- Frozen source package: `r5_qadd_n7_nested_lc_progress_v5.zip`
- Frozen source SHA-256:
  `f184410ced99830d4737bea58ccd0590e87ae0525c77d95265b0ef756a184a8e`
- `numeric_analysis_repeated=false`
- `consumed_reuse_assets=true`

ZIP CRC, path safety, record hashes/sizes, return exact-set and package
allowlist all pass. Package and installed preflight both pass, and all formal
D targets were absent before simulation.

## Dynamic and progress result

```text
compile_exit_status=2
simulation_exit_status=125
simulation_started=false
dynamic_attempt_counted=false
natural_terminal=false
formal_D_observed=0
formal_D_missing=28
formal_D_mismatch=0 (not evaluable)
```

The return covers 23.230137533 seconds of host wall time. It contains no
simulation time, stage/Start_Comp event, qualified accepted/completion window,
last/terminal event or formal D because compile failed first. The five
available progress records are the contract, host timing, signal status,
single `OBSERVER_NOT_CREATED` sample and negative observer-binding receipt.
The actual simulator argv and observer log are correctly recorded as missing.

## First divergence

The compile command contains:

```text
+define+NATIVE_RETURN_OBSERVER_ENABLE
```

VCS selects the guarded TB branch, then reports:

```text
Error-[SFCOR] Source file cannot be opened
Source file "native_return_observer.svh" cannot be opened
tb_NDP_Top_new_phy.sv:5855
```

Therefore:

```text
progress_adjudication=PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE
diagnostic_infrastructure_root_cause=PACKAGE_OBSERVER_INCLUDE_SOURCE_NOT_BOUND
functional_qlinearadd_root_cause=UNRESOLVED_NO_NEW_DYNAMIC_EVIDENCE
```

This is a compile/package diagnostic-infrastructure failure, not a QLinearAdd
functional failure or evidence of progress/stall. It is not counted as a
dynamic attempt.

## Authorized minimal next identity

A fresh diagnostic-only package may preserve the complete v5 workload and
timeout while carrying the already-audited read-only observer under
`tb_probe/native_return_observer.svh`. The compile command must bind both:

```text
+incdir+$package_root/tb_probe
+define+NATIVE_RETURN_OBSERVER_ENABLE
```

The package must not install, patch or inspect a server source file. It must
declare one package-local observer entry, zero functional RTL entries, verify
the observer SHA before compile, and retain the same progress/return gates.

## Fresh diagnostic binding package

```text
identity=r5_qadd_n7_nested_lc_progress_bind_v6
status=PACKAGE_READY_NOT_RUN
claim=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
functional_fix=false
zip_sha256=9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90
```

The package contains 133 files: the frozen v5 payload plus exactly one
package-local observer source. It has zero functional RTL entries and does not
write any server source path. The observer source SHA-256 is
`47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`.

The final return allowlist contains 46 unique entries. Eight are mandatory
progress/binding records, adding `evidence/actual_compile_argv.txt` to the
seven v5 progress records. Runtime D remains absent before simulation.
Independent validation and deterministic double-build pass.
