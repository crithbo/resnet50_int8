# GAP dual-operand ingress observability rule publication

## Trigger

The formal node0071 v7 return proved a long-running dynamic stall after one
producer path had reached Buffer0 while joint GA input acceptance remained
zero. The return did not observe the second producer path or per-operand
capture/tag matching, so configuration-versus-RTL responsibility could not be
assigned safely.

Accepted evidence:

- return ZIP SHA-256:
  `f7ebfd83d56edb189471f617c7f85df89dda0d035038529397e451cd7e7a5d1b`
- machine report:
  `artifacts/operator_config_validation/r5-gap-node0071-v7-return-analysis/report.json`
- machine report SHA-256:
  `b6cdb8f4734c1689dc2f144fe85a8a229496a8d0316bb1615887c9422390b327`
- task record:
  `.agents/task_records/20260731_gap_node0071_v7_return_analysis_and_v8_dual_ingress.md`
- task record SHA-256:
  `4fbb6b3f3c289283663c579f0e31b102a393058b1636bf0800e81dd1b049e1eb`

## Published rule

File:
`.agents/rules/GAP_probe_v7_validator_rules.md`

Previous SHA-256:
`2dee42a883bde9c1650710c8312d23e661aeb3c66ef9d1d4e15524af79c33dc7`

Current SHA-256:
`4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf`

New rule ID:
`CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`

The rule requires separate qualified evidence for both producer-to-buffer
paths, each enabled operand's capture/tag matching, and joint GA acceptance.
Raw ready/valid/occupancy levels cannot substitute for transactions. If every
formal D is missing, `mismatch=0` must be recorded as unevaluable.

## Package consequence

`r5_n71_gap_v8_dual_ingress.zip` was built and self-audited before this public
rule publication. Its bytes remain unchanged, but its previous final-ZIP audit
is no longer current-match. It is quarantined pending review by the GAP owner.
If the final manifest must change to bind the new rule receipt, the old ZIP
must remain isolated and a fresh identity must be built and independently
self-audited. No package-external receipt patch is allowed.

No numeric workload, golden, configuration, functional RTL, or server state
was changed by this publication.
