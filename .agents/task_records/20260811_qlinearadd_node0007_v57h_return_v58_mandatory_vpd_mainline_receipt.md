# QLinearAdd node0007 v57h return / v58 mandatory-VPD mainline receipt

- role: `family.qlinearadd`
- owner thread: `019ff02d-9e93-7d61-8c98-c928fdea157c`
- owner epoch / registry epoch: `2 / 6`
- shared gate epoch: `waveform-mandatory-v2-01ca6d7cd4a4a270`
- status: `PACKAGE_READY_NOT_RUN`
- server action: none

## Previous formal progress

The supplied v57h return passed production compile and started simulation, then timed out before a natural
terminal. Tail-round stage1 had one ordered start and no finish; formal D was `0/28`.

- `LAST_PROVEN_GOOD=C_BUFFER5_MRM_REQUEST_DECODE`: `req_valid=rd_en=0xff`, `req_addr=0`,
  `req_strb=0x33333333`.
- `FIRST_DIVERGENCE=C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT`.
- Classification: `SELECTED_PINGPONG_PORT_REQUIRED_LANES_NOT_READY`; pingpong selected port0 while
  `ready0/ready1=0/1`, `selected_ready=0`, `bank_ready=0`, `valid_at_req=0xcccccccc`, required missing
  lanes=`0x33333333`, failed banks=`0xff`, read accepts=`0`.

The v57h return contained no waveform, so the temporal producer, clear event and selected-port-ready cause
inside this boundary remained unresolved.

## Fresh successor purpose and exact identity

v58 preserves the exact v57h tail-round/lane-phase target diagnostic and adds complete full-hierarchy VPD
plus resilient formal-return recovery so the selected-port/bank-lane readiness stall can be localized in one
attempt.

- pending ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd.zip`
- bytes: `46652561`
- SHA-256: `97c5fce6714e9a53937043fb7626d2b462c52ce362147341b834fa33c2b9582d`
- machine handoff: `outputs/qlinearadd_node0007_v58_mandatory_vpd_release/qlinearadd_node0007_v58_return_analysis_package_ready_not_run.json`
- final audit: `outputs/qlinearadd_node0007_v58_mandatory_vpd_release/r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd.final_zip_audit.json`
- first-fresh: `outputs/qlinearadd_node0007_v58_mandatory_vpd_release/exact_zip_audit/first_fresh_extra_audit_validation.json`

Mainline matched the exact pending ZIP identity, read the formal handoff/final/first-fresh reports, inspected
the exact ZIP runner and waveform plan, and confirmed the corrected global storage index. Final-ZIP,
clean-extract, first-fresh, source-bound, post-sim, runner resilience, mandatory-waveform and storage exact-set
gates pass; the pending exact-set contains one QAdd identity.

## Mandatory waveform and frozen surface

- actual compile/sim controls: `DUMP_VCD=1,DUMP_FSDB=0,TB_DUMP_FSDB=0`
- dump: `tb_NDP_Top_new_phy`, depth `0`, `FULL_HIERARCHY`, exclusions `[]`
- collect all `wave.vpd` shards from the current attempt; no cap, truncation, sampling or size-based deletion
- started-without-wave fails closed; timeout/HUP/INT/TERM/nonzero recover partial wave; compile-not-started
  preserves mandatory compile-core return
- frozen: config, numeric, workload, golden, functional RTL and target diagnostic exact bytes

## Future command and claim boundary

Only after later explicit authorization:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy05`

Expected return:

`/home/panqs/ndp/simresult/r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd_r<epoch-ns>_<pid>_return.zip`

This receipt claims formal v57h return analysis plus local construction/gates/storage publication for v58 only.
It does not authorize upload, lease or server run and does not claim a new production compile, simulation,
natural terminal, formal D, E4 or E5.
