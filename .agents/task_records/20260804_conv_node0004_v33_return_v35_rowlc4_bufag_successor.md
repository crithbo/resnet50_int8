# Conv node0004 v33 return → v35 ROW_LC4/Buffer_AG successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: serialized node0004 correctness only
- numeric/workload/config repeated: `false/false/false`
- functional RTL modified: `false`
- server action: `false`

## v33 formal return

The return ZIP SHA256 is
`82c1cc545d1df6a9e0359be6902c064af30d7e9631d50fcc4182177eb904105e`.
CRC, root/path safety, exact return set, allowlist, per-file receipts, source
package binding, package/install preflight and observer binding all pass.
Compile and runner exit are both zero. The observer reaches its diagnostic
finish, but the DUT does not reach natural terminal. Formal D has 0/320
present, 320 missing and zero mismatches; this is not a numerical pass.
E3/E4/E5 and the joint result gate remain false.

Qualified evidence proves six LC18 global releases while PE7 accepts, writes,
reads and forwards seven values to MSE4. The final LC18 fanout backpressure is
`0x1fffffbff`: bit 10 is the only missing sink. Active
`IGA_Interconnect.sv` maps that physical bit exactly to physical ROW_LC4.

- LAST_PROVEN_GOOD:
  `PHYSICAL_LC18_VALUE6_ACCEPTED_BY_PE7_AND_CONSERVED_THROUGH_PE7_WRITE_READ_TO_MSE4_SEVENTH_INPUT1_ACCEPT`
- FIRST_DIVERGENCE:
  `PHYSICAL_LC18_VALUE6_GLOBAL_FANOUT_RELEASE_BLOCKED_ONLY_BY_PHYSICAL_ROW_LC4_BACKPRESSURE_BIT10`
- root-cause status:
  `UNRESOLVED_BELOW_UNIQUE_ROW_LC4_FANOUT_BOUNDARY`

This closes the PE7/MSE4 index-path observation blocker and opens
`B_CONV_NODE0004_LC18_TO_ROW_LC4_BUFFER5_FINAL_FLUSH_PATH_UNOBSERVED`.
The old SA outbuffer occupancy theory remains
`INVALIDATED_NOT_RTL_BUG`.

## Single-run information-gain successor

v35 keeps the frozen c0 causal prefix because ROW/COL/Buffer_AG/prepared-data
state is cumulative and no legal hardware checkpoint or approved internal
tensor replay exists. It reduces runtime observer features from nine to five
and adds qualified, bounded ROW_LC4/COL_LC4/Buffer_AG/RD_Buffer_AG events.
The package contains a five-row candidate×observation matrix that separates
selected-input refusal, counter/output blocking, COL_LC4 fanout, Buffer_AG
queue blocking and RD/prepared-data saturation.

v34 was rejected by its own final audit because inherited generation-read
receipts still named old agent/index/server-rule identities. No workload or
observer behavior was changed to fix that. The only runnable identity is:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v35_rowlc4_bufag_diag.zip`
- bytes: `5845508`
- SHA256:
  `af9f94d12275e9b5e9b138101354811bf5fdc4c7a5f4b3ef32cf7d94dd5f90cd`
- sidecar SHA256:
  `ab02ff10ee5234337391c731a12504642826c81fbc7e47a019cc48fe8d069023`
- run:
  `bash r5_n4_hw_v35_rowlc4_bufag_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v35_rowlc4_bufag_diag_return.zip`

## Final local gates

- deterministic double build: PASS
- focused Icarus syntax/scope positive: exit 0
- hierarchy typo / declaration deletion / task syntax negatives:
  exits 1 / 4 / 2
- qualified-update deletion semantic negative: fail closed
- real runner → safe compile stub: exit 74, compile called exactly once
- TERM harness/runner: exits 0/143, partial return preserved
- canonical decision negatives: 5/5 fail closed
- feature enable/limit/time0/return-target negatives: 4/4 fail closed
- final ZIP current-rule audit: PASS, errors=0

Machine reports:

- `outputs/conv_node0004_v33_return_analysis/report.json`
- `outputs/conv_node0004_v35_package_validation/observer_scope.json`
- `outputs/conv_node0004_v35_package_validation/runner_controls.json`
- `outputs/conv_node0004_v35_package_validation/final_zip_audit.json`
- `outputs/conv_node0004_v33_return_v35_successor/report.json`

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. The continuous-closure,
time-to-root-cause optimization, qualified-event, final-ZIP self-audit and
owner-completion notification rules directly governed this result. No
non-synonymous public-rule delta is needed.

`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`.
