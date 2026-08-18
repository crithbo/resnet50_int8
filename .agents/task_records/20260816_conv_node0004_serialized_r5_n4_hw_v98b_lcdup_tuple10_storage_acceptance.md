# Conv node0004 serialized v98b LC-dup tuple10 storage acceptance

- date: 2026-08-16
- family: `family.conv.serialized`, owner epoch 2, registry epoch 6
- package: `r5_n4_hw_v98b_lcdup_tuple10`
- status: `PACKAGE_READY_NOT_RUN`

## Purpose

Preserve the v97 validated boundary that Memory_AG input1 supplies nine rather
than ten 32-unit tuples. The user-authorized mapper A/B duplicates logical LC9
into dormant logical LC3, reroutes only `PE1.inport2` to LC3, and keeps the
original LC9 as `GROUP4.ROW_LC` source. The package observes copied-LC advance,
PE join, Memory_AG input1 acceptance, downstream drain, tuple10, natural
terminal and Formal-D.

This is a targeted configuration experiment, not a functional RTL mutation.
Production tuple10, natural terminal, Formal-D and E3/E4/E5 remain unproven.

## Local proof

- Mapper A/B: penalty 0, no fallback, equivalent ordered addresses and output
  values, unchanged data-plane memory traffic and cycle upper bound.
- Occupancy changes from 14/20 to 15/20 physical LCs; five remain spare.
- Cost is one additional LC plus eight meaningful config bytes / sixteen
  transport bytes, with zero data-plane traffic delta.
- Exact ZIP and all current active-rule, semantic-v3 first-fresh,
  materialized-config, observer-only/source-bound, runner/runtime, post-sim and
  schema-enabled release gates passed.

## Managed storage

- Pending ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v98b_lcdup_tuple10.zip`
- ZIP bytes: 5912380
- ZIP SHA-256: `aff2d997e0cc7ae6f0984c96992c03beef69e5fc80fb43f513bf0f6244536c4b`
- Indexed evidence SHA-256:
  `ebba0fefd451f41b1d899002180fd16500b976dafd137bda2d20cff03b1bff8a`
- Post-publication counts: pending/tested/superseded `3/52/24`.
- Index bytes: 423974
- Index SHA-256: `1bdcacefa3979ccef01b13136b86cb4a0b6a43f41de897efb61b4de2728ea8d3`

The pre-existing GAP v72 and QAdd v68 pending packages remained byte-exact.
No upload, lease, connection, server run, functional RTL change, or
numeric/workload/golden mutation occurred.

Unique future command only after separate server authorization:

`bash r5_n4_hw_v98b_lcdup_tuple10/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
