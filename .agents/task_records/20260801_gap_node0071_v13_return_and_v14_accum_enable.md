# GAP node0071 v13 return and v14 accumulator-enable successor

Date: 2026-08-01

Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

The received v13 return ZIP is:

`C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-08\r5_n71_gap_v13_buffer_to_ga_diag_return.zip`

- bytes: `124050`
- analysis-side SHA256:
  `69e8fb4f318d649740ecf111e9ce57664e80eec9c1247e8663f17d663aef7816`
- adjacent sidecar: absent
- transport receipt:
  `USER_ATTESTED_NO_SIDECAR_ACCEPTED`

Per current rule
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`, the explicit
user transport guarantee replaces only the external adjacent sidecar. Missing
sidecar is content-neutral and is not a blocker. It does not replace any
internal/source/dynamic gate.

The return ZIP passes CRC, path safety, single-root, duplicate and budget
checks. All 23 entries exactly match `RETURN_MANIFEST.json`; there are no
unlisted, missing, size or SHA mismatches. The returned
`PACKAGE_MANIFEST.json` is byte-identical to source v13:

- source:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v13_buffer_to_ga_diag.zip`
- source SHA256:
  `88715902dd818b488990521bcdfa9d9be24f3195e0371c9c25a664a17fc76131`
- manifest SHA256:
  `8404fa18aceb8440b093152b7ec0fd79f124e86f6fff6356433c6da3e4307315`

Package/install/observer preflight pass and runtime formal-D targets were
initially absent. Compile exits 0. Simulation and runner exit 125 under INT;
there is no natural terminal. All 48 formal D files are missing.
`mismatch=0` is unevaluable. The conjunction fails, therefore E3/E4/E5 are
all false.

The canonical decision is
`LONG_RUNNING_HANG_AT_ANY_MSE_READ_DATA_ACCEPTED`. Simulation reaches
`187480279000 ps`, active cycle `149422080`, and remains flat for
`149159936` qualified cycles against a `1048576` cycle stall window.

## FIRST_DIVERGENCE

`BUFFER_TO_GA_DIAGNOSTIC_RUNTIME_ENABLE_ABSENT`

The v13 observer source gates all newly added Buffer-to-GA counters, including
the `clk_sg` edge witness, with `return_obs_accum_state_enabled`. The real
simulator argv does not contain `+RETURN_OBS_ACCUM_STATE`. The observer time-0
header proves `accum_state=0`.

Consequently the returned zeros for:

- `sg_edges`
- Buffer0/4 ARM accept
- GA group0/2 ingress accept

are disabled-instrumentation zeros, not zero-transaction evidence. The generic
`observer_enabled_and_returned=true` marker is insufficient for this optional
feature.

The previous qualified facts remain valid:

```text
MSE0 -> Buffer0 accepted once
MSE3 -> Buffer4 accepted once
GA operand0 capture = 0
GA operand2 capture = 0
GA joint accept = 0
```

The raw last snapshot (`buf_rtag=0`, `buf_bp=3`, nonzero group tag,
`group_bp=3`, PE operand valid=0) is state only and cannot establish an
accepted transaction.

## HANG_ROOT_CAUSE

Functional hang root cause remains:
`UNRESOLVED_FUNCTIONAL_HANG_AFTER_PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE`.

The deterministic package root cause is closed: v13 did not enable its
already-packaged narrow probe. This occurs before the intended Buffer-to-GA
transactional discrimination, so no config/RTL cause may be inferred from the
disabled counter values.

The remaining narrow boundary is:

`BUFFER0_4_ARM_READ_ACCEPT_TO_GA_GROUP0_2_INGRESS_ACCEPT_TO_PE_OPERAND_TAG_VISIBILITY`.

The prior local topology/ready-valid RTL audit is consumed and not repeated.
No GAP sum/tail numeric analysis, workload, config semantics or golden was
rerun.

## BLOCKER_DELTA

Closed:

- `DIRECT_ADJACENT_RETURN_SIDECAR_ABSENT`

New and closed by successor:

- `V13_BUFFER_TO_GA_DIAGNOSTIC_RUNTIME_ENABLE_ABSENT`

Open:

- Buffer0/4 ARM read to GA group0/2 ingress to PE operand visibility
- natural terminal absent
- formal D `48/48` missing
- server source identity unbound for E4/E5

v13 is quarantined and must not be rerun.

## RULE_DELTA_PROPOSAL

Proposal only:
`CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`.

Every optional diagnostic feature with a dedicated runtime gate should bind:
the real simulator argv, a time-0 feature-enabled marker, a returned
feature-specific binding receipt, and negative controls removing each
enable/limit. Generic observer enable evidence must not substitute for a
feature-specific gate.

No public rule was edited by this family task.

## PACKAGE_RELEASE

Fresh successor:

- identity: `r5_n71_gap_v14_accum_enable`
- claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- status: `PACKAGE_READY_NOT_RUN`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v14_accum_enable.zip`
- bytes: `1795598`
- ZIP SHA256:
  `98ef0a67d09f6790c2dfa8fb7445b6535ae605fc92c9455e5513b21210f5271b`
- sidecar SHA256:
  `d3f8613251092365db5f919d552432716129c1f99ee74e1a7b21068399b378d7`
- final self-audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v14_accum_enable.final_zip_rule_self_audit.json`
- self-audit SHA256:
  `cb5fe5facf5c7672173c0173c9918630a23d2d45409e3de9c1fb989c9f0ff53b`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- errors: `0`

The fix is runner-only activation:

```text
+RETURN_OBS_ACCUM_STATE
+RETURN_OBS_ACCUM_LIMIT=512
```

and a fail-closed returned marker
`buffer_to_ga_accum_state_enabled=true`. Observer source SHA remains
`c6ae0bbd7f2cbe40c5ba47608b8ffb2c4123f58c5ce7ebe9e92f3dce8fb87c59`,
byte-identical to v13. All 73 frozen numeric files are byte-identical.
Configuration semantics and golden are unchanged; only the fresh SCA
namespace changes.

All final-ZIP validators and negative controls exit 0 at the audit layer.
The real-runner safe compile-stub positive control reaches make and exits 86;
wrong identity exits 5 before compile. Runtime-D absent, manifest exact-set,
bootstrap immutability, observer four-way, gated-domain witness, canonical
decision, return allowlist and new accumulator enable controls all pass.

Server command:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return ZIP:
`r5_n71_gap_v14_accum_enable_return.zip`. The runner still generates its
server-local sidecar, but under the user-attested policy the user need not
return it.

Machine report:
`artifacts/operator_config_validation/r5-gap-node0071-v13-return-analysis/report.json`.

Current rule receipts:

- index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- common operator:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- NDP fields:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server:
  `88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6`
- GAP int32:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- GAP dynamic:
  `4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf`
- exact tail:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- plan mutable provenance:
  `23087aee1f7dadd123eebca24d802bd2444f2b26b442cc6a77c764bf85d930f9`

