# Observer-only wide-causal shared gate v1

Date: 2026-08-13  
Role: `optimizer.whole-network`  
Activation proposal: `observer-only-wide-causal-v1`

## User decision implemented

The next-fresh shared profile is observer-only. Actual compile and simulation argv must bind `DUMP_VCD=0`, `DUMP_FSDB=0`, and `TB_DUMP_FSDB=0`. VPD, FSDB, VCD, FST, waveform Tcl and waveform PLI surfaces are rejected from the final package and formal return.

The observer evidence aggregate has a decimal `100000000` byte soft preference. Exceeding it emits a warning and preserves full evidence. Every hard-limit field is null/absent; sampling, truncation, event/byte caps and size-based deletion are rejected. The formal return total size is reported independently.

## Shared implementation

- `tools/validate_server_observer_only_wide_causal.py`
- `tools/server_observer_runtime_supervision.py`
- `schemas/server_observer_only_wide_causal_contract_v1.schema.json`
- `schemas/server_observer_runtime_supervision_v1.schema.json`
- `contracts/server_observer_only_wide_causal_dispatch_v1.json`
- `fixtures/server_observer_only_wide_causal_v1/positive_contract.json`
- `fixtures/server_observer_only_wide_causal_v1/cases.json`
- `tests/test_server_observer_only_wide_causal.py`
- `tests/test_server_observer_runtime_supervision.py`
- `outputs/observer_only_wide_causal_gate_v1/report.json`

The contract covers 26 atomic causal roles and requires an exact source-bound signal catalog. It requires FIRST_DIVERGENCE upstream/current/downstream plus hold/clear observations, and proves every open candidate pair distinguishable through an exact candidate-by-boundary matrix. Formal return validation checks identity-bound ordered JSONL/TSV events, exact time/sequence/width and 0/1/X/Z values, end-state, heartbeat, signal-exit/timeout/nonzero partial records, exact chunk set, exact return-manifest set and compile-not-started core exception.

Runtime supervision is waveform-independent: Linux child-subreaper, fresh session/process group, escaped-descendant discovery, TERM/KILL and reap, plus same-attempt simulation-time heartbeats. A final heartbeat is taken after tree quiescence so a short successful simulation cannot escape progress evidence.

## Validation

Canonical `.venv` focused regression: 37/37 PASS. Python compile and scoped `git diff --check`: PASS. Machine report: `outputs/observer_only_wide_causal_gate_v1/report.json`.

Positive coverage includes natural, timeout, HUP, INT, TERM, nonzero and compile-not-started returns, preserved X/Z and observer aggregate above decimal 100MB as warning-only. Negative coverage includes dump enablement, hidden waveform argv/PLI, waveform members/allowlist, hard cap, sampling/truncation, derived-only expected signal, missing causal role/boundary, indistinguishable candidates, observer-driven DUT, source/catalog/matrix/identity drift, missing/unindexed chunks, time/sequence/width/four-state/end-state loss and missing partial-exit record.

## Mainline merge contract

No synonymous public rule is proposed. Narrowly strengthen existing:

- `CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001`
- `CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001`

Add build gate `observer_only_wide_causal_final_zip`; for later next-fresh packages retire the waveform-specific gates `waveform_observation_final_zip`, `waveform_portable_local_decodability`, and `fsdb_process_tree_writer_quiescence`, while preserving generalized process-tree reap and simulation-time heartbeat semantics. Update the generation index and NDP_copy README with the exact observer-only argv, event return and repeat-safe behavior.

## Claim boundary

This proves shared local package/return evidence integrity only. It does not interpret any family signal, generate or modify a family package, run production VCS, claim natural terminal/formal D/E3/E4/E5, modify public rules/plan/registry/RTL/config/numeric/workload, or perform a server action. Production source binding and runtime behavior remain first-fresh receipts owned by each family.
