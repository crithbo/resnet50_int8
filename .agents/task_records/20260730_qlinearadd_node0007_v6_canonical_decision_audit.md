# QLinearAdd node0007 v6 canonical-decision receipt audit

## Scope

This is a receipt-only audit of the immutable final v6 ZIP under
`CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`. It does not repeat the
17-instance analysis, W3 arithmetic, frozen workload, golden, mapping,
bitstream, execplan or SCA analysis. It performs no server action.

## v6 adjudication

The final ZIP
`r5_qadd_n7_nested_lc_progress_bind_v6.zip`, SHA-256
`9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90`,
retains its previously validated four-way observer binding. It does not
contain a canonical decision parser, a unique complete canonical record
contract, or a required canonical record in the return allowlist. It also
lacks release negative controls for sustained-high raw state, summary-only
append, conflicting decisions and missing reason/boundary.

Therefore v6 is not runnable under the current rule and is classified
`QUARANTINED_NOT_RUN_CANONICAL_DECISION_MISSING`. Its ZIP and sidecar remain
unchanged.

## Authorized successor

The only authorized successor change is a package-local canonical decision
parser and its runtime/return binding. The observer source, package-local
include, enable macro, timeout, workload, six qparams, W3 order, golden and
all hardware configuration assets remain unchanged except the fresh install
namespace. The successor remains
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

## Rule drift and fresh identity

The first successor,
`r5_qadd_n7_progress_canon_v7.zip`, SHA-256
`1ed2ed3cb1015e62b585a77dbff0b82b45e592a27695ddd9331b47eb1196df1f`,
was deterministically built but then an active server-package rule changed.
Because its manifest lacked the newly required post-build final-ZIP audit
contract, it is isolated as
`QUARANTINED_NOT_RUN_ACTIVE_RULE_DRIFT_AFTER_BUILD`. It was not run.

The fresh successor is:

```text
artifacts/operator_config_validation/r5-server-test-packages/
  r5_qadd_n7_progress_canon_v8.zip
SHA-256=b74b18f906fbf32851ce016906c599889236e7088ad7209607e52368bad69100
status=PACKAGE_READY_NOT_RUN
claim=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX
```

It differs from v7 only by its fresh install namespace and the manifest
contract for `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`. The final validator
proved workload equivalence across 99 runtime files after namespace
normalization.

## Post-build current rule receipts

```text
.agents/rules/生成前必读索引.md
  SHA-256=12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f
.agents/rules/服务器测试包生成规则.md
  SHA-256=7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa
.agents/rules/QLinearAdd算子配置规则.md
  SHA-256=fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba
```

All three were completely reread after v8 generation. Their immutable
receipts remain current-match. The plan is mutable provenance only.

## Independent final-ZIP audit

Working directory:
`C:\Users\15383\Desktop\Codex\project\resnet50_int8`

Validator command and exit:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\
dependencies\python\python.exe
  tools/validate_qlinearadd_node0007_progress_canonical_v8.py
exit=0
```

Directed tests and negative controls:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\
dependencies\python\python.exe -m unittest
  tests.test_qlinearadd_progress_canonical_decision
  tests.test_qlinearadd_node0007_progress_canonical_v8 -v
exit=0
tests=8/8 PASS
```

The validator directly read final ZIP, sidecar, manifest, runner, embedded
runtime/parser, allowlist and observer. It also ran the embedded runtime
preflight from a fresh extraction with `PYTHONDONTWRITEBYTECODE=1`; exit was
0 and the package tree was byte-identical before/after.

Negative controls all failed closed:

```text
observer source removed
package +incdir removed
observer enable macro removed
runtime/return binding removed
sustained-high raw level with no qualified-event growth
summary-only append after a complete decision
two conflicting canonical decisions
missing reason
missing boundary
```

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-progress-canonical-v8/report.json`

Report SHA-256:
`be25c468e605af0c1861ce50f99e692506499db5e4cd2dee1d1f653676335003`

Final adjudication:

```text
FINAL_ZIP_RULE_SELF_AUDIT_PASS=true
errors=0
all_required_negative_controls_fail_closed=true
CANONICAL_DECISION_RULE_VALIDATED
```
