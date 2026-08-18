# QLinearAdd v67 storage acceptance

- family: `qlinearadd_node0007`
- package: `r5_qadd_n7_tailround_lanephase_v67_cfg42_tg`
- status: `PACKAGE_READY_NOT_RUN`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_v67_cfg42_tg.zip`
- bytes: `108687211`
- SHA-256: `dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740`
- command: `bash r5_qadd_n7_tailround_lanephase_v67_cfg42_tg/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04`
- evidence: `outputs/qlinearadd_node0007_v67_cfg42_tgcap_release/storage_lifecycle_complete.json`

v67 preserves the validated 4/2 config lineage and 64-signal selected-port target,
uses sparse pretarget safety snapshots during preload, then switches to continuous
untruncated target capture. Semantic-v5 and all current exact-ZIP gates pass. No
server action occurred.
