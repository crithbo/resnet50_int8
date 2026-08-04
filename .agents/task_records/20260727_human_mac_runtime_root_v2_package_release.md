# Human MAC runtime-root-v2 package adaptation

## RETURN_ANALYSIS

This round adapted the frozen human-MAC fd2 package to the user-authorized
`CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001` profile. No operator JSON,
mapping, bitstream, execplan, SCA/SCA_D, input, or golden semantics changed. No server
upload or execution occurred because the server lease is `NONE`.

The new runner:

- accepts exactly one absolute, resolvable, enterable server-root directory;
- does not constrain the root basename;
- performs no fixed server-file preflight;
- performs no server RTL/build/TB/support/Git/README/tree scan or identity gate;
- lets the mechanically inherited compile command fail naturally and returns a bounded
  compile log;
- uses a fresh contained runtime namespace;
- has no observer and touches zero server-source targets;
- records restore as `NOT_REQUIRED`;
- emits an allowlist-only return ZIP and SHA256 sidecar from normal exit or
  `HUP/INT/TERM/EXIT` finalization.

All outcomes are fixed to:

```text
result_profile=VERSION_UNBOUND_DIAGNOSTIC_ONLY
candidate_release=false
counts_as_E4=false
counts_as_E5=false
```

## Read receipt

| Path | SHA256 |
|---|---|
| `.agents/agent.md` | `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0` |
| `.agents/plan.md` | `581ee5b55d2d5b1df36d8cfc2937e3a3822c1108c835cbd8669c9d80820d22fe` |
| `.agents/rules/生成前必读索引.md` | `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7` |
| `.agents/rules/算子配置规则.md` | `f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023` |
| `.agents/rules/NDP硬件字段语义.md` | `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59` |
| `.agents/rules/GAP_int32_mac_bypass_rules.md` | `f53fecb9106705d113354b4ab81356cbdc8179e602b2f7e584390bafe57e67a8` |
| `.agents/rules/服务器测试包生成规则.md` | `72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524` |

The superseded server-rule receipt is absent from the final package.

## Audit correction

During the initial routing read, the task mistakenly read
`NDP_copy01/README_HARDWARE_SIM_ENTRY.md`. This was a read-only process deviation.
No further `NDP_copy*` access occurred.

Non-derivation was established as follows:

1. The adapter consumes the frozen fd2 ZIP, current public rules, and human-MAC family
   local builder/validator/tests only.
2. The compile and simulation command fragments in the adapted runner are mechanically
   extracted from the frozen fd2 package-local runner and match those source fragments
   byte-for-byte.
3. The final source/package audit found no fixed `NDP_copy01/02/03` name, local server
   path, accidental README filename/SHA, server-source scan command, Git query, or
   superseded rule hash.
4. All `workload/**` and `provenance/**` members match the frozen fd2 ZIP byte-for-byte.
5. An arbitrary-basename empty root reached the real compile path without server-file
   preflight; a controlled `make` exit 47 produced a version-unbound diagnostic return,
   restore receipt, ZIP, and matching sidecar.

The first candidate self-check failed due to checker defects (a Unicode path comparison
and five forbidden literals in the validator). A later check completed the substantive
tests but failed while Windows removed its temporary directory. Both failed candidate
directories are excluded from release. The final candidate was rebuilt twice in new
directories and passed its complete post-formation check.

## PACKAGE_RELEASE

- Identity: `human_mac_int32_uint8_v3_runtime_root_v2`
- Source fd2 ZIP SHA256:
  `5bcc26c80a995063b6b8c071eea4962426dd0547d782df771c61cf1fa3024e52`
- Final ZIP:
  `artifacts/human_mac_int32_uint8_20260727_v1/runtime_root_v2_final/human_mac_int32_uint8_v3_runtime_root_v2.zip`
- ZIP bytes: `144024`
- ZIP SHA256:
  `af9a1acdd79db6e3889b0ae86aab65ccd0c0386ab053e1d21a3736e99c02a229`
- Manifest SHA256:
  `83b9db8cd3e5820dfc15859d101af558332342aa6173b9f364a7a8a327843c23`
- Sidecar:
  `artifacts/human_mac_int32_uint8_20260727_v1/runtime_root_v2_final/human_mac_int32_uint8_v3_runtime_root_v2.zip.sha256`
- Unique command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/server_root`
- Expected return:
  `human_mac_int32_uint8_v3_runtime_root_v2_return.zip` and `.sha256`
- Package RTL entries: `0`
- Observer: absent

Two fresh final builds produced identical ZIP bytes and SHA256. The complete final check
passed all 23 checks; report:
`artifacts/human_mac_int32_uint8_20260727_v1/runtime_root_v2_final/final_self_check.json`,
SHA256 `ffa4e2bfc79f66b374d956e7d501a0b0552ddf5bd38795daa5c3aa88a69d6ae4`.

## BLOCKER_DELTA

- Package compatibility blocker: closed locally for the variable-root diagnostic profile.
- Server execution: still blocked by `server_lease=NONE`.
- Hardware conclusion: unchanged. A future result remains version-unbound diagnostic
  evidence and cannot close E4/E5 or establish stock-RTL identity.

## RULE_DELTA_PROPOSAL

`NONE_NEW`. The package implements the current public rule
`CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`; no public-rule edit is requested.
