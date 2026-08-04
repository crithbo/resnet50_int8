# GAP node0071 v12 gated-clock rule drift revalidation

Date: 2026-07-31

Source/mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

Status: `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`

## Applicability

New rule:
`CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001`

Applicability to v12: `NOT_APPLICABLE`.

The final v12 observer has three posedge blocks and only two clock owners:
top-level `u_NDP_Top_new.clk_db` and `u_NDP_Top_new.clk_sg`. The frozen local
clock source proves both are free-running: RTLSIM uses independent `forever`
oscillators, while non-RTLSIM passes through `clk_db` and continuously divides
it into `clk_sg`. No observer qualified counter is owned by a gated leaf clock.

Heartbeat emission is owned by `clk_db` and gated only by the same-domain
`return_obs_active_cycles % return_obs_heartbeat_period`. No `clk_sg`
qualified counter is used as a cross-domain modulo/equality or unique emitter.
Therefore the failure mode targeted by the new rule is absent.

Boundary: v12 deliberately uses the user-supplied-root no-source-preflight
profile, so this is a local frozen RTL applicability proof and not a server
source identity claim.

## Content-neutral decision

No change is required to:

- final ZIP bytes;
- runner/runtime behavior;
- manifest machine contract;
- negative-control assets;
- return schema.

The v12 ZIP SHA remained
`a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06`
before and after revalidation. The package remains `PACKAGE_READY_NOT_RUN`.

Old server rule SHA:
`0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a`.

Current server rule SHA:
`507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`.

External receipt:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v12_minruntime.rule_drift_content_neutral_revalidation.json`

Receipt SHA-256:
`bfa5a6b2393ab04fede24500586628a1b7f8cec75817c2cd72fef6bc8db191ea`.

Canonical, observer four-way, dual-ingress and real-runner positive/negative
validators all exited zero. No numeric analysis, sum/tail workload, package
build, functional RTL edit, server access, upload, or run occurred.

