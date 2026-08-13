# Conv node0004 v61 return → v62 PE keep threshold fix

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric analysis repeated: `false`
- workload rebuilt: `false`
- functional RTL modified: `false`
- server action: `false`

## RETURN_ANALYSIS

The formal v61 return ZIP is structurally valid and binds the exact v61 source
package. Production compile and simulation both exited zero, the signal receipt
is `NONE`, and the physical-LC/actual-argv observer binding is valid. The DUT did
not reach a natural terminal. Formal D is `0/320 present`, `320 missing`,
`0 mismatch`; therefore E3 passes while E4/E5 and the joint result gate fail.

## LPG / FD / root cause

- LPG: physical LC17 was accepted by LC18 and PE7, then LC18 generated its
  `last_index=3` terminal value.
- FD: that LC18 terminal did not release PE7 keep inport0, so the next physical
  LC17 value could not advance.
- Root: final materialized
  `lc_pe_configs.PE1.inport0.keep_last_index=2`, while the direct RTL predicate
  in `IGA_PE_Inbuffer.sv:167` requires
  `buffer_last_index <= keep_last_index`. The observed terminal index is 3, so
  `3 <= 2` is false. The required value is 3.

The dynamic trace proves LC18 remained ready while PE7 inport0 alone blocked the
LC17 all-destination mask. This is a configuration off-by-one, not a functional
RTL defect. The historical outbuffer-occupancy claim remains
`INVALIDATED_NOT_RTL_BUG`.

## Local rebuild

Only the PE1 keep threshold changed from 2 to 3. Mapping and execplan are
byte-identical, SCA semantics are unchanged, and the encoded bitstream differs
at exactly byte offset 1301. Boundary microtrace and changed-slice causal ledger
pass. Numeric/W3/qparam/tail/workload/golden were not recomputed.

## PACKAGE_RELEASE

`r5_n4_hw_v62_pekeep_fix` is `PACKAGE_READY_NOT_RUN`,
`candidate_release=false`, classification
`CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

- pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v62_pekeep_fix.zip`
- bytes: `5158130`
- SHA256:
  `613eb2a6e4dc14f65065c1a4cd880f0f42828b25a6ebde8383ae78f6d2bdec40`
- command:
  `bash r5_n4_hw_v62_pekeep_fix/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- expected return:
  `/home/panqs/ndp/simresult/r5_n4_hw_v62_pekeep_fix_return.zip`

Deterministic double build, family validator, shared install-only V2 harness,
observer/predicate trace, configuration negative controls, final-ZIP audit, and
storage audit all pass with exit zero. v61 is archived under `tested`; v62 is
the sole pending package for `conv_serialized_node0004`.

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. Qualified handshakes, exact mapper
identity, direct RTL consumer semantics, changed-slice ledger, boundary
microtrace, and current final-ZIP gates were sufficient to distinguish this
configuration defect from a DUT defect. No public-rule delta is proposed.

