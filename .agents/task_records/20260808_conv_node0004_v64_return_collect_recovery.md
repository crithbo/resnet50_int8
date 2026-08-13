# Conv node0004 v64 return collector recovery

The user-provided server text proves compile exit 0, run exit 0, signal NONE,
valid canonical decision, and all runtime diagnostic feature bindings,
including `RETURN_OBS_DSKEW`. The run evidence therefore remains valuable.

The return was not formally collected because the repeat-execution reissue
updated `node0004_hang_localization_runtime_v7.collect` and its CLI call to six
arguments, including `return_zip`, but left the wrapper
`node0004_hang_localization_runtime.collect` at five arguments. The wrapper is
assigned to `base.collect`; the base CLI then calls it with six arguments and
raises:

`TypeError: collect() takes 5 positional arguments but 6 were given`

This is a package-local return-collection ABI error after simulation, not a
DUT, numeric, config, or RTL result.

`outputs/conv_node0004_v64_return_recovery/RECOVER_V64_RETURN.sh` performs a
non-destructive server recovery. It validates the preserved attempt
`a3721173`, calls the exact six-argument `_base_collect`, applies the same
`validate_return_zip` gate, verifies the sidecar, and never reruns compile or
simulation. Existing valid results are reused; conflicts cause a fresh
`rrecover_*` target rather than overwrite or delete.

Formal E4/E5 remain open until the recovered ZIP and sidecar are returned.
