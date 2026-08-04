# QLinearAdd node0007 v6 four-way observer binding validation

## Scope

This is a receipt-only validation of the frozen final ZIP:

```text
artifacts/operator_config_validation/r5-server-test-packages/
  r5_qadd_n7_nested_lc_progress_bind_v6.zip
SHA-256=9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90
```

The validator directly parsed the final ZIP under
`CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`. It did not trust the builder
directory or rebuild the package. Numeric and workload analysis were not
repeated.

## Four-way receipt

```text
status=FOUR_WAY_BINDING_VALIDATED
source=true
include=true
compile_enable=true
runtime_return=true
zip_unchanged=true
package_rebuilt=false
server_action=false
```

- The ZIP contains exactly one observer source:
  `tb_probe/native_return_observer.svh`, 111824 bytes,
  SHA-256=`47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`.
  Its manifest record, binding record and fresh-extract bytes all match.
- The final runner contains package-local
  `+incdir+$package_root/tb_probe` in both the compile receipt and actual
  compile command. Normalization remains within the package and equals the
  observer source parent.
- The final runner contains
  `+define+NATIVE_RETURN_OBSERVER_ENABLE` in both compile bindings.
- Runtime uses `+RETURN_OBSERVER`. The source emits
  `# Native NDP return observer v4` from its initial block, the runner checks
  that marker, and required return targets include actual compile argv,
  actual simulator argv, host timing, signal status, progress contract,
  progress samples, observer-binding receipt and observer log. EXIT/HUP/INT/
  TERM all route through collection.

## Negative controls

Four in-memory mutations were applied to final-ZIP members without modifying
the ZIP:

```text
remove source          -> PACKAGE_OBSERVER_BINDING_INCOMPLETE
remove +incdir         -> PACKAGE_OBSERVER_BINDING_INCOMPLETE
remove enable macro    -> PACKAGE_OBSERVER_BINDING_INCOMPLETE
remove runtime/return  -> PACKAGE_OBSERVER_BINDING_INCOMPLETE
```

All four negative controls fail closed at their expected direction. The
frozen v6 ZIP and sidecar remain unchanged.

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-progress-bind-v6-four-way/report.json`
