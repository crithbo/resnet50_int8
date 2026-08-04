# Conv v25 and QAdd v20 formal-return dispatch receipt

Date: 2026-08-03

Mainline / completion-notification target:
`019fbec2-fe93-7e03-9314-cff6f222f33d`

Applicable completion rule:
`CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`

## Conv node0004 v25

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v25_terminal_match_diag_return.zip`
- Return bytes: `96603`
- Return SHA256:
  `e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f`
- Adjacent return sidecar: absent; user-attested transport exception applies
  only to the external sidecar.
- Frozen source ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v25_terminal_match_diag.zip`
- Source bytes: `5829810`
- Source SHA256:
  `e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab`
- Dispatch status: sent to the persistent Conv/SA owner.

The owner must complete receipt-only RETURN analysis and continuous successor
closure, then proactively notify this mainline with an evidence-backed
`RULE_DELTA_PROPOSAL` or `RULE_CONFIRMATION`.

## QLinearAdd node0007 v20

- Owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- Return:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_fp32_ingress_compilefix_v20_return.zip`
- Return bytes: `179242`
- Return SHA256:
  `fd874e7d0f2ded42a31288bfa273c9fe32323c15455d256fb2cb01e66d0563d7`
- Frozen source ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_fp32_ingress_compilefix_v20.zip`
- Source bytes: `38041268`
- Source SHA256:
  `13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`
- Dispatch status: owner analysis already active.

The user-approved A/B/C/D segmented diagnostic is localization-only. It may
use hardware-produced checkpoint/restart, or compile-once plus target-stage
early-stop when reliable checkpoint support is absent. Host precomputation of
internal scratch is forbidden, and final six-stage plus 28-D end-to-end E4/E5
remains required.

The owner was explicitly refreshed to the current completion-notification rule
and must proactively notify this mainline after RETURN-to-successor closure.

No package upload, server execution, lease, public-rule change or functional
RTL modification was performed by this dispatch.
