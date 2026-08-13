# Conv native-four-lane p17 RETURN → p18 PE keep-threshold successor

## Outcome

- Formal p17 return is valid for c0 diagnosis. Production compile completed
  with exit 0, the genvar-static XMR gate closed, and DUT simulation started.
- The later `INT` occurred after four identical qualified no-progress windows;
  it does not erase the already-stable functional stall.
- p17 contains no formal 320D payload by design. It neither passes nor fails
  formal D, E3, E4, E5, or performance.
- The first divergence is the fourth MSE4/PE1 flattened-index occurrence.
  `lc_pe_configs.PE1.inport0.keep_last_index=2` rejects the reachable terminal
  index 3. The exact current predicate requires `3 <= keep_last_index`.
- Fresh p18 changes only that leaf from 2 to 3. Mapping remains
  `LC15→LC17`, `LC9→LC18`, `PE1→PE7`; final bitstream changes one byte at
  offset 1301. The prior `transout_last_index=5` and Buffer-AG `[5,5]` fixes
  remain intact.

## Formal p17 evidence

- Return analysis:
  `outputs/conv_native_four_lane_0ccae916_p17_return_analysis/report.json`
  - bytes: 29618
  - SHA256: `e77fb6a35cb1f12fc8f63ae4e5f0b8f520e89eccb2cf4e2e4753985fa16496b1`
- Source p17 ZIP SHA256:
  `3828628f2573c3cd970330fba60bd3393b305555085c5517ea074a919f40a978`
- Qualified c0 counts: SA input 30, SA output 4, MSE4 index 3,
  Buffer5 ARM accept 4, MRM accept/clear 16/16. Final Buffer5 mask is `0xff`
  and the next SA output is held valid with ready low.

## p18 materialization

- Local report:
  `artifacts/operator_config_validation/r5-conv-native-four-lane-0cc-p18-pekeep3-c0/local_rebuild_report.json`
  - SHA256: `e19ee936e99063d476e2598fa51e0caf2bcecc6c1d83b0e5bd4a0d9cf57a041f`
- Changed transaction ledger SHA256:
  `32f0e36fc3f5d1edc1d7ae6c60019b789fdfd132c61111fe694238a77759c613`
- Boundary microtrace SHA256:
  `0c4774d6259bb2269821f6b542d2709ccb745b7549880a8c2a325a11e97e3e35`
- New bitstream SHA256:
  `2f79247677c0ae8a8f89ac1bca7f381d757e28d049c7eef88e8f0bfae75d90fa`
- Numeric/W3/golden were not repeated; address surface and functional RTL did
  not change.

## Package release

- `PACKAGE_RELEASE=PERFORMANCE_DIAGNOSTIC_CANDIDATE`
- `candidate_release=false`
- `lifecycle=PACKAGE_READY_NOT_RUN`
- Pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p18_pekeep3.zip`
  - bytes: 45941995
  - SHA256: `381e0d8597e72350d5403b73c98ea4d5986d220481cf643b188252b34286eada`
- Command:
  `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected fixed return:
  `/home/panqs/ndp/simresult/r5_n4_0cc_p18_pekeep3_return.zip`
  and adjacent `.sha256`.

The exact ZIP passed deterministic double build, path/preflight, all
normal/preflight-fail/compile-fail/HUP/INT/TERM/missing-install runner
scenarios, fixed-simresult publication, NDP-root direct-set preservation, and
the shared install-only V2 validator (errors 0).

The first family audit had two validator-only mistakes: it stripped the SCA
`runs/c0` layer twice and required two byte-identical regenerated execplans to
change. The ZIP was not rebuilt. Content-neutral revalidation reused the
already-passed shared gate exactly once:

- revalidation SHA256:
  `aad21db60f7f64b9c1450d7fbdee7b9e83d66da0dd8cc89a037cd66874083cc4`
- shared validation SHA256:
  `ae0e0db42412bce9291c372cf55b6a734ee33f37d3f02795a82356dcd2de334d`

Storage rotation moved the formally consumed p17 set to `tested`; p18 is the
only pending ZIP for `conv_native_four_lane`.

## Claim boundary and blocker delta

- Closed: p16 dynamic-XMR compile blocker, Buffer5/public causal unknown, deep
  MSE4/Buffer5 leaf unknown, and p18 local config→consumer closure.
- Opened: p18 dynamic c0 keep3 return.
- Preserved: c0 slice_finish, 27 natural terminals, formal 320D, performance,
  E3, E4, and E5.

## Rule feedback

`RULE_CONFIRMATION`:

- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`
- `CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001`
- `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`

No non-synonymous rule delta is proposed.
