# Conv node0004 v59 shared-layout parent-precondition HOLD

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Status: `PACKAGE_HELD_SHARED_LAYOUT_PARENT_PRECONDITION_TOO_STRICT`
- Successor: not built; wait for shared rule/tool exact receipts and mainline
  redispatch.

## Reason

The actual p14 server run proved that the shared install-layout contract was
too strict: it required all three of `install`, `install/cfg_pkg`, and
`install/codex_runs` to pre-exist. The corrected shared intent is that only
`$server_root/install` must pre-exist as a real, non-symlink directory; a
package may create `cfg_pkg` and `codex_runs` beneath it.

v59 embeds the same three-parent precondition. Therefore its previous local
PASS receipts remain historical evidence only and cannot authorize a run.
Content-neutral receipt refresh is explicitly forbidden.

## Storage disposition

The complete eight-member v59 package/receipt set was moved without overwrite
from pending to:

`artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_serialized_node0004/r5_n4_hw_v59_install_subtree/`

The archived ZIP remains byte-identical:

- bytes: `5153755`
- SHA256:
  `e5023a50e827ae3d4b0fc6bb9ac327c9aa38d9e72db068cc4fd567f8e76a216d`

After the move:

- storage index: PASS
- serialized Conv pending set: empty
- total pending packages: 3
- total superseded packages: 30
- successor built: false
- server action / upload / lease: false

Machine receipts:

- hold adjudication:
  `outputs/conv_node0004_v53_install_subtree_successor/v59_hold_shared_parent_precondition.json`
  SHA256
  `7c0cb6310b3437ec3c89269978226b2b5c2d17abd86b0dbeff138534710dfebf`
- storage receipt:
  `outputs/conv_node0004_v53_install_subtree_successor/v59_storage_hold_receipt.json`
  SHA256
  `a8aa876363a2380bdf74aa225c5c0273dd3e8f1dbfd6aeb034829dd1cf766239`
- storage index SHA256:
  `c77e9705b0ca95a7eba7ab766e6591909e092e5196aa2e9b8aaf59a6d73315d1`

## Claim boundary

v59 bytes and its family/shared validation reports are preserved only as
historical evidence. DUT/config/numeric/observer/RTL are frozen. No new
package may be constructed until the shared audit owner publishes fresh exact
rule/tool identities and the mainline explicitly redispatches this family.
