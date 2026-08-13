# GAP node0071 v56 slice-local mandatory-VPD mainline receipt

- role: `family.gap`
- owner thread: `019ff02d-8225-7d21-9779-e46ce4130572`
- owner epoch / registry epoch: `2 / 6`
- shared gate epoch: `waveform-mandatory-v2-01ca6d7cd4a4a270`
- status: `PACKAGE_READY_NOT_RUN`
- server action: none

## Previous progress and current purpose

v54 closed the remote owner-ready RTL root at `WAIT_RTL_FIX`; it did not modify functional RTL. Old v55
then locally proved the slice-local-base configuration workaround and was withdrawn only because it used the
old `DUMP_VCD=0` runtime semantics. v56 preserves the exact v55 slice-local config/workload/source-bound
diagnostic and avoids the remote owner-ready path through slice-local base rewrites. Its new purpose is to
return complete full-hierarchy unbounded VPD so a later explicitly authorized run can localize the remaining
dynamic cause in one round.

## Exact package and receipts

- pending ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v56_slice_local_base_vpd.zip`
- bytes: `2055389`
- SHA-256: `c3dcee5c32ebf40c06653b07e39210164d51f51a8d8bc2313a64d4e43be89a02`
- final audit: `outputs/gap_node0071_v56_slice_local_base_vpd/final_audit/overall.json`
- first-fresh: `outputs/gap_node0071_v56_slice_local_base_vpd/final_audit/first_fresh_validation.json`
- active-rule postbuild audit: `outputs/gap_node0071_v56_slice_local_base_vpd/final_audit/active_rule_registry_postbuild.json`

Mainline independently matched the pending ZIP identity, read the final/first-fresh/rule reports, inspected
the exact ZIP runner and waveform plan, and confirmed the current storage index. Final and first-fresh reports
are pass with empty errors; candidate coverage is `5/5` pairwise distinguishable; storage audit is clean and
the pending family set contains exactly one GAP identity.

## Mandatory waveform and frozen surface

- actual controls: `DUMP_VCD=1,DUMP_FSDB=0,TB_DUMP_FSDB=0`
- dump: `tb_NDP_Top_new_phy`, depth `0`, `FULL_HIERARCHY`, exclusions `[]`
- discovery: every `wave.vpd` and `wave.vpd.*` below the current attempt's `compile/sim_results`
- return: no waveform size cap, truncation, sampling or size-based deletion; started-without-wave fails closed;
  compile-not-started preserves the compile-core exception; timeout/HUP/INT/TERM/nonzero recover partial wave.
- frozen: config, numeric, workload, functional RTL and target diagnostic; `functional_rtl_modified=false`.

## Future command and claim boundary

Only after later explicit authorization:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

Expected return:

`/home/panqs/ndp/simresult/r5_n71_gap_v56_slice_local_base_vpd_<return_tag>_return.zip`

This receipt claims local construction, exact-ZIP/first-fresh/waveform/source-bound/runner/runtime-layout gates
and storage publication only. It does not claim production compile, DUT simulation, natural terminal, formal D,
E3, E4 or E5 and does not authorize upload, lease or server run.
