# Formal return analysis-to-successor closure and rule-audit escalation

Date: 2026-08-14  
Role: `mainline.control`  
Owner epoch: `2`  
Registry epoch consumed: `6`

## User decision

Formal returns are no longer dispatched as analysis-only terminal work. For the current four TB-VCD returns and all later returns, the owning family must complete analysis and then either:

- correct a package-local runner/TB/observer/parser/return/gate defect and publish a fresh validated package;
- build the highest-information-gain fresh diagnostic successor when the target remains open;
- or return an explicit `CLOSED`, `WAIT_RTL_FIX`, `HARDWARE_CAPABILITY_BLOCKED` or `WAIT_USER_DECISION` terminal when a package-only successor is meaningless or unauthorized.

No upload, lease, connection, server run or functional RTL change is authorized by this decision.

## Mandatory escalation

`RULE_GAP_AUDIT_REQUIRED` applies when production compile passes, simulation and the target causal interval execute, and the return is consumable, yet the run does not uniquely localize the root cause. Before releasing the successor, the owner must audit the causal catalog, four-layer boundary, candidate matrix, actual-source identity, trigger/stop/global-progress logic, return exact-set, parser/streaming analysis and positive/negative controls. The audit must produce evidence-backed `RULE_CONFIRMATION` with implementation controls or a non-synonymous `RULE_DELTA_PROPOSAL`; the successor must bind the adjudicated correction.

`PACKAGE_BUILD_FAILURE_RULE_AUDIT_REQUIRED` applies before a third attempt when the same target has two consecutive failed fresh build/final-gate attempts, or two consecutive server attempts fail to exercise the target because of package-local defects. Renaming the package does not reset the chain. The audit must aggregate both failures and examine generators, schemas, validators, definition-before-use, identities, compile core, partial return and negative controls.

## Current exact dispatches

- GAP: `C:/Users/15383/Downloads/r5_n71_gap_v62_sum_s2_tbvcd_r1786698149152170252_2255343_return.zip`
- Serialized Conv: `C:/Users/15383/Downloads/r5_n4_hw_v92b_tbvcdcone_r1786698125871137122_2252228_return.zip`
- Native Conv: `C:/Users/15383/Downloads/r5_n4_0cc_p47_tbvcdcone_r1786698137747571521_2253824_return.zip`
- QLinearAdd: `C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v63_tbvcd_r1786698111383862725_2250595_return.zip`

All four persistent family owners received the superseding instruction. They must stream large evidence into `analysis_state.json`, append-only `checkpoints.jsonl` and incremental `report.md`, then proactively return `RETURN_ANALYSIS`, audit disposition when triggered, and `PACKAGE_READY_NOT_RUN` or an explicit terminal state.

## Claim boundary

This record changes local analysis/build/rule-audit workflow only. It makes no claim about the four returns' integrity, production result, root cause, natural terminal, formal D, E3, E4 or E5; those remain family-owned analysis outcomes.
