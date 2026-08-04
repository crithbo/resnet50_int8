# Conv node0004 v7 observer four-way binding review

## Current receipts

- Mutable plan provenance:
  dispatch `fdd8cf3e14128d40a141655f60cd79b80d46c6f6626446c56daba837ee9cc8a6`;
  finish-observed
  `3b4db10d51d23d5f081f0470d435a0c15730b65b34a896ae62f27f88196e5891`.
  This drift is mutable provenance only and did not trigger a rebuild.
- Server-package rule:
  `4c960c5cee73355d08f17d9d1a17edb2931b6a0336ae3831372b41f6af4dc8dc`.
- Applied rule: `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`.

This was a final-ZIP binding audit. It did not repeat node0004 W3 analysis,
rebuild the numeric workload, inspect a server, upload, or run.

## v7 adjudication

The reviewed ZIP remains byte-identical:

```text
r5_n4_hw_v7_hangloc_bind.zip
bytes = 5803877
sha256 = 7752d9023f0ddae7cb506f44b4cde44f8fc8308b3b85594d0a8aae5a2b5eadc2
```

The independent validator reads the final ZIP rather than the builder or
unpacked package directory. v7 has a valid CRC, one root, the normalized
package-local `+incdir`, and the exact enable macro. It nevertheless fails the
new rule because its final manifest has no `observer_binding_four_way` object:
the observer's expected `size_bytes` and the exact runtime/return binding are
not declared. Its fixed status is therefore
`PACKAGE_OBSERVER_BINDING_INCOMPLETE`; v7 is quarantined and must not run.

## Fresh successor

`r5_n4_hw_v8_hangloc_fourway` retains v7's compile macro/include repair and
frozen c0 workload. The only semantic addition is the manifest-level four-way
binding contract and the corresponding receipt:

- source: unique `tb_probe/native_return_observer.svh`, 121822 bytes,
  SHA256 `9a6cc0f3c4d7e9235199ecc33d2ba4649462b7b64fcc1235aa1ce7f77d53f82e`,
  readable after a fresh extraction;
- include: exactly
  `+incdir+$package_root/tb_probe`, normalized within the package root;
- compile enable: exactly one
  `+define+NATIVE_RETURN_OBSERVER_ENABLE`;
- runtime/return: `+RETURN_OBSERVER`, `+RETURN_HANG_DIAG`, the time-zero
  `[RETURN_OBSERVER] enabled` marker, actual compile and simulator argv,
  observer/host progress logs, sim log, result/status receipts, and
  EXIT/HUP/INT/TERM collection paths.

The direct final-ZIP result is `FOUR_WAY_BINDING_VALIDATED`.

## Negative controls

All four mutations fail closed as `PACKAGE_OBSERVER_BINDING_INCOMPLETE`:

1. delete observer source;
2. delete/replace package-local `+incdir`;
3. delete the compile enable macro;
4. delete the observer return-allowlist binding.

Focused tests are 7/7 PASS. Combined v7/v8 related tests are 11/11 PASS.

## Package identity

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v8_hangloc_fourway.zip`.
- ZIP bytes: `5804862`.
- ZIP SHA256:
  `44e592e4d6059b22d4ccfa76e17ec5d7a995e6375b1960ed743893e212a70308`.
- Sidecar file SHA256:
  `40403fefc80c72541c370c0b7af995004477367ed508e3b2015f855b4456ed58`.
- Package validation SHA256:
  `4aecb4d487d06a50df05f0bb5e217ce2a21547bc265707ce58c81cc0d1b9dc4a`.
- Four-way receipt SHA256:
  `d7b4c1ab62c4156ac5df8ea79452a71b345083c696f0a41a36504c595ba17eb6`.
- Status: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`.
- Functional RTL entries: 0; server TB modified: false.

## BLOCKER_DELTA

- QUARANTINE `r5_n4_hw_v7_hangloc_bind.zip`.
- CLOSE `B_CONV_NODE0004_V7_PROGRESS_BIND_DYNAMIC_VERIFICATION`.
- ADD `B_CONV_NODE0004_V8_PROGRESS_BIND_DYNAMIC_VERIFICATION`.
- KEEP `B_CONV_NODE0004_C0_LONG_RUNNING_HANG_ROOT_CAUSE`.
- KEEP `B_CONV_SERVER_DYNAMIC_RELEASE`.
- KEEP `B_CONV_SERVER_RTL_IDENTITY`.
- KEEP `B_CONV_INT8_SA`.

## RULE_DELTA_PROPOSAL

None.

## PACKAGE_RELEASE

- Functional package: `NONE`.
- Diagnostic package:
  `r5_n4_hw_v8_hangloc_fourway.zip`,
  `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`.

## Evidence assets

- Machine report:
  `artifacts/operator_config_validation/r5_conv_node0004_v7_four_way_binding_review_v1/report.json`,
  SHA256 `985a91e2839561698c6e758e501caa42f0a00ec202bee03a9f781d7521c88572`.
- Independent final-ZIP validator:
  `tools/validate_node0004_observer_four_way_binding.py`,
  SHA256 `30dc51bef625ee9e9361bc2c80d596971a2d467ca836f48d15ac383d2f90000a`.
- Four-way/negative-control test:
  `tests/test_node0004_observer_four_way_binding.py`,
  SHA256 `5b21557b852b5cd43f863ccb378e58919e45cb462edc47411c25cf5c2a313bc3`.
- v8 builder:
  `tools/build_node0004_v7_four_way_binding_package_v8.py`,
  SHA256 `9f85ca2524619927b87841d38738a811523b7ac1e666cb261264ddcfabe0f1a7`.
