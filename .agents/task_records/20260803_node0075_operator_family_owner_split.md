# node0075 operator-family owner split

## Provenance

- date: `2026-08-03`
- mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- pre-split plan SHA256:
  `6b82860af88b991cb4401fa2f3b36bbda5a2d04ff2e247addb4a5daeaf3375b8`
- old shared-backend owner:
  `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- new independent QLinearMatMul owner:
  `019fc775-8de0-7f10-bc4a-026a4673776f`

## Adjudication

Shared INT8-SA, Buffer, MSE, mapper, bitstream and execplan primitives do not
make QLinearMatMul part of the Conv operator family. The earlier dispatch used
hardware-backend ownership and is superseded by strict operator-family
ownership.

node0075 is now owned exclusively by the independent QLinearMatMul task. The
new task may read and reuse already accepted Conv/SA primitives, but it must
not:

- modify Conv family assets;
- report node0075 progress as Conv coverage;
- mix node0075 blockers or rule feedback into Conv receipts;
- modify mainline plan, public rules or functional RTL.

The old owner was notified to stop node0075 work at a safe message boundary,
preserve any read-only findings, avoid deletion or rollback, and return to
Conv-only work.

## node0075 scope

The independent owner receives the complete node0075 scope:

- MatMulInt32Accumulate/QLinearMatMul schema, handler and registry;
- node0075 A consumer materializer and the authorized minimum necessary
  at-least-8-pass qualified reload path;
- B/weight, bias/psum and rank-2 INT8-SA accumulation;
- exact UINT8 requant tail with output zero-point 60;
- D endpoint and formal readback;
- deterministic target JSON, mapping, bitstream, execplan and SCA;
- config-bound E2 and, only after E2, a diagnostic non-production server
  package.

The current A repeated-read authorization and all no-copy/no-host-replay,
visibility, occurrence, traffic and lifetime gates remain unchanged.

## Conv scope after split

The Conv owner retains node0004 and the remaining Conv instances. The current
route remains the previously authorized correctness-first, performance
non-optimized serialized single-nonzero-product baseline:

- `candidate_release=false`;
- compute occurrence multiplier: about 4x;
- weight payload multiplier: about 4x;
- activation payload multiplier: about 4x;
- at most one useful product lane per four-lane occurrence;
- maximum useful product-lane utilization: 25%;
- no production or performance-pass claim.

The immediate Conv task remains the node0004 v28 D-write path diagnostic and
the natural-terminal/320-formal-D joint gate. The remaining 52 Conv instances
must not be expanded before the representative node closes.

## Server and mutation boundary

No server upload, run or lease is authorized by this split. No functional RTL
or public-rule change is authorized. Both owners must proactively report
PACKAGE_READY_NOT_RUN or the first precise blocking leaf to the mainline.
