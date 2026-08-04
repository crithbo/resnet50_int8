# Conv node0004 v12 final-ZIP rule self-audit

## Outcome

`r5_n4_hw_v12_hangloc_returngate.zip` is the only current Conv diagnostic
package and is `PACKAGE_READY_NOT_RUN`. It is not a functional fix and cannot
claim E3/E4/E5 before a formal server return.

- ZIP SHA256:
  `80d489798af019b00bba7ee7a7b6060de9f4cf77c2b6e57b11955995803e2e6d`
- ZIP bytes: `5811903`
- sidecar SHA256:
  `debd7103308eae24566af0db164952b7628882944c2517256b5366f55936e9d7`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- all required negative controls fail closed
- deterministic independent rebuild equals the final ZIP
- no server action, no functional RTL change, no numeric re-analysis, and no
  node0004 workload rebuild

The v12 delta is package infrastructure only. It adds final return ZIP
CRC/sidecar/exact-set/hash checks, 16 MiB compressed / 32 MiB uncompressed /
8 MiB per-file budgets, mandatory argv/sim/observer/host-progress evidence
after compile success, and a complete fail-closed canonical record if an
external signal arrives before the observer decision.

## Post-generation current-rule receipt

- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- `.agents/rules/INT8_SA点积专项规则.md`
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`
- plan mutable provenance:
  `8625b61df7094b20e71b07cb658e7fe80599df847d1c7b22adf5af613028b851`

Applicable IDs include
`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`,
`CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001`,
`CDA-SERVER-ONE-COMMAND-001`,
`CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`,
`CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`,
`CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`,
`CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`,
`CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`,
`CDA-SERVER-RETURN-RECEIPT-001`,
`CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001`, and
`CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001`.

## Validation

All commands used the bundled Python with `-B` and
`PYTHONDONTWRITEBYTECODE=1`.

1. Return gate positive test plus six negative controls: exit `0`; report
   SHA `686bce02c300feeb561e37822a3f82871ece529c0933b5d28bbb34a22fa44d5f`.
2. Four-way binding plus four negative controls: exit `0`; report SHA
   `0e0e7430105aa0c501a902a45cb74b2df0ef1ba0d6a655ccc1f140f389f075aa`.
3. Canonical decision plus five negative controls: exit `0`; report SHA
   `1dd70c2d38ee9a7502d154a2f9558ecd8e5c8295bc5a6dd9870724110d7333f1`.
4. Independent final-ZIP rule self-audit: exit `0`; report SHA
   `89e5352a23caca1e4f16bf8c01c5b55822827757fdabd01ce2df398a10dcfd44`.

The first final audit invocation correctly failed because the old four-way
negative control removed only the first occurrence of the runtime return path.
The negative-control harness was corrected to remove every occurrence; the
package ZIP was not changed. The repeated final audit then passed.

## Release and quarantine

Server command:

```bash
bash r5_n4_hw_v12_hangloc_returngate/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return:
`r5_n4_hw_v12_hangloc_returngate_return.zip` and adjacent `.sha256`.

v9 (`bce6e7...14ce`), v10 (`9dad43...f0c4`), and v11
(`27b9c6...4ea7`) remain quarantined and should be withdrawn from the server
queue. Only v12 may be run.
