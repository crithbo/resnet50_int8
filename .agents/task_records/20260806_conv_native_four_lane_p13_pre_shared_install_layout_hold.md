# Conv native-four-lane p13 pre-shared install-layout HOLD

## Status

`PACKAGE_HELD_PRE_SHARED_INSTALL_LAYOUT_GATE`

Mainline `019fbec2-fe93-7e03-9314-cff6f222f33d` held p13 because it was built
before specialist thread `019fd276` completed the shared install-layout
contract/schema/validator/tests.

The user has now fixed the future layout semantics: runtime work/config/run/
evidence must live beneath an `install/` subtree that already exists inside the
supplied `NDP_copy0x` root before the run. The p13 root-external work-root
contract therefore cannot be used for operator pickup or server execution,
even though its earlier package-local audit passed.

## Preservation action

- No p13 package byte was changed.
- No p13 asset was deleted or overwritten.
- No successor package was generated.
- No server upload, execution or lease action occurred.
- p13 was removed from the ZIP-only operator `pending/` pickup surface and
  preserved as a pre-shared intermediate under:

  `artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_native_four_lane/r5_n4_0cc_p13_pathfix/`

- preserved ZIP bytes: `45888225`
- preserved ZIP SHA256:
  `a2c9e849bf57bc96d05ceb50c22351ae512470343bf1c96928d5b57962c8fe01`
- preserved former final-audit SHA256:
  `8342ba8cb5cb966af449773cc259337e12b610e447f1333c1566ed2d22efb77e`

Machine HOLD receipt:

- `outputs/conv_native_four_lane_0ccae916_p13_hold_pre_shared_install_layout/report.json`
- bytes `1770`
- SHA256
  `c8f9af68d1e6d5840010255c371b6caf2b14dc126f127e89c2d3ecd0b8ca2cb1`

## Storage receipt

- storage audit: PASS
- p13 indexed disposition: `superseded`
- indexed reason:
  `PACKAGE_HELD_PRE_SHARED_INSTALL_LAYOUT_GATE; preserved pre-shared intermediate pending future exact-contract rebuild`
- `pending/r5_n4_0cc_p13_pathfix.zip`: absent
- current native-four-lane pending package: none
- `PACKAGE_STORAGE_INDEX.json`: bytes `119145`, SHA256
  `0f1e1ac735899e6b03d5170deae939c13d0cbc87254cbb8eb978b90588b6c900`

Other family pending assets were not modified.

## Next action

Stop. Wait for mainline redispatch containing the exact SHA of the completed
specialist shared contract/schema/validator/tests. Do not regenerate or publish
a native-four-lane successor from summaries or from the held p13 layout.

`RULE_CONFIRMATION`

The mainline HOLD is applied exactly as dispatched. No public rule or plan was
modified, and no rule delta is proposed before the specialist contract is
available.
