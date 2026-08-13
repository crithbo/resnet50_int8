# Trassic cloud master 0ccae916 direct checkout and NDP_copy01 RTL sync

Date: 2026-08-05  
Owner: mainline `019fbec2-fe93-7e03-9314-cff6f222f33d`  
Status: `DIRECT_FAST_FORWARD_AND_NDP_COPY_SYNC_PASS`

## Authority and direct checkout

The signed-in GitHub authority check established
`xlsjdjdk/Trassic2.0_RTL/master@0ccae916ef61904a64d6cf8ec1d1931b45e428d8`.
The local independent checkout was clean at
`e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`; ancestor verification passed and
`master` was fast-forwarded directly by 12 commits to exact `0ccae916`.

No old RTL snapshot or backup copy was created or retained. The local
`origin/master` tracking ref remains at e1 because a credential-less fetch failed with
`SEC_E_NO_CREDENTIALS`; it was not fabricated. Cloud authority is bound by the signed-in
GitHub report and the immutable local 0cc commit object, not by that stale tracking ref.

Cloud authority report:

- `artifacts/rtl_sync/trassic_cloud_master_0ccae91_20260805/report.json`
- SHA256=`c77e81c7d7ee5b7f557e52a8ec22cb8318cac06ff0ead2aeab80aaa236e25d93`

## NDP_copy01 exact sync

The 11 cloud-changed paths under `code/NDP_rtl` were copied directly to the same relative
paths under `NDP_copy01/rtl`. Full-tree per-file size/SHA comparison then proved:

- source files/bytes=`2262 / 50706759`
- target files/bytes=`2262 / 50706759`
- missing/extra/different=`0/0/0`
- source tree SHA256=`c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093`
- target tree SHA256=`c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093`
- `rtl_pre_*` backup directories=`0`

Tree algorithm:
`sha256(UTF8 concat(sorted(relative_path + NUL + size + NUL + lowercase_file_sha256 + LF)))`.

Machine report:

- `artifacts/rtl_sync/trassic_master_0ccae91_20260805/report.json`
- bytes=`3465`
- SHA256=`5b2af42c6893abe6f21d7a8a91097d623bee0afe524d2518bf745d3872adf71b`

## Project binding

- `repos.lock.json` now pins `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`;
  bytes=`1980`, SHA256=`92980ab96eb25127551275b37a1f0dfa12e3e15ef0a3cc9b0093f64c77fad4f1`.
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` records the same commit/tree;
  bytes=`6044`, SHA256=`0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`.
- `.agents/plan.md` records the same direct-sync state;
  bytes=`13835`, SHA256=`03a0d2cd66ea9174320224e21a865f063cd1fb371d7cdb56632861df0d4215d3`.

This action synchronized existing upstream functional RTL; mainline authored no functional RTL
change. No server package bytes were modified, and no server upload/run/lease action occurred.
Actual production compile identity and operator dynamic results remain formal return evidence.

## Validation

- `tools/sync_repositories.py verify --repo Trassic2.0_RTL`: exit=`0`, exact pinned
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`.
- `python -m unittest tests.test_repository_sync -v`: `11/11 PASS`, exit=`0`.
- Whole-project repository verify stopped on a pre-existing unrelated dirty
  `CGRA_SIM/cgra_python/layout/layout_buffer.py`; this did not affect the targeted Trassic
  verification and was not modified or cleaned.
