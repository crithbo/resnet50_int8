# node0075 A repeated-read diagnostic bypass authorization

## Provenance

- date: `2026-08-03`
- mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner thread: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- user authorization: allow at least 8x legal repeated A reads as a diagnostic
  bypass
- pre-update plan SHA256:
  `cf10be7d807f73924ef7a975d7b135eb0337fa16b7792708d8b5efe663fd9a6f`

## Determined capacity bound

The active stock-SA path has the following currently audited bound:

- A Buffer lifetime field: 4 bits, at most 16 accesses per load;
- parallel output columns per SA use: 8;
- maximum output columns served by one A load: `16 * 8 = 128`;
- node0075 output columns: `N = 1000`;
- minimum A reload passes: `ceil(1000 / 128) = 8`.

This is a stock-RTL/config scheduling-capacity constraint, not a confirmed
functional RTL defect.

## Authorized bypass

The owner may materialize the minimum necessary number of repeated node0075 A
consumer reads, with at least 8 passes, as a correctness diagnostic and
non-production path.

Each pass must:

- point only to the same node0071-owned 16 slice bases;
- consume the same 2,048 valid bytes per slice as 64 ordered 32-byte
  transactions;
- be represented by real node0075 qualified consumer occurrences;
- retain node0071 as the allocation owner;
- preserve the exact unique byte set of 32,768 bytes;
- prove its ordered-address and read-byte-set receipts;
- occur only after the node0071 producer-final visibility barrier.

If exactly 8 passes are sufficient, the expected accounting is:

- 512 accepted 32-byte read occurrences per slice;
- 8,192 accepted occurrences over 16 slices;
- 262,144 bytes of total accepted A read traffic;
- 32,768 bytes of unique A storage.

If final stock fields require more than 8 passes, the materializer must report
the exact mechanically necessary pass count, formula and reason. Unbounded or
unexplained repeated reads are not authorized.

Allocation release is extended through the last accepted A read of the final
pass and the absence of pending consumer transactions.

## Prohibited substitutions

This authorization does not permit:

- host copy, precompute, tensor replay or relayout;
- a new A scratch allocation;
- changing the node0071 storage owner;
- treating producer base addresses as consumer acceptance evidence;
- replaying computed partial sums or final outputs;
- modifying functional RTL.

Qualified repeated reads of the same producer-owned byte set are explicitly
distinguished from prohibited host or computed-tensor replay.

## Claim boundary

This authorization only removes the prior exact-once A-read restriction for a
diagnostic materializer. It does not close:

- the MatMul/QLinearMatMul handler, registry or materializer blocker;
- B/weight layout and traffic;
- bias/psum accumulation;
- rank-2 SA arithmetic;
- exact UINT8 tail with output zero-point 60;
- D endpoint/formal readback;
- config-bound E2 or any E3/E4/E5 gate.

The owner may proceed through deterministic target JSON, mapping, bitstream,
execplan and SCA generation. A fresh server package remains forbidden until
config-bound E2 closes. No upload, server run or lease is authorized.

The owner must proactively notify the mainline at `PACKAGE_READY_NOT_RUN` or
the first newly proven blocking leaf, including the actual repeat factor,
traffic receipts, blocker delta and evidence-backed rule feedback.
