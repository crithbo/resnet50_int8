# Trassic master d0aa87f active RTL sync

## Scope

- Mainline owner: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- User authorized checking the authenticated GitHub hardware repository and synchronizing the current fix into `NDP_copy01/rtl`.
- Dirty-worktree preservation was mandatory. No reset, checkout, clean, deletion, or unrelated overwrite was performed.

## GitHub authority

- Repository: private `xlsjdjdk/Trassic2.0_RTL`, branch `master`.
- Previous synchronized commit: `8f2f3181c1103d705cdf9b9722959e7315f8b875`.
- Current head: `d0aa87f682880a260fb792aaac88f70a23aba414`.
- Functional fix commit: `cb11353d4196b4af26aac18b4dcc39ba0027e8bc`.
- GitHub compare reports two commits and exactly two changed files, with three additions and three deletions.
- Authenticated browser archive: `C:/Users/15383/Downloads/Trassic2.0_RTL-d0aa87f682880a260fb792aaac88f70a23aba414 (1).zip`, bytes `76739307`, SHA256 `d025daab17e8ce60bcad6f6d7208377f8ec74287b060d3d52ad9fa8138163806`.

## Three-way conflict gate

Both active local files were byte-equal to the previous `8f2f3181` authority before synchronization. Therefore no user/parallel drift overlapped the two upstream changes.

| File | Previous/pre-sync SHA256 | New upstream/post-sync SHA256 |
|---|---|---|
| `SA_PE_Float_CSA.v` | `ea24759841d990f230f9c33a111f934e107c996a85b2f5ea00c9408ca73d0223` | `429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a` |
| `SA_PE_Float_Control.v` | `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6` | `00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb` |

The active local files now match the two archive members exactly. No upstream-deleted local file was removed.

## Directed functional revalidation

Focused Icarus/VVP compilation succeeds, but the repair acceptance simulation fails:

- frozen node0075 `-19 + 19`: expected `0x00000000`, observed `0x80000000`;
- frozen Conv node0003 `-5 + 5`: expected `0x00000000`, observed `0x80000000`;
- adjacent Conv `-6 + 5 = -1` and `-4 + 5 = 1` controls pass.

The two pre-existing independent witnesses were recompiled against the new exact source identity and still reproduce the same exact-cancellation failure. Therefore the GitHub change is real and synchronized, but it does **not** close either hardware capability blocker. Source sync is not promoted to functional repair.

## Return dispatch receipts

- Conv v29 return: bytes `99367`, SHA256 `80bc305d70106952a15887e9e72b275d8572126d5dd46d17087523c37656d069`.
- GAP v29 return: bytes `125678`, SHA256 `2b990565c41da4984bb1293ccbaf135a0f92ccee955e11653f25c60fd0c1a0bd`.

Both are delegated to their persistent family owners for formal RETURN-to-successor closure. The `(1)` suffix is treated only as a local duplicate-download name; no adjacent external sidecar claim is inferred.

## Claim boundary

- Proven: authenticated source head and exact two-file local synchronization; focused compile; focused directed failure persistence.
- Not proven: full-design VCS identity, E2, server natural terminal, formal D, E4/E5, node0075 materializer, or Conv native-four-lane package.
- Functional RTL was not authored by mainline; only authenticated upstream source bytes were synchronized.

Machine report: `artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json`.
