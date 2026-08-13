# 2026-08-12 — Portable VCD/query profile v1 mainline activation and family rebuild dispatch

## Ownership and scope

- Mainline role: `mainline.control`; owner epoch: `2`; registry epoch: `6`.
- Shared-method owner: `optimizer.whole-network`, thread
  `019fd276-14c5-7800-94db-87ebfb9ce632`.
- Existing unique rule:
  `CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001`.
- Activation epoch remains `waveform-portable-local-decodability-v1-b0a94cf60d6e` because this is the
  clarified implementation profile of the existing rule and no affected family has yet built its first fresh
  package under that epoch.
- No functional RTL, config, numeric, workload, golden, current package or server state was changed by mainline.

## Previous progress and current purpose

Previous progress: mandatory waveform v2 made the full, unbounded raw VPD authoritative and returnable, but the
real serialized-Conv v87b return proved that raw VPD transport is not synonymous with local semantic decoding.
The first portable-local activation supplied an identity-bound post-return `vpd2vcd` path, but the local machine
has no VPD decoder executable. The current Make/UCLI also proved that the misleading `DUMP_VCD=1` name actually
selects `dump -type VPD` and writes `wave.vpd`.

Current purpose: make the first later family package independently actionable without a local Synopsys tool by
retaining authoritative raw VPD and adding, in the same simulation attempt, both a distinct direct portable VCD
path and a registered complete signal-query/event receipt.

## Mainline adjudication

The optimizer publication `CURRENT_DISK_PORTABLE_VCD_QUERY_METHOD_READY` is accepted. It extends the existing
rule rather than defining a synonymous rule:

- `DUMP_VCD=1` remains the authoritative raw-VPD path.
- `DUMP_PORTABLE_VCD=1` is a distinct same-attempt `dump -type VCD` path.
- Each affected family's first fresh package must retain raw VPD, generate direct unbounded VCD and generate a
  registered query/event receipt in the original attempt.
- Direct VCD must bind actual compile/sim argv, exact dump Tcl, scope/depth, execution/attempt, raw receipt, VCD
  identity/header/timescale/catalog/completeness and return allowlist.
- The registered query/event receipt must bind the exact source-generated candidate catalog, instance paths,
  widths, timescale, contiguous event sequence, every ordered 0/1/X/Z transition, end states and allowlist.
- Neither VCD nor query/event data may have a byte, file, event or time-window cap, sampling or truncation.
- Portable evidence failure must preserve raw VPD and compile/sim/signal/core return, and must mark diagnosis
  `DIAGNOSTIC_EVIDENCE_INCOMPLETE`.
- Raw VPD cannot be cancelled in the first fresh. Only a later real return proving direct-VCD completeness and
  local readability, plus measured runtime/storage overhead and a separate mainline adjudication, may make it
  optional.

## Published shared assets

- `tools/server_waveform_portable_query.py`
- `schemas/server_waveform_portable_profile_v1.schema.json`
- `schemas/server_waveform_signal_query_receipt_v1.schema.json`
- `schemas/server_waveform_portable_runtime_receipt_v1.schema.json`
- `contracts/server_waveform_portable_query_profile_v1.json`
- `tests/test_server_waveform_portable_query.py`
- `fixtures/server_waveform_portable_query_v1/`
- `outputs/whole_network_waveform_portable_query_v1/profile_validation.json`
- `outputs/whole_network_waveform_portable_query_v1/portable_dump_tcl.example.tcl`
- `artifacts/operator_config_validation/r5-whole-network-waveform-portable-query-profile-v1/report.json`
- `.agents/task_records/20260812_portable_vcd_query_profile_v1.md`

## Validation and unproven boundary

- Portable profile focused suite: `11/11 PASS`.
- Combined mandatory-VPD, post-return local-analysis and portable-query suites: `31/31 PASS`.
- Shared helper compilation, JSON parsing, active-rule audit and scoped diff checks pass after mainline sync.
- Exact dual raw VPD plus direct VCD UCLI behavior has not been exercised by a real VCS run. Therefore each
  family must perform the first-fresh exact-ZIP implementation audit before publishing
  `PACKAGE_READY_NOT_RUN`; dynamic VCD completeness remains unclaimed until the next formal return.

## Exact family rebuild dispatch

Mainline authorizes package construction only, with fresh identities, for GAP v57, serialized Conv v87b,
native Conv p42 and QAdd v58. Each family must:

1. preserve the previous target diagnostic and freeze config, numeric, workload, golden and functional RTL;
2. change only fresh identity plus portable waveform/query/runtime-return and identity-binding surfaces needed by
   the shared profile;
3. retain raw VPD, add same-attempt direct VCD and complete registered query/event receipt;
4. run exact final-ZIP, source-bound, post-sim, runner-resilience, mandatory-waveform, portable-query and new-epoch
   first-fresh audits;
5. rotate storage only through the family-owned package manager and return `PACKAGE_READY_NOT_RUN` or an explicit
   local terminal state;
6. perform no upload, lease, remote run or other server action.

Serialized Conv additionally must bind the actual compiled DUT target/filelist/include/define/parameter,
preprocessed target and elaborated ACK driver set; retain all 65 phase-event rows plus `clk`, `rst_n` and
`slice_rst`; and keep the current conditional RTL/source-identity classification without modifying functional RTL.

Mainline will not poll the family tasks continuously. It will consume their completion receipts when they return.
Conflicts: `[]`.
