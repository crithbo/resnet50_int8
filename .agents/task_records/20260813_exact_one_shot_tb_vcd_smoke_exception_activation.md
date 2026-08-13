# Exact one-shot TB VCD smoke exception activation

## Previous progress

The observer-only four-family round removed VPD/FSDB/VCD/FST to avoid decoder, portable-UCLI and
writer-quiescence failures. Serialized v89b, GAP v60 and native p45 subsequently reached production VCS
but were stopped before simulation by the shared missing DesignWare `sim_ver` dependency; their formal
operator targets remain unexecuted.

## Current purpose

The user explicitly approved one exact, non-generalizable VCD diagnostic smoke using testbench standard
system tasks. The purpose is to measure whether production VCS accepts `$dumpfile+$dumpvars`, advances
past time zero, returns a locally readable 38-signal VCD, and establishes its growth/performance cost
relative to the interrupted partial FSDB baseline. It is not a formal serialized Conv successor and may
not adjudicate DUT root cause, E4 or E5.

## Activation

- Exception request: `one-shot-curated-vcd-smoke-r5-n4-v1`
- Epoch: `one-shot-tb-vcd-smoke-r5-n4-v1-6bf4c7fe5596`
- Exact package: `r5_n4_hw_vcdsmoke_causal_v1`
- Canonical lane: `artifacts/operator_config_validation/r5-whole-network-experimental-vcd-smoke-v1/activated/`
- Machine contract: `contracts/server_one_shot_tb_vcd_smoke_exception_v1.json`
- Status: `ACTIVATED_NOT_SERVER_AUTHORIZED`

The probe contains 38 explicit read-only aliases for one selected slice13/group1/MSE4 WR instance and
uses only TB `$dumpfile+$dumpvars`. Compile/sim dump variables stay zero. UCLI VCD, VPD, FSDB, FST,
full-hierarchy selection, memory arrays, sampling, truncation and hard size caps remain forbidden.

The exception permits one production invocation after the DesignWare environment is restored or an exact
replacement is separately approved and identity-bound. Activation does not authorize upload, lease,
server run or toolchain replacement. It does not enter formal pending, claim `PACKAGE_READY_NOT_RUN`, or
modify/hold serialized v89b, GAP v60, native p45 or QAdd v61.

## Claim boundary

Local reproducible package construction and self-checks are accepted. Production compile/elaboration,
time advance, returned VCD completeness, performance and size remain unproven until the single formal
execution return is supplied. No server action was performed by mainline.
