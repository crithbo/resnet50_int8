# QAdd 8400-second source-bound budget, v73 storage, and control-plane sync

Date: 2026-08-17  
Mainline role: `mainline.control`, owner epoch 2, registry epoch 6

## Authorized scope and result

- The user authorized the narrow predecessor-semantic compatibility correction and the QAdd source-bound wall-budget override.
- The shared TB-VCD gate now validates a current semantic-v7 successor while consuming an exact semantic-v5/v6 predecessor contract or its exact published PASS receipt. Immediate predecessor identity, receipt SHA, source identity, signal evolution and candidate preservation remain blocking.
- The default wall budget remains 3600 seconds. Only the exact source-bound QAdd successor uses 8400 seconds, derived from the v70 measurement (19/30 completed at 3608.29 seconds; deterministic recommendation 8022 seconds). The 8GB VCD, 10GB return, disk/growth/write/quota and signal guards are unchanged.
- Failed v71 and v72 are local non-publishable records. Fresh v73 passed every current local gate.

## Managed storage lifecycle

Exactly one QAdd manager rotation completed after a corrected clean pre-audit:

- tested predecessor: `r5_qadd_n7_tailround_lanephase_v70_pmapfix`, bytes 108772022, SHA-256 `7df37603b1d6ccab664301f8e998d8eacf1e114c434c56eb17b8904b210eaac8`;
- pending successor: `r5_qadd_n7_tailround_lanephase_v73_w8400v7`, bytes 108809782, SHA-256 `0cd165a36014e878e507dfc3e810d0271c1e41e1484ca7d5d8e248f8330be18f`;
- pending evidence: `r5_qadd_n7_tailround_lanephase_v73_w8400v7.release_receipt.json`, bytes 3450, SHA-256 `a450771ec52d855e4884d1303e6876aef9f06c60e366e6781b4b31563ae75640`;
- post-audit counts: pending/tested/superseded = `2/59/24`;
- exact pending set: serialized `r5_n4_hw_v102b_lcdup_guardprocfs` and QAdd `r5_qadd_n7_tailround_lanephase_v73_w8400v7`;
- storage index bytes 473168, SHA-256 `c0620ccbed4e4745ca59bbd19b51293cdb1b301f93e79f3bbf7696848a982801`.

Serialized v102 remained byte-identical: bytes 5969334, SHA-256 `f7d185c5d97dc5f4712cf9209a0155d68b8331b58a9663544f4eed7b323a3321`.

## Current runnable packages

- QAdd command: `bash r5_qadd_n7_tailround_lanephase_v73_w8400v7/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04`
- Serialized command: `bash r5_n4_hw_v102b_lcdup_guardprocfs/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Both remain `PACKAGE_READY_NOT_RUN`; this record authorizes no upload, lease, connection or server run. GAP and native Conv have no pending package and remain at their validated-root authorization boundaries.
