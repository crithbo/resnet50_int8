# GAP node0071 v72 temporary config-bypass storage acceptance

- date: 2026-08-16
- family: `family.gap`, owner epoch 2, registry epoch 6
- authorization: direct user authorization for a temporary config-only correctness bypass; local package/storage publication only

## Purpose and boundary

- Preserve the validated v71 root: stale MSE0/Buffer0 column-index FIFOs survive `slice_rst` and replay prior-stage bases.
- Temporarily map sum_s2 A to logical B / `READ_STREAM1` / MSE1 / Buffer2 / GA inport1.
- Move constant 1 to GA inport0, preserving exact INT32 MAC semantics by commuting `A*1+C` to `1*A+C`.
- C remains MSE3/Buffer4 and D remains MSE4/Buffer5.
- This is a diagnostic bypass to expose later configuration blockers, not a functional repair of the validated FIFO-reset defect.

## Local gates

- Fresh package: `r5_n71_gap_v72_sum_s2_mse1_cfg_bypass`.
- Exact ZIP: 2505304 bytes, SHA-256 `4e19837bf59c4acdc88b23c731fb6fd85dae8d40dc69a260b80b56adf7bf431b`.
- Package-ready receipt: 9450 bytes, SHA-256 `0873b333053bb0e03a6ff1e21aa3c429fbb0aea0a083e5b757409b9687e97bd3`.
- Build-failure rule audit: 5178 bytes, SHA-256 `b97c9e05aa2845c828a874cc1cca69cdbc1d5ee94664b1c998cf680dec1bbd32`.
- Native mapping double-build, bitstream/config materialization, all-stage slice-local execplan, TB-VCD v5, HDL/frontend, runner/runtime, post-sim, first-fresh, deterministic ZIP, release admission, active-rule and focused regression gates passed.

## Storage

- Mainline reconciled the user authorization before granting sole-writer publication.
- Corrected pre-audit passed at pending/tested/superseded `1/52/24`, with sole pending QAdd v68.
- GAP v72 was published with no previous GAP pending retired.
- Corrected post-audit passed at `2/52/24`.
- Managed pending ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v72_sum_s2_mse1_cfg_bypass.zip`.
- Pending sidecar: 108 bytes, SHA-256 `23cafdaa2ce6b53043a859ef1e63e244b14fc276bed20960c8c2856438b0c976`.
- QAdd v68 remained byte-exact; GAP v71 remains absent from managed storage.
- Final storage index: 420859 bytes, SHA-256 `a5bef1afa4c9b24ce47becd1eb96921a49822c03e79b7ff3580b4bb67a98d534`.
- No upload, lease, connection, server run or RTL mutation occurred.

Future command only after separate server authorization:

`bash r5_n71_gap_v72_sum_s2_mse1_cfg_bypass/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
