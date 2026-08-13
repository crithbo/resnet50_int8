# QLinearAdd node0007 v35 formal return analysis

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- input return: `r5_qadd_n7_crow32_v35_return.zip`
- return bytes/SHA256: `215158` / `30c5bdc1d1bb3cd47f28300e7557e8316ad770d38e50cebaeda1fce81e067972`
- frozen source SHA256: `45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829`
- adjacent sidecar: absent, accepted only for external transport under the user-attested no-sidecar rule
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-v35-return-analysis/report.json`
- machine report bytes/SHA256: `8143` / `387d4267aa29cafa5b8f34559d2efb289578998fe3e2ea643d2c8f07ae622c25`

## Formal result

Internal CRC, single safe root, inventory exact-set, RETURN_MANIFEST per-file
receipts, allowlist, and source/package/install/run identity all pass. Compile
completed. Simulation exited `124`, had no natural terminal, and produced none
of the 28 split-C stage-local D targets. Consequently mismatch is not
evaluable and E3/E4/E5 are false.

Ordered stage evidence proves A dequant, B dequant, and relocation complete.
The FP32 add then reaches finite dual-input reads and GA activity but never
forms an accepted Buffer5 output row.

- LAST_PROVEN_GOOD: `FP32_ADD_GA_OUTPUT_9114_OF_9408_ROWS`
- FIRST_DIVERGENCE:
  `FP32_ADD_GA_16B_OUTPUT_CANNOT_FORM_BUFFER5_32B_ACCEPTED_ROW`
- HANG_ROOT_CAUSE:
  `UNIQUE_CONFIG_GA_OUTPUT_FOUR_PE_16B_SUPPLY_VS_BUFFER5_EIGHT_BANK_32B_REQUIREMENT`

The decisive final-config comparison is four enabled GA output PEs
(`PE00/PE02/PE20/PE22`) times 4 bytes = 16 bytes, versus Buffer5's eight
enabled banks times 4 bytes = 32 bytes. The trusted native FP32-add config
uses eight PEs. Dynamic evidence is consistent: GA advances, Buffer5 accepted
write remains zero, and MSE4 owns a request with no write data.

No numeric, W3, qparam, exact-tail, workload, config-domain, or golden analysis
was repeated.
