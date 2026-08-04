# Return owner completion notification and rule-feedback merge

Date: 2026-08-03

Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## User requirement

- Server package execution does not require continuous mainline monitoring.
- Every return dispatch must require the family owner to notify the current
  mainline proactively after completing RETURN analysis and successor closure.
- Every completion must use the observed failure or success experience to
  propose a corresponding rule change or confirm that the current rule is
  sufficient.

## Gap adjudication

The current control plane already required automatic RETURN-to-successor
closure and included `RULE_DELTA_PROPOSAL` in the structured return. It did not
explicitly require an active completion notification to the current mainline,
and it did not require evidence when the owner reported
`RULE_DELTA_PROPOSAL=NONE`.

This is not synonymous with the existing continuous-closure rule. Continuous
closure governs what work the owner must complete; the new rule governs the
completion receipt, target notification, and rule-learning feedback.

## Public rule change

Added rule:

`CDA-SERVER-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`

The rule establishes:

1. no continuous mainline/owner polling requirement while a package runs;
2. every return dispatch binds the current mainline thread ID;
3. the owner must proactively notify that mainline after completion;
4. the completion notification contains the full structured RETURN/successor
   result;
5. rule feedback is either an evidence-backed `RULE_DELTA_PROPOSAL` or an
   evidence-backed `RULE_CONFIRMATION`;
6. family owners do not modify public plan/rules; mainline adjudicates changes,
   confirmations, duplicates, and over-strict proposals.

## Files changed

- `.agents/agent.md`
- `.agents/rules/生成前必读索引.md`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/plan.md`
- `.agents/history.md`
- this task record

No functional RTL, operator package, frozen return, server state, upload, run,
or lease was modified.

## Current public identities

- `.agents/agent.md`
  - bytes: `12383`
  - SHA256:
    `1f2471722bb4999faba2b07dae59dec42a3704e8ca219573870e02e4cae72b64`
- `.agents/rules/生成前必读索引.md`
  - bytes: `8636`
  - SHA256:
    `3758b2c271b4fce152afcf79e7a0d916b3b35c00e56b113bb719f4c64edaca5e`
- `.agents/rules/服务器测试包生成规则.md`
  - bytes: `54607`
  - SHA256:
    `0ccb358222e0f6e481e92086fb2df8578cea4d8f2963c72d631b8c52b2f67c99`

## Validation

- Full current agent/index/server/common-operator rule reread: complete.
- New rule ID exact-count check: one definition.
- Routing and stop-gate search: pass.
- Scoped `git diff --check`: pass.
- Functional RTL/package/server mutations: none.
