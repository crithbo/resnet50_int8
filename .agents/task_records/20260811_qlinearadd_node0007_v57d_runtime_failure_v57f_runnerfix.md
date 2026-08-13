# QLinearAdd node0007 v57d runtime failure → v57f runner fix

The server report `PREPARE_AND_RUN.sh: line 18: run_root: unbound variable` is a deterministic package-runner defect. Exact v57d binds `source_bound_filtered_log` at line 18 while `run_root` is only initialized at line 31 and materialized from `RUN_ROOT` at line 181. With `set -u`, execution stops before argument preflight, compile or simulation.

v57d is `QUARANTINED_SERVER_RUNTIME_INIT_UNBOUND_VARIABLE`; this result is not config, numeric or RTL evidence.

Fresh v57f moves the single required binding immediately after `run_root="$RUN_ROOT"`. Numeric/W3/qparams/tail/workload/config/golden/observer/timeout/functional RTL remain frozen.

- v57f ZIP bytes: `70704126`
- v57f ZIP SHA256: `eeb922f3828b0e1dd6532bf0903e516351f0a4a0a9a0439b917e8e1b2532415e`
- final audit: `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors `0`, SHA256 `18ab8abe4e1d3f159de6aba9a7118824b05037a48a6a51bfe6626b839777498f`
- exact runner no-argument gate: exit `2`, expected runner error, no `unbound variable`
- exact runner relative-root gate: exit `2`, expected runner error, no `unbound variable`
- source-bound/post-sim/runtime-layout/stage-filter gates: pass

Server command:

`cd /home/panqs/ndp/r5_qadd_n7_tailround_lanephase_qual_v57f && bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy05`

Expected return:

`/home/panqs/ndp/simresult/r5_qadd_n7_tailround_lanephase_qual_v57f_<execution>_return.zip`

`RULE_CONFIRMATION`: current exact-runner startup, source-bound runner token, final-ZIP and storage rules are sufficient; no non-synonymous delta proposed.

Owner `019fa2c0-b647-7a91-93bf-d21a173487e3`; target `019fbec2-fe93-7e03-9314-cff6f222f33d`; no server action.
