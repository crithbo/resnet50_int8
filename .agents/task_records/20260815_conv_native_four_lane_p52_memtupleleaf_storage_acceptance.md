# Conv native p52 storage acceptance

- family: `conv_native_four_lane`
- package: `r5_n4_0cc_p52_memtupleleaf`
- status: `PACKAGE_READY_NOT_RUN`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p52_memtupleleaf.zip`
- bytes: `6013257`
- SHA-256: `fcb8a7b61fcd02be90ddf53b637b00259f208239a8c392cc38a2685da765d22f`
- command: `bash r5_n4_0cc_p52_memtupleleaf/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
- evidence: `outputs/conv_native_four_lane_0ccae916_p52_memtupleleaf_release/storage_lifecycle_complete.json`

p52 preserves the p51 one-transaction / 32-unit metadata-deficit boundary and adds
40 direct Memory_AG tuple, same/gotten, split-FIFO and keep-release leaves. It has
146 signals, 14 pairwise candidates and 56 matrix rows. Semantic-v5, first-fresh,
release-admission and deterministic exact-ZIP gates pass. No server action occurred.

