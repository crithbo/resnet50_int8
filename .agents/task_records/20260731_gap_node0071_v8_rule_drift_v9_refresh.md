# GAP node0071 v8 post-generation rule drift and v9 receipt refresh

Date: 2026-07-31  
Owner thread: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- This is a receipt-only post-generation rule-drift review. No server return was
  parsed and no server action was taken.
- Frozen v8:
  - ZIP:
    `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v8_dual_ingress.zip`
  - bytes: `1791519`
  - SHA-256:
    `cb1b43b3e8228951a2c62e8de02b36f17291a2561048cb1b36c0a9ed876b5a0f`
  - sidecar SHA-256:
    `66504e75d9573cb8a8d1f415a58ed8943da4a18e0149806795aa09d78a4a388a`
- The direct v8 audit failed closed with exactly one semantic class:
  `current rule SHA differs: .agents/rules/GAP_probe_v7_validator_rules.md`.
- The v8 manifest and README bind the prior GAP dynamic rule receipt and do not
  contain `CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`.
- v8 bytes and sidecar were left unchanged. Its release state is
  `QUARANTINED_POST_GENERATION_RULE_DRIFT`; it must not be run.

## FIRST_DIVERGENCE

```text
V8_FINAL_MANIFEST_RULE_RECEIPT
  -> GAP dynamic SHA is stale
  -> new dual-operand ingress rule ID is absent
  -> final ZIP current-match gate fails closed
```

This is a package receipt/identity boundary defect, not a numeric, config,
golden, observer-algorithm, or functional-RTL defect.

## V8_TO_V9_AUTHORIZED_DELTA

Fresh identity: `r5_n71_gap_v9_ingress_rule`.

Exactly five relative paths differ from frozen v8:

1. `PREPARE_AND_RUN.sh`
2. `README.md`
3. `TEST_PACKAGE_MANIFEST.json`
4. `workload/sca_cfg.json`
5. `workload/sca_cfg_D.json`

Independent byte comparison proved:

- exact relative file set: PASS
- exact changed-path allowlist: PASS
- 73 frozen numeric workload files: byte-identical
- 120 immutable payload files: byte-identical
- observer source: byte-identical, SHA-256
  `0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8`
- identity/SCA namespace rewrite: exact
- current GAP rule SHA, new rule ID, and publication record receipt: present
- negative controls for deleted new rule ID, restored old SHA, observer
  mutation, and numeric mutation: all fail closed

No GAP sum/tail numeric analysis was repeated. No config, golden, timeout,
observer algorithm, workload semantics, or functional RTL was changed.

## BLOCKER_DELTA

- Closed: v8 post-generation current-rule receipt drift.
- Closed for v9 delivery: current GAP dynamic rule and
  `CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001` are package-bound and
  independently validated.
- Still open: the dynamic GAP hang/root-cause boundary that v9 is intended to
  localize. v9 is diagnostic only and does not claim a functional fix.
- Still open: all E3/E4/E5 claims until a formal return passes the full
  compile/run/natural-terminal/formal-D conjunction.

## RULE_DELTA_PROPOSAL

None. The newly published rule is consumed as-is. This task did not modify the
index, public rules, plan, or RTL.

## PACKAGE_RELEASE

```text
identity=r5_n71_gap_v9_ingress_rule
claim=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
status=PACKAGE_READY_NOT_RUN
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
```

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v9_ingress_rule.zip`
- bytes: `1791899`
- SHA-256:
  `d37f40e768001d3588cd22f25040ba4e229ffc138221a42b13d7e446436e644c`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v9_ingress_rule.zip.sha256`
- sidecar file SHA-256:
  `b5d324affd00305ed822f2c5bb5facab3946a74e26c54dbd7910604cc9a760a0`
- single server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  - `r5_n71_gap_v9_ingress_rule_return.zip`
  - `r5_n71_gap_v9_ingress_rule_return.zip.sha256`

The final ZIP audit directly verified ZIP CRC, exact-set, sidecar, current rule
receipts, applicable rule IDs, runtime-D absence, one-command boundary,
return allowlist, fresh-extract preflight immutability, runner syntax,
canonical decision rules, observer four-way binding, dual-ingress qualified
localization, and the v8-to-v9 authorized-delta boundary.

## COMMAND_RECEIPTS

All listed harnesses exited `0`; their internal negative cases fail closed.

- canonical validator: exit `0`, stdout SHA-256
  `2f1c707542de198b341de3f48559750549df6c05b40b0e023deb67b716e35275`
- observer four-way validator: exit `0`, stdout SHA-256
  `142899e49982094ac861389ff510976ad7d794c0581643c9af2f8db18328a250`
- dual-ingress validator: exit `0`, stdout SHA-256
  `989e557f56ff3db932473b1598f3911d69523016fbe9d1b19beea04547dd5642`
- v8-to-v9 rule-refresh validator: exit `0`, stdout SHA-256
  `8a39861f965b686a749698fb5c6078f20c1f837a0adf160881f1bf1b2b6ab482`
- fresh-extract package preflight: exit `0`, stdout SHA-256
  `306260f4f897a8b351f52bd86dd843b141f157d941da65db59a190b020740428`
- fresh-extract canonical self-test: exit `0`, stdout SHA-256
  `967a9690abd7b130352ea15e211f8368e8a0cc4b0f1bd852867bda59742b7f85`
- fresh-extract runner `bash -n`: exit `0`

Reports and tools:

- build validation report SHA-256:
  `3ff672399e78a7d4365bbe17211340892d901d03aa4ce75acd40c9030eca1343`
- final ZIP rule self-audit report SHA-256:
  `8c5c74bce82e63e529f23ca989cf3455891b9918d7b802a8ddb915b37dbf2af2`
- builder SHA-256:
  `0dbd4dcb9d8662c96b8c83e38234af1e608f36c188575c825f239acb53b3059f`
- rule-refresh validator SHA-256:
  `cbc27e73b068aecb4d00f1e6e700761af9a6128dba1a9aaf099e8a58e015727c`
- final auditor SHA-256:
  `0ec3e7c86b26c3185f64dda2c80d55d5fb3e4bf845e3ab8dd8c211ce13f76b9e`

## RULE_RECEIPTS

- generation index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- server package rules:
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- GAP int32 rules:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- GAP dynamic rules:
  `4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf`
- exact UINT8 tail rules:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- publication record:
  `b8f4519c4cd98aec22498b250269e884e69bd893a52db71cd486424651f801c6`
- plan mutable provenance only:
  `9a5d9de4b48508fd19d6800c905abb865a03da7a1745eb5301e2ae4dc63244c9`

No upload, server run/inspection, lease, public-rule edit, plan edit, or
functional-RTL edit occurred.
