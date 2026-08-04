# Conv node0004 v7 hangloc return analysis

## RETURN_ANALYSIS

- Return ZIP SHA256:
  `37e84246a8908c38ec5056c3fc965d90198a2809b049f3c7303215e508d07dcf`.
- Source package identity:
  `r5_n4_hw_v7_hangloc_bind.zip`,
  SHA256 `7752d9023f0ddae7cb506f44b4cde44f8fc8308b3b85594d0a8aae5a2b5eadc2`.
- Adjacent return sidecar is absent. The formal receipt gate is fail-closed.
- ZIP CRC, single root, 14-entry exact set, 13-record allowlist, every
  allowlisted size and SHA all pass. Internal diagnostics are consumable
  despite the formal receipt failure.
- Package/install/observer preflight pass. Runtime D was initially absent.
- Actual VCS argv contains both the package-local observer `+incdir` and
  `+define+NATIVE_RETURN_OBSERVER_ENABLE`; VCS parsed the observer include.
- Actual simulator argv enables `+RETURN_OBSERVER` and `+RETURN_HANG_DIAG`;
  time 0 emits `[RETURN_OBSERVER] enabled for slice 0`.
- Compile exit is 0, run exit is 0, signal is `NONE`. The run is not a natural
  terminal: the observer calls `$fatal` at the 8,388,608-cycle diagnostic
  budget. No formal D readback exists. E3/E4/E5 are all false.

## FIRST_DIVERGENCE

Formal-return first divergence is the missing adjacent sidecar.

Diagnostic first divergence is earlier than the v7 result gate claims:
the v7 observer adds raw Buffer4/5 enable-level sample counters to the
monotonic progress sum. Buffer4 write and Buffer5 read remain high, adding
262,144 each per sample window. That exactly creates the reported 524,288
delta while all qualified request/read-data/write-data counters remain
unchanged.

The v7 parser has a second independent error. It keeps the final
`DIAG_DECISION` line, but the observer writes a reason-bearing record followed
by a summary-only record. The summary overwrites the real decision and causes
the contradictory `C0_HANG_BOUNDARY_LOCALIZED` result.

## HANG_ROOT_CAUSE

`DIAG_DECISION=LONG_RUNNING_HANG_AT_READ_DATA_ACCEPTED_TO_BUFFER5_WRITE_ABSENT`.

The last proven-good transaction boundary is qualified read-data acceptance:
stream0=12, stream1=12, stream3=16. The first bad interval has no Buffer5
write witness, no qualified D write-data, and no terminal. The qualified IO
sum is 136 in both window 1 and window 32, so windows 2 through 32 are 31
consecutive qualified no-progress windows, well above the declared
four-window threshold.

This does not yet prove the precise internal SA RTL sub-cause. Buffer4 read is
an enable-level/edge witness, not a qualified SA-input acceptance event.
Therefore the defensible hardware interval is:

`qualified read-data accepted -> Buffer5 write absent -> D write-data absent`.

## BLOCKER_DELTA

Closed:

- v7 observer source/include/compile-enable/runtime binding is dynamically
  proven.

Opened or retained:

- formal return sidecar missing;
- v7/v8 progress classification invalid under event-qualification rules;
- c0 natural terminal and formal D readback absent;
- precise RTL sub-cause inside the bounded interval remains unproven.

Quarantine v7 and v8. v8 has the same observer SHA as v7 and does not contain
this qualification repair.

## RULE_DELTA_PROPOSAL

`NONE`. The current
`CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001` already prohibits treating a
persistent ready/enable level as one new transaction per cycle.

## PACKAGE_RELEASE

`r5_n4_hw_v9_hangloc_qualified.zip` is
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`.

- ZIP SHA256:
  `bce6e7e852885cc3c396a860f8aeb687b245a1137a7943db1b9bdc6cf9bd14ce`
- ZIP bytes: `5,807,387`
- observer SHA256:
  `97db5984e8cd33a97eb29f47fce3f073370e713d2735afdcaf63bc50cc4eb607`
- validation SHA256:
  `3aa22cfa875a3c6c8dca6e3788e3ee61ab41037ab085c08cb30e80aca4607867`
- four-way receipt SHA256:
  `98faf2c260a54c13e8ec53bf21d4ef3654236002a6a5e3a835a0be164a0ea239`
- deterministic repeated build: equal
- four-way final-ZIP validation: pass
- four negative controls: all fail closed
- functional RTL modified: false
- server RTL entries: 0
- server action: false

v9 reuses the frozen v8 c0 workload read-only. It does not repeat node0004
numeric analysis and does not rebuild the workload. Its only changes are:

1. monotonic progress includes qualified external IO handshakes only;
2. Buffer4/5 levels remain raw state and get separate rising-edge witnesses;
3. the parser accepts only reason-bearing `DIAG_DECISION` records.

Current receipts:

- plan mutable provenance:
  `256b74e977546c611d6c52f9ca0025f0a5bf677a4c6ed8b245e892e5c1473a51`
- server rule:
  `4c960c5cee73355d08f17d9d1a17edb2931b6a0336ae3831372b41f6af4dc8dc`
