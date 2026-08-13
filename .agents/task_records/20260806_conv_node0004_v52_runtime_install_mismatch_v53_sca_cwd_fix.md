# Conv node0004 v52 runtime install mismatch and v53 runner-only fix

Date: 2026-08-06  
Owner/provenance: `019fa2c1-17df-7122-bcbd-a727aaf173f5`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Return analysis

The user-supplied server log is
`C:/Users/15383/.codex/attachments/458fc0a4-2ac0-44f5-bdb1-c36e91297f0f/pasted-text.txt`
(49,838 bytes, SHA256
`e2dc1750df9e2e933b6c86050d0ad152e9f84c789f62e5a8f892eaf1e54ff9a9`).

At 7,794,000 ps the TB, whose cwd is `/home/panqs/ndp/NDP_copy01`,
attempted to open SCA inputs below
`install/cfg_pkg/r5_n4_hw_v52_ndproot_gate/...`. The frozen v52 runner had
instead installed the payload under
`/home/panqs/ndp/simresult/.r5_n4_hw_v52_ndproot_gate.run.<pid>/install/cfg_pkg/...`.
The excerpt records 52 distinct `ERROR: Cannot open file` lines: 23 B
matrices, 28 C matrices and the bitstream. Because the attachment begins at B
slice05, that is the first captured failure, not necessarily the first loader
failure.

`JSON config: 86 matrices loaded` and `Reg Started.` are not success gates:
the TB emitted them after the failed opens. No natural terminal or formal D is
available. E3/E4/E5 therefore remain false. The failure is package-local and
does not adjudicate DUT, numeric, config contents, or the separate native
four-lane p12 issue.

Classification:
`PACKAGE_LOCAL_RUNTIME_INSTALL_LOCATION_VS_SCA_RELATIVE_PATH_MISMATCH`.

## v53 fix scope

Fresh identity: `r5_n4_hw_v53_sca_cwd_fix`.

The runner now:

- requires a pre-existing, non-symlink `$server_root/install`;
- installs the frozen payload at
  `$server_root/install/cfg_pkg/r5_n4_hw_v53_sca_cwd_fix`;
- keeps compile/run/evidence and final atomic return under the fixed server
  result root `/home/panqs/ndp/simresult`;
- preserves the NDP root direct-child name/type exact set, because only an
  isolated subdirectory of the existing `install` entry is used.

Numeric, W3, workload, config, golden, observer, timeout, backpressure and
functional RTL are frozen. This is a runner/package fix, not a DUT fix.

## Local verification

The exact final runner was executed in an isolated Git-Bash harness. The safe
simulator consumed the real `+SCA_CFG` argv and opened, read and SHA256-hashed
all 86 SCA input consumers from the actual TB cwd. Normal, compile-fail, HUP,
INT and TERM paths retained their expected exits and finalizer behavior.

Fail-closed controls cover:

- matrix deleted after install preflight;
- bitstream deleted after install preflight;
- one SCA relative prefix changed;
- cfg root moved back outside the NDP root;
- missing pre-existing `install` parent;
- new root-level directory;
- new root-level file.

The first four fail at actual SCA opening, the parent control exits before
write, and the root-level controls fail the root exact-set gate.

Current rule receipts after generation:

- `.agents/rules/生成前必读索引.md`:
  `1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500`
- `.agents/rules/服务器测试包生成规则.md`:
  `b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724`
- `.agents/rules/INT8_SA点积专项规则.md`:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`:
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`

Applicable rule confirmations:
`CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`,
`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`,
`CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`,
`CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`, and
`CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`.

The current SCA rule already requires paths to resolve from the actual server
simulator working directory and treats `Cannot open` as failure. No public
rule delta is required; the escape was v52 package noncompliance and
insufficient safe-stub coverage.

## Release

`r5_n4_hw_v53_sca_cwd_fix` is `PACKAGE_READY_NOT_RUN`.

- pickup ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v53_sca_cwd_fix.zip`
- ZIP bytes/SHA256:
  `5147227` /
  `3ec80d1f583c267b4e894a06e196a61c63ed60ee5b5c672556329abd074ad77a`
- command after extraction:
  `bash r5_n4_hw_v53_sca_cwd_fix/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
- expected return:
  `/home/panqs/ndp/simresult/r5_n4_hw_v53_sca_cwd_fix_return.zip`
- final ZIP audit:
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`
- server action: none.

v52 was actually run and is retained under the `tested` disposition. v53 is
the only pending serialized-node0004 ZIP.
