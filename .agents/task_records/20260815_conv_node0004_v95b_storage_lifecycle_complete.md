# Serialized Conv node0004 v95b storage lifecycle complete

## Scope

- role: `family.conv.serialized`
- owner epoch: `2`
- registry epoch: `6`
- server action: none
- storage writer scope: serialized only

## Previous-version progress

The consumed v94b run entered the target and localized the first dynamic mismatch to the prepared-data versus WR-metadata lifetime boundary. Five prepared-data groups were observed while only three WR metadata groups were accepted; the user interrupted the non-natural run. The formal analysis remains bound by `outputs/conv_node0004_v94b_tbvcd_wrdrain_return_analysis/return_analysis.json`.

## Current-version purpose

v95b preserves the frozen v94b configuration, numeric, workload, golden, functional RTL, actual-source target and runtime-v3 behavior, while discriminating WR_Memory_AG metadata lifetime from Buffer_AG/RD_Buffer prepared-data production and drain accounting.

## Storage transaction

The corrected manager pre-audit passed with pending/tested/superseded counts `4/42/23`. The only serialized pending identity was v94b. `tools/manage_server_test_package_storage.py rotate` then atomically:

1. moved v94b to `tested/conv_serialized_node0004/r5_n4_hw_v94b_tbvcd_wrdrain` and bound its exact formal return analysis;
2. published the already-gated v95b ZIP to flat `pending/`;
3. published the v95b sidecar and 11 additional receipts to its family receipt directory;
4. rewrote the storage index.

The corrected manager post-audit passed with counts `4/43/23`. Serialized has exactly one pending package, v95b. Native p50, GAP v70, QAdd v65 and every non-serialized package/receipt record were canonicalized before and after the transaction and are byte-identical. Conflicts are empty.

## Result

- `STORAGE_LIFECYCLE_COMPLETE`
- `GLOBAL_STORAGE_AUDIT_CLEAN`
- v94b disposition: `tested`
- v95b disposition: `pending`
- v95b package state: `PACKAGE_READY_NOT_RUN`
- further storage writes: stopped
- upload, lease, connection, or server execution: none

Machine receipt: `outputs/conv_node0004_v95b_tbvcd_metapair_release1/storage_release/storage_lifecycle_complete.json`.
