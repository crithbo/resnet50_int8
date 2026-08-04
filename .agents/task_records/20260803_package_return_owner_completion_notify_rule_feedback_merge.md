# Package/return owner completion notification and rule-feedback merge

Date: 2026-08-03

Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## User clarification

The completion notification requirement applies both when a branch finishes a
local server test package and when it finishes formal return analysis and
successor closure.

## Adjudication

The immediately preceding rule covered only formal-return owner completion.
Adding a second package-only rule would be synonymous and could let the two
notification contracts drift. The public rule was therefore broadened and
renamed in place to:

`CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`

## Required package completion receipt

At `PACKAGE_READY_NOT_RUN` or an explicit terminal state, the package owner
must proactively notify the mainline bound in the dispatch and provide:

- `PACKAGE_RELEASE` or explicit terminal state;
- ZIP and sidecar path, bytes and SHA256;
- unique server command and expected return identity;
- final-ZIP self-audit and negative-control result;
- `BLOCKER_DELTA`;
- evidence-backed `RULE_DELTA_PROPOSAL` or `RULE_CONFIRMATION`.

Formal-return completion retains the full RETURN analysis, LPG/FD/root-cause,
successor and rule-feedback requirements.

No functional RTL, package bytes, frozen return, server state, upload, run or
lease was modified.

## Current public identities

- `.agents/agent.md`
  - bytes: `12886`
  - SHA256:
    `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/rules/生成前必读索引.md`
  - bytes: `8849`
  - SHA256:
    `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- `.agents/rules/服务器测试包生成规则.md`
  - bytes: `54939`
  - SHA256:
    `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`

## Validation

- Broad rule definition count: one.
- Superseded return-only rule definition count in current rules: zero.
- Package-generation and return-analysis routes both require notification.
- Package and return completion stop gates require evidence-backed rule
  feedback.
- Scoped `git diff --check`: pass.
