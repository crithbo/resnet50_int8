# Trassic master e1fb0f7 direct checkout and NDP_copy01 RTL sync

Date: 2026-08-04

## Adjudication

- The former non-Git `Trassic2.0_RTL` snapshot was removed and replaced in place by
  the real `xlsjdjdk/Trassic2.0_RTL` Git checkout.
- Local `master`, `origin/master`, and `HEAD` are all
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`; ahead/behind is `0/0` and the
  checkout is clean.
- No old snapshot or temporary audit clone was retained.
- `NDP_copy01/rtl` was transactionally replaced by the exact contents of
  `Trassic2.0_RTL/code/NDP_rtl`. The staged copy was fully hashed before the old
  target was removed.
- Both historical `NDP_copy01/rtl_pre_*` backup directories were deleted, and no
  staging directory remains.

## Exact local receipt

- source files/bytes: `2260 / 50685721`;
- target files/bytes: `2260 / 50685721`;
- source and target tree receipt:
  `70334ce5f9addcfa409d566e7f7215b9870f815a7afc813d55f020a3af3ae647`;
- exact per-file source/target SHA comparison: `PASS`.

Machine report:
`artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json`,
bytes=`2519`,
SHA256=`c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c`.

## Server and package boundary

The user confirmed that the real server root has also been replaced with the
latest RTL. This closes the documentation ambiguity that the server still uses
the old source baseline.

Existing ZIPs are immutable. A package name or build provenance containing
`df23e4d` remains historical provenance and was not rewritten. Packages that
consume the server root will compile the current server RTL; their formal return
must still bind the actual compile identity, natural terminal, and formal D before
any E3/E4/E5 or performance claim.

## Persistence

`Trassic2.0_RTL` is now pinned in `repos.lock.json` as an independent Git checkout
instead of being described as an activity mirror. The project README,
`NDP_copy01/README_HARDWARE_SIM_ENTRY.md`, and current plan were updated to use
the same identity and claim boundary.

Mutable documentation receipts at completion:

- `.agents/plan.md` SHA256=
  `83ee1f0f9cd938a46bdc2bf6a259b00c16752a909f17aa6b117fa7520bfe6fe8`;
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` SHA256=
  `e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`.

No functional RTL edit was authored by the mainline, no server package bytes were
changed, and no server run/upload/lease action was performed.
