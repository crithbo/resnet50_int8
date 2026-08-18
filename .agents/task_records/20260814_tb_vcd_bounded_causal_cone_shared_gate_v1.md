# TB VCD bounded causal-cone optional shared gate v1

Date: 2026-08-14  
Role: `optimizer.whole-network`  
Status: `CURRENT_DISK_SYNC_READY`  
Epoch: `tb-vcd-bounded-causal-cone-optional-v1-0820e1733437`

## Previous progress and current purpose

The existing `OBSERVER_ONLY_WIDE_CAUSAL` mode remains the byte-frozen default. This task added a separate explicit `TB_VCD_BOUNDED_CAUSAL_CONE` local contract and did not restore VPD, FSDB, UCLI direct VCD or vendor query paths. It did not build or rotate any family package.

The optional mode uses only package-local TB `$dumpfile/$dumpvars/$dumpon/$dumpoff/$dumpflush`, binds a source-derived 41-role causal catalog and an exact candidate×boundary matrix, returns an ordinary locally readable VCD, and retains only a lightweight progress supervisor beside it.

## Safety closure

- A package selects exactly one bulk mode. Observer mode is unchanged; VCD mode forbids full observer JSONL.
- `DUMP_VCD=0`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0` remain exact actual-argv requirements; prebuilt VCD self-inclusion, VPD/FSDB/FST and UCLI/vendor controls fail closed.
- Causal plateau requires the conjunction of advancing owner clock and sim time, stable qualified counters, bitwise-stable complete source-bound causal state, stable global witness, complete catalog/matrix coverage and no unresolved X/Z. Global progress advancing forbids a local-cone stop.
- Three 30-second sim-time freezes, 60-minute wall ceiling, 8GB operational projection, 10GB return projection, disk/write/quota failure and signals remain independent partial-exit triggers. Written VCD is never truncated.
- Decimal 100,000,000 bytes is warning-only. It never caps, samples, deletes or suppresses the return.
- Raw retention is `MAX_PROGRESS + LATEST_1 + LATEST_2`; deletion requires analysis completion, family and mainline consumption, deterministic core evidence and protected-set audit.
- Streaming review uses atomic `analysis_state.json`, append-only `checkpoints.jsonl`, incremental `report.md`, bounded summaries and offset resume; unique root-cause closure stops further scanning.

## Validation

- Four new Python tools: `py_compile` PASS.
- New focused regression: 33/33 PASS.
- Observer/post-sim/retention plus new related regression: 108/108 PASS.
- Eight JSON/schema/contract/fixture documents parse successfully.

Machine report: `outputs/tb_vcd_bounded_causal_cone_shared_gate_v1/report.json`.

## Mainline merge and claim boundary

`contracts/server_tb_vcd_bounded_causal_cone_mainline_merge_v1.json` is the narrow semantic merge recommendation. Mainline must keep observer-only as default, add the optional VCD rule/gate conditionally, and activate first-fresh extra audit only when the VCD mode is selected.

This is local synthetic closure only. Production VCS compatibility, family-specific cone/catalog correctness, real process-tree/filesystem behavior and real VCD overhead remain first-fresh runtime boundaries. No public rule, plan, owner registry, current package, RTL, config, numeric/workload asset or server state was modified.
