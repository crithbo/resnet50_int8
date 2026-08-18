# p52 / v97 / GAP v71 formal-return analysis dispatch

- date: 2026-08-15
- mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- registry epoch: 6
- disposition: analysis first; managed storage frozen until family receipts are accepted and serialized

## Exact returns

- native Conv p52: `C:/Users/15383/Downloads/r5_n4_0cc_p52_memtupleleaf_r1786793357121273848_2914398_return.zip`, 124528356 bytes, SHA-256 `3dbec1a4a0bfcb04d0c95bece9b0e2c1b274dcbdc90f7a54f53b45fc48e04331`; routed to `family.conv.native` thread `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`.
- serialized Conv v97: `C:/Users/15383/Downloads/r5_n4_hw_v97b_tbvcd_memtuple_xmrefix_r1786793347853153460_2912853_return.zip`, 710085642 bytes, SHA-256 `5bc3e44f95cd5df54de5deff9c084d7dbc192215657ec4e504335b900b30aa1d`; routed to `family.conv.serialized` thread `019ff02d-901b-7f70-a9da-f54e268b5bbe`.
- GAP v71: `C:/Users/15383/Downloads/r5_n71_gap_v71_sum_s2_tbvcd_colcfg_r1786793366049290840_2915952_return.zip`, 60627798 bytes, SHA-256 `656981c8b65a9109753f1c622a248989eb11d0bb2c47615a56d6873c649a39c4`; routed to `family.gap` thread `019ff02d-8225-7d21-9779-e46ce4130572`.

## Required adjudication

- Consume each return with bounded streaming/resume and incremental report/checkpoint artifacts.
- Bind exact package, execution root, config, source and return identities before functional claims.
- Treat config plus actual compiled RTL plus same-attempt dynamics as direct causal evidence.
- If the target ran but no root closes, perform `RULE_GAP_AUDIT` before the next fresh package. Apply `PACKAGE_BUILD_FAILURE_RULE_AUDIT` for repeated package/pretarget failures.
- GAP v71 was not in the accepted pending set, so provenance and config authorization/equivalence must be proven before it may alter the v70 validated root.
- No family may call the storage manager until mainline grants a sole-writer release. No server action is authorized by this dispatch.
