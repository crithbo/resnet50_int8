# Conv node0004 v25 return → v26 transout threshold fix

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- unique mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- successor classification:
  `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`
- successor status: `PACKAGE_READY_NOT_RUN`
- numeric analysis repeated: `false`
- node0004 workload rebuilt: `false`
- configuration rebuilt: `true` (one authorized leaf)
- functional RTL modified: `false`
- server action: `false`

## Current receipts

- agent:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- plan:
  `ea465e54afb96968fdcb5c8d373f585ad94747a00a95796bbe860ddbc0246cb6`
  (mutable provenance)
- index:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- server rule:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- INT8-SA:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- hardware README:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## Formal v25 return

Return ZIP:
`r5_n4_hw_v25_terminal_match_diag_return.zip`, bytes `96603`, SHA-256
`e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f`.
The missing adjacent sidecar is content-neutral under the user-attested
transport rule.

CRC, root/path safety, duplicate/symlink checks, RETURN_MANIFEST exact set,
allowlist receipts, frozen source-package binding, package/install/observer
preflights, compile/runtime argv and four feature receipts all pass. VCS
compile/elaboration and runner return zero; simulation starts and reaches the
diagnostic finish, but not the DUT natural terminal. Formal D is
`expected=320, present=0, missing=320, mismatch=0`; E3/E4/E5 and the joint
result gate remain false.

## Deterministic root cause

All 256 returned terminal records are qualified A/B accepts:

- raw and masked valid are `0x3`;
- masked last is `0x3`;
- `all_matched=1`;
- `pipeline_enable=1`;
- accepted last index 5 occurs 192 times;
- accepted last index 4 occurs 64 times.

The final materialized `special_array.transout_last_index` is 2. Active
`SA_PE_Control_Block.sv:161-167` computes:

```text
diff = accepted_last_index - transout_last_index
ignore = last && !diff[4] && |diff[3:0]
matched = last && !|diff
out = last && diff[4]
release = matched || out
```

Thus indices 4 and 5 produce positive diffs 2 and 3. All 256 terminals are
`ignore=1`, and none can set matched/out, terminal ALU tag, PE output or
Buffer5 write. This exactly matches the dynamic summary:
`terminal_ignore=256`, `terminal_equal=0`, `terminal_out=0`.

`LAST_PROVEN_GOOD` is
`QUALIFIED_A_B_TERMINAL_ACCEPT_WITH_ALL_OPERANDS_MATCHED`.
`FIRST_DIVERGENCE` is
`ACCEPTED_TERMINAL_INDEX_TO_TRANSOUT_THRESHOLD_CLASSIFICATION`.
The old outbuffer occupancy theory remains `INVALIDATED_NOT_RTL_BUG`.

## Fresh local rebuild

The only logical change is:

```text
special_array.transout_last_index: 2 -> 5
```

The owner formula is `max(accepted A/B terminal last_index)`. With threshold
5, index 5 is matched and index 4 is out; all 256 accepted terminals satisfy
the release predicate. The mapper changes the encoding from `0010` to `0101`.
The bitstream changes exactly byte offsets `4459, 4460, 4461`; execplan and
SCA hashes remain unchanged. All 84 matrix members are byte-identical.

Local rebuild report:
`artifacts/operator_config_validation/r5-node0004-transout-threshold-fix-c0-v5/local_rebuild_report.json`,
bytes `4282`, SHA-256
`abd6675a413d9729eb0fd4898a437b31a76de5bd5dbad415b851304b5ac37647`.

## v26 package release

- identity: `r5_n4_hw_v26_transout_threshold_fix`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v26_transout_threshold_fix.zip`
- bytes: `5830794`
- SHA-256:
  `94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb`
- sidecar bytes: `106`
- sidecar file SHA-256:
  `4118f7bbc45aa0bca3131c9d69cea550a50f00c7431f040927fa459592b50c50`
- command:
  `bash r5_n4_hw_v26_transout_threshold_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v26_transout_threshold_fix_return.zip`

Deterministic double build passes. Focused package-local observer frontend
exits 0 and all declaration/use/update negatives fail closed. Safe compile
runner control returns 74, TERM finalizer returns 143, and the runner validator
returns 0. Final ZIP current-rule self-audit returns 0 with `errors=0`; all
config, bitstream, include/macro/runtime, observer-identity and return-contract
negatives fail closed. Targeted unit tests are `3/3 PASS`.

## Blocker delta

- closed by v25 evidence:
  `B_CONV_NODE0004_RAW_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_UNOBSERVED`
- identified and locally fixed:
  `B_CONV_NODE0004_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL`
- open until v26 dynamic return:
  `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`,
  `B_CONV_NODE0004_FORMAL_D_320`
- invalidated and not reopened:
  `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

## Rule confirmation

No synonymous delta is proposed. This return and successor provide direct
confirmation of:

- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`: compile/run success
  plus simulation start did not convert the diagnostic finish into success;
  the analysis continued to a deterministic config root cause.
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`: all-missing D with mismatch 0
  remained fail-closed.
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`: the same owner
  built the fresh one-leaf fix instead of stopping proposal-only.
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`: exact
  v26 focused syntax/scope and required negatives pass without claiming local
  full-design elaboration.
- `CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001`:
  the final structured completion notification contains return, LPG/FD/root
  cause, blocker delta, package identity and this evidence-backed confirmation.

Claim boundary: this confirms the local return-to-successor workflow and
package gates. It does not claim v26 server VCS, natural terminal, formal D,
E3, E4 or E5.

## Machine assets

- return report:
  `outputs/conv_node0004_v25_return_analysis/report.json`, bytes `15583`,
  SHA-256 `75a8e0a798b02b566247fa7bf52b19bf12ca3a284854347eb7290b6e051fd6e0`
- observer scope:
  `outputs/conv_node0004_v25_return_analysis/v26_observer_scope.json`, bytes
  `7776`, SHA-256
  `5b0db9d43356985cb95ecd123c92e0a4d46b62f92914b8193ab59a5c34674383`
- runner controls:
  `outputs/conv_node0004_v25_return_analysis/v26_runner_controls.json`, bytes
  `7768`, SHA-256
  `250c3122ec30d2432f820d12ffa8a2a5c60a6aca859cf5d6da3b4dc32bc3930c`
- final ZIP audit:
  `outputs/conv_node0004_v25_return_analysis/v26_final_zip_self_audit.json`,
  bytes `6300`, SHA-256
  `22e9cee015da907b3c6e36a4565ae7f786e4fb0fc66a0a427baaf0382a267f1c`
- structured release:
  `outputs/conv_node0004_v25_return_analysis/successor_release.json`, bytes
  `10767`, SHA-256
  `42189ce6a2f17a3e16b419d7f5a2d5181e7ea8002d369f3f256e96ddf56b0651`

