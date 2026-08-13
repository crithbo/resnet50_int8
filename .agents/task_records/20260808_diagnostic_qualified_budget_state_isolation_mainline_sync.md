# Diagnostic qualified/state budget isolation — mainline sync

Status: `PASS`

The mainline accepted the non-synonymous rule
`CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001`.

## Merge

The specialist rule snapshots were not copied wholesale because the mainline
already contained parallel server-package and generation-index increments.
Only the new qualified/state budget semantics were merged.

- server rule:
  `7cf2cb4511cba04cb8a14d06473d67061deae64f602988d27053d8289c964b13`
  -> `1fa6d9be4894d914e1f7b1889b0f62c7ed43f661e77de2afd1b97472b2be019c`;
- generation index:
  `d4ff32f162538574a0dd48402e299fa25a11fb95074352c19fcfb007ebb77603`
  -> `b3c5d7dcfb5a6417d38448f98e0cecac716ec05568aa454c4a99f447b1e69378`.

The shared schema, trace schema, registry, current-five profile, validator,
tests, and two fixtures were mechanically synchronized to the accepted exact
specialist bytes.

## Validation

- focused unittest: 19/19 PASS;
- `py_compile`: PASS;
- current-five shared profile: exit 0;
- early-slice state oscillation positive: exit 0;
- legacy shared-counter mutation: exit 1 as required;
- targeted `git diff --check`: PASS.

## Frozen GAP successor

`r5_n71_gap_v51_ga_ob_mode_factor_diag.zip` was not rebuilt, modified, or
family-revalidated:

- bytes: `1966085`;
- SHA-256:
  `76336937dd52822e948dcc81c6f35054c73d0066dfad5f964b6753a04a78f7b4`.

No server, upload, run, lease, RTL, ISA, hardware, active ndp-sim, config,
numeric, workload, mapping, bitstream, execplan, SCA, or package action was
performed.

Machine report:
`artifacts/operator_config_validation/r5-diagnostic-qualified-budget-state-isolation-v1/mainline_sync_report.json`.
