# Conv native four-lane p19b RETURN_ANALYSIS → p20 observer-scope successor

## Scope

- Family: frozen node0004 native four-lane performance candidate.
- Mainline/return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Serialized Conv, functional RTL, workload, config, mapping, bitstream,
  execplan, SCA semantics, numeric/W3/golden and timeout remain frozen.
- No upload, server run or lease was performed locally.

## Formal p19b identities and internal receipt

- Return:
  `C:/Users/15383/Downloads/r5_n4_0cc_p19b_dflow_r1786123618156106372_3804102_return.zip`
  - bytes: `718510`
  - SHA256:
    `3c6881ae5c4e77e63154c2fb9a9a1f83f172031271db8be47ae93d204c4ba826`
  - execution identity: `r1786123618156106372_3804102`
- Exact source:
  `r5_n4_0cc_p19b_dflow.zip`
  - bytes: `5873801`
  - SHA256:
    `ac920faca1e90bcf31371a49529579bd8ec31a0c711a10f6f4820f60778114ef`
- Canonical analysis:
  `outputs/conv_native_four_lane_0ccae916_p19b_return_analysis/report.json`
  - bytes: `14467`
  - SHA256:
    `94d86b3e272df80d0fb2da2329ff45905b10ab5ab01348fa52d971e2285ab968`

The per-execution basename is a runtime identity, not a source mismatch. ZIP
CRC, safe root/path, return manifest/exact-set/allowlist, returned source
manifest, source files, install-only layout, NDP-root direct-set, fixed
simresult, unique return and exact-owned repeat contract all pass.

## p19b formal adjudication

- Package/path/install/observer preflights: pass.
- Production compile: started, exit `2`; VCS inner compile reports three
  `Error-[IND]` failures and final make error `255`.
- Simulation: not started.
- Signal: `NONE`; runner return status `125`.
- Actual production RTL identity: not collected because compile did not pass.
- Qualified D-flow ledger: not executed; event count `0`. No dynamic D-flow,
  config or RTL conclusion may be drawn.
- c0 slice finish/natural terminal: not proven.
- Formal D: p19b is c0 diagnostic-only and carries no formal 320D payload.
- E3/E4/E5 and performance: false/not claimed.

The unique root is package-local:

```text
native_return_observer.svh:2203
  return_obs_enabled
  return_obs_fd
native_return_observer.svh:2238
  return_obs_active
```

The imported v64 D-flow tail referenced private observer symbols absent from
the combined p19b scope. The p19b focused audit fabricated declarations for
those symbols, so it checked tail syntax but escaped the exact combined-scope
binding failure. This is not a DUT/RTL/config/numeric failure.

Blocker delta:

- closed: p19b formal transport/source/reset/install receipt;
- opened and uniquely classified:
  `B_CONV_NATIVE_P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE`;
- preserved:
  `B_CONV_NATIVE_POST_PEKEEP3_D_FLOW_FIRST_DIVERGENCE_UNKNOWN`,
  c0 slice finish, 27/27 natural terminals, formal 320D and E3/E4/E5.

## Fresh p20 successor

Disposition: `PACKAGE_READY_NOT_RUN`, diagnostic-only,
`candidate_release=false`.

Pickup ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p20_obsbindfix.zip`

- bytes: `5874994`
- SHA256:
  `68e2fc8f98fa1c6c95fa8eb56a7d5a46e9ac132719cf252be5748b3da2dca208`

p20 changes only the p19b imported-tail lexical bindings:

| p19b symbol | p20 exact module-scope binding | replacements |
|---|---|---:|
| `return_obs_enabled` | `n4d_enabled` | 14 |
| `return_obs_fd` | `n4d_fd` | 114 |
| `return_obs_active` | `n4d_active` | 13 |

No XMR or predicate changed. The final observer SHA256 is
`9ef8d8d2e8a6008c90013a5fd806a4b3cd3e5ca791180dc868c68647d27e15eb`.
All 87 installed payload members are byte-equal to p19b, and both SCA files
are exact after package-identity normalization. Deterministic double build
passes.

Exact combined-scope validation uses the three declarations extracted from
the final package itself. The focused positive compiles, and deleting or
renaming each declaration produces six fail-closed negative controls.
The earlier fabricated-declaration escape is therefore permanently covered.

Final receipts:

- build profile:
  SHA256 `900ecb1998ef9c1aea4b0b405a4bb24053e5efd6114acb58cadbbd720f04a432`;
- family audit PASS/errors0:
  SHA256 `d8b81d0e4756a647af25af11630bb6b044d821ec501d928a96f89e7cc81e9240`;
- normal/preflight-fail/compile-fail/HUP/INT/TERM harness PASS:
  SHA256 `ed4a561f1e51ad806b7c38c70b99c2a27da7fb82cebbfddebbae06cee36d19b5`;
- shared runtime-layout PASS/errors0, exact final ZIP invocation count `1`:
  SHA256 `153e3a740f872b1e1e8bca893707658816acfe694a6bc7099e7c6247b19e98c9`;
- final ZIP audit PASS:
  SHA256 `5a837502d150f1144d3193f3ab0dd2d96a9ffe8898ac6594cea19d3c12d95d77`.

Server command after extraction:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected return:

```text
/home/panqs/ndp/simresult/r5_n4_0cc_p20_obsbindfix_r<epoch-ns>_<pid>_return.zip
/home/panqs/ndp/simresult/r5_n4_0cc_p20_obsbindfix_r<epoch-ns>_<pid>_return.zip.sha256
```

Storage rotation passes:

- p19b moved to `tested/conv_native_four_lane/r5_n4_0cc_p19b_dflow/`;
- p20 is the sole `conv_native_four_lane` pending ZIP;
- `pending/` remains ZIP-only;
- storage index SHA256:
  `2fdef57c5f1385a809517c816adfad125331527f8bf16b46720854553bd7def7`.

## Rule feedback

`RULE_CONFIRMATION`: current per-execution return identity, result
conjunction, continuous closure, observer public-surface/XMR proof, exact-owned
repeat reset, install-only V2, root-direct exact-set, fixed simresult,
release-gate applicability and storage rotation rules are sufficient.

No non-synonymous `RULE_DELTA_PROPOSAL` is raised. The p19b escape is a missing
application of the existing exact combined-scope HDL gate, not a missing rule.
