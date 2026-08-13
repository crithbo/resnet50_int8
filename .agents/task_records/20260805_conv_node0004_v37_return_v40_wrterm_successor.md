# Conv node0004 v37 return → v40 WR-terminal successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: serialized node0004 correctness only
- numeric/workload/config repeated: `false/false/false`
- functional RTL modified: `false`
- server action: `false`

## v37 formal return

The return ZIP is 105608 bytes with SHA256
`6a2cc106f6124f3640340531d5f1e62bac245e3c8674bd3fdb0e3307714a2d37`.
Its absent adjacent sidecar is transport-only under the user-attested rule.
CRC, root/path safety, exact return set, allowlist/per-file receipts, source
binding, package/install/runtime-D preflight, observer identity, actual argv,
compile, run and signal gates pass. Compile and runner exit are zero and
signal is `NONE`.

The DUT does not reach natural terminal. Formal D has 0/320 present,
320 missing and zero mismatches; zero mismatches with all items missing is not
a pass. E3/E4/E5 and the joint result gate remain false.

This is not a regression. v37 moves the proven boundary downstream:

- LAST_PROVEN_GOOD:
  `32_WR_DESCRIPTORS_AND_32_PREPARED_GROUPS_CONSUMED_THROUGH_DATAHUB_CROSSBAR`
- FIRST_DIVERGENCE:
  `PREPARED_GROUP_33_AND_34_HAVE_NO_CORRESPONDING_WR_DESCRIPTOR_AND_REMAIN_AS_COUNT32_PLUS_ONE_HOLD`

The address side accepts 16 Memory_AG input1 tuples and produces exactly
32 descriptors. All 32 descriptors are pushed, popped and accepted through
DataHub. The data/tag side prepares 34 groups. After the last descriptor,
two 16-entry groups remain (`prepared_count=32`), one following group is held,
and the RD tag queue remains count 2/full.

v37 excludes descriptor-FIFO live stall, masked-write dependency, output-slot
backpressure, memory write-data ready and DataHub arbiter/bank/queue stall.
It does not yet distinguish excess data scheduling, stale tag/data lifetime,
early address terminal and descriptor-unaware prefetch. No configuration or
functional-RTL defect is claimed.

The former
`B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` remains
`INVALIDATED_NOT_RTL_BUG`.

## v40 successor

The only runnable successor is
`r5_n4_hw_v40_wrterm_diag`, classified
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, `candidate_release=false`.
It keeps the frozen cumulative c0 prefix because no approved checkpoint can
recreate internal descriptor, tag and prepared-data queues.

One new low-cost feature, `RETURN_OBS_WRTERM`, begins qualified chronology at
the final descriptor pop. `WRTERM_EDGE_V1` records subsequent Memory_AG
input1 accepts, descriptor push/pop, tag push/pop, prepared writes and hold
rises with last/index and queue state. `WRTERM_BOUNDARY_V1` returns the
aggregate discriminator. State levels do not count as progress.

The final compiled HDL actual-consumer span contains 21 unique XMR
expressions. All 21 are parsed from the exact final ZIP source, classified and
bound to current RTL owners; uncovered count is zero. Focused Icarus positive
compile exits 0. Mutating the real consumer expression, deleting state owner,
deleting enable owner and misspelling the task consumer exit 1/5/6/1.

The real runner reaches the safe compile stub exactly once and exits 74 as
intended. TERM exits 143 and preserves the partial return. Feature enable,
limit, time-zero marker and return-target negatives fail closed. Canonical and
path-budget negatives fail closed. Final ZIP self-audit passes with zero
errors.

Two non-runnable intermediates are quarantined: v38 omitted a runtime-consumed
path-budget field; v39 omitted the final-audit target-root budget declaration.
Neither changes the frozen DUT workload or configuration.

## Package release

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v40_wrterm_diag.zip`
- bytes: `5849371`
- SHA256:
  `f1695ec3232e1e651a3242603e299c5ce0b4a46762ec9a23401e0bf7a5523d9e`
- sidecar SHA256:
  `00fc6a6fff7cfdc0a91233d1241912ac59b6b08dd584e7b63e488cc6f0b91d90`
- run:
  `bash r5_n4_hw_v40_wrterm_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v40_wrterm_diag_return.zip`

`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`.

## Machine reports

- `outputs/conv_node0004_v37_return_analysis/report.json`
- `outputs/conv_node0004_v37_return_analysis/v40_successor_release.json`
- `outputs/conv_node0004_v40_package_validation/observer_scope.json`
- `outputs/conv_node0004_v40_package_validation/runner_controls.json`
- `outputs/conv_node0004_v40_package_validation/final_zip_audit.json`

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`.
The current actual-consumer negative, diagnostic time-to-root-cause, feature
end-to-end, path-length, final-ZIP and continuous-closure rules rejected the
two incomplete intermediate manifests and admitted only v40. No non-synonymous
public-rule delta is proposed.
