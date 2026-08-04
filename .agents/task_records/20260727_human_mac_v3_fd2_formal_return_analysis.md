# Human MAC corrected-v3 formal-return analysis

## RETURN_ANALYSIS

The simulation did not hang. Compilation and simulation both returned zero,
the slice completed after 891 cycles, and stock simulation reached natural
`$finish` at 68,828,125 ps. VCS CPU time was 17.5 seconds. No timeout or fatal
event appears in the returned log.

The numeric result nevertheless fails:

- all 28 formal D readbacks are present;
- every slice has 64 lines of 16 bytes;
- lines 0--15 (256 bytes) are bit-for-bit equal to golden;
- lines 16--63 (768 bytes) are entirely unknown `x`;
- across all slices there are 448 known-equal lines, zero known-value
  mismatches, and 1,344 unknown lines.

This proves that the arithmetic represented in the first quarter is correct,
but only one quarter of the declared 1,024-byte output is present in the
formal readback range.

No diagnostic observer is present in this return. The facts above are formal
D/readback and package-log facts only.

## Last trusted boundary and first divergence

The corrected-v3 static human JSON has:

`stream_engine.stream2.dim_stride = [32, 256, null]`

The address-bound operator actually encoded into the package has:

`stream_engine.stream2.dim_stride = [32, 1024, null]`

The graph contract is correctly typed as output `uint8[1,32,32]`; it is not
misdeclared as int32. The native
`quant_from_buffer_int32MN_uint8MN` control-register handler computes the
write-stream outer stride as `d_n * 32`. With `d_n=32`, this produces 1024.
`output_writer.py` then applies that control update to the operator JSON,
overwriting the human value before encoding.

For the realized stream:

- one LC2 transaction is 32 bytes;
- eight LC2 transactions write 256 bytes per LC0 occurrence;
- four LC0 occurrences with stride 1024 address offsets
  `0..255`, `1024..1279`, `2048..2303`, and `3072..3327`;
- formal D reads only offsets `0..1023`.

Therefore only offsets `0..255` intersect the formal readback. The predicted
unwritten interval `256..1023` is exactly the returned 48 `x` lines per
slice. A stride of 256 would instead place the four groups contiguously at
offsets 0, 256, 512, and 768.

The first divergence is consequently
**native control-register materialization before encoding**, specifically
`stream2.dim_stride[1]: 256 -> 1024`. It is not an `LC2.last_index` error and
not a remaining `general_array.outport.src_id` error.

## Return identity and adjudication

- return ZIP bytes: `62980`
- return ZIP SHA256:
  `d2d8a8d39f5cb36f4fd45229fb4a9edd41b77fd61c166f33b31c11191f06df41`
- internal receipt install name and package-manifest SHA match the frozen fd2
  package;
- package preflight and package-local pre/post identity gates pass;
- required adjacent return `.sha256` sidecar is absent.

The missing sidecar requires fail-closed formal identity adjudication even
though the internal receipt and logs are coherent. Classification:

- `RETURN_IDENTITY_INCOMPLETE_SIDECAR_MISSING`
- `FIRST_DYNAMIC_FAILURE`
- `NO_DYNAMIC_BASELINE`
- `NATURAL_COMPLETION`
- `FORMAL_D_PARTIAL_COVERAGE`
- `NATIVE_MATERIALIZATION_FIELD_OVERWRITE`

This is not called a regression because no equivalent dynamic passing
baseline exists.

## BLOCKER_DELTA

Closed by this return:

- corrected-v3 GA source selection now permits arithmetic and natural
  completion;
- `LC2.last_index=1` is not implicated.

Opened/confirmed:

- native materialization overwrites the human output stride from 256 to 1024;
- the formal return sidecar is missing.

## RULE_DELTA_PROPOSAL

`HUMAN-JSON-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`: before encoding, diff
the static human JSON against the address-bound/materialized JSON. Any
non-base field change must have an explicit per-field ownership rule;
otherwise fail generation. Re-prove the formal readback byte coverage from
the materialized occurrence/address equation.

No public rule file was modified.

## PACKAGE_RELEASE

`NONE`. This round was analysis-only; no JSON or package was changed.
