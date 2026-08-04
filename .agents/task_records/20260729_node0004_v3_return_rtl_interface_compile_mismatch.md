# node0004 v3 observer return adjudication

Date: 2026-07-29

## Scope and identities

- Return ZIP:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v3_obs_return.zip`
- Return bytes: `30967`
- Return SHA-256:
  `31389aa859418d7bba866f07ee9410e00fe2e83f4ce5c53c1e45ba3c610e9750`
- Bound source package:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v3_obs.zip`
- Source package SHA-256:
  `84c834de989c7912edfd711cd5fb2bdfe51e40998bb493d3e4ec5b99da9a331c`
- Source sidecar SHA-256:
  `88506c715857b1f9c15c9c51c7a2b0cf557dffa80d31941cd0f2ed84a44c1db3`
- Source validation SHA-256:
  `2ba469090caad4f88be675907b8683f86aa8f8335ace0f5c9568df26c3f6765c`
- Active server-package rule SHA-256:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`

## Return integrity

- ZIP CRC: pass.
- Exact file set: pass, 9 files.
- `RETURN_ALLOWLIST.json`: pass, 8 declared payloads; every size and SHA
  matches and there are no undeclared files.
- Package preflight: valid, 829 files, 320 formal readback targets, 0
  preloaded targets.
- Install preflight: valid, 503 files, 0 preloaded targets.
- Package-local observer SHA:
  `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`.
- Observer precompile identity/XMR guard: pass; 198 generated-instance
  references checked, 0 runtime-indexed generated XMR references.
- The compiler command contains
  `+incdir+/home/panqs/ndp/r5_n4_hw_v3_obs/tb_probe`; compile.log line 2394
  confirms that exact observer was parsed.

## Joint result gate

The conjunction fails:

- compile exit = 2, not zero;
- run exit = 125, not zero;
- simulation did not start;
- natural terminal was not observed;
- formal readback produced = 0 / 320;
- missing = 320;
- mismatch bytes = 0, but this lone true predicate cannot produce PASS.

The v3 result gate therefore correctly reports `NODE0004_SERVER_FAILURE`.
There is no E3/E4/E5 or Conv numeric evidence.

## FIRST_DIVERGENCE

`SERVER_RTL_INTERFACE_COMPILE_MISMATCH`

After the observer was successfully parsed, VCS reports:

- compile.log line 2451: `Error-[UPIMI-E] Undefined port in module instantiation`;
- line 2452: caller
  `rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v:124`;
- line 2453: port `slice_rst` is not defined in module `SA_PE_Mul_Array`;
- line 2454: compiled callee definition is
  `rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v`.

Thus the server filelist contains an internally incompatible caller/callee
interface: the caller connects `.slice_rst(slice_rst)`, while the compiled
callee definition lacks that port. `compile_driver.log` independently records
the same ordered signature.

## Adjudication

- The v2 package-local observer include blocker is closed.
- This failure is a server source/RTL integration mismatch, not a Conv
  arithmetic, mapping, terminal, lifecycle, or readback result.
- The package contains zero RTL entries and this task has no authority to
  modify server RTL or hide the compiler error.
- No successor package is authorized by this return.
- `PACKAGE_RELEASE=NONE`.
- Numeric analysis repeated: false.
- node0004 workload rebuilt: false.
- Reused asset consumption: read-only source package/sidecar/validation only.
- Server inspection outside the supplied return: false.

## Machine evidence

- Report:
  `artifacts/operator_config_validation/r5-node0004-hw-v3-return-analysis/report.json`
- Report SHA-256:
  `bf3d69771856285ead5771ef271b466909ba72057716eea4134b9c87aeb7cfab`
- Analyzer SHA-256:
  `4a889dc22c2d4d5a914db85e1add8a95120cdc2222d5d2c3cc7a0b9ce97aa6f7`
- Directed test: 1/1 PASS.

## BLOCKER_DELTA

- close: `B_NODE0004_PACKAGE_OBSERVER_INCLUDE_PATH`
- add: `B_NODE0004_SERVER_RTL_COMPILE_INTERFACE_MISMATCH`
- keep:
  `B_NODE0004_DYNAMIC_RESULT_PENDING`,
  `B_NODE0004_SERVER_RTL_IDENTITY_UNBOUND`,
  `B_NODE0004_NO_DYNAMIC_BASELINE`

## RULE_DELTA_PROPOSAL

None. The current conjunction, absent-readback, observer include/XMR and
allowlist rules already classify the return without ambiguity.
