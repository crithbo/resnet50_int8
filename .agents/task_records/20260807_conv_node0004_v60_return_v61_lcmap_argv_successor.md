# Conv node0004 v60 formal return → v61 mapped-LC diagnostic successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Result: `PACKAGE_READY_NOT_RUN`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`

## v60 formal return

- Return ZIP: `C:/Users/15383/Downloads/r5_n4_hw_v60_install_only_return.zip`
- Bytes/SHA256: `121269` / `6cd43cd7bbea1c2e2dd37c409b7f4cca7eba2468fd2bca645945f49b4fadf0d2`
- Frozen source ZIP bytes/SHA256: `5154474` / `cb3342e90510e4cd1e66afb9a19977cc5eae725abccf987346757d3d34937ec8`
- External sidecar: not required under the user-attested transport rule.
- CRC/root/path/exact-set/allowlist/source/package/install receipts: PASS.
- Production compile/run: `0/0`; signal: `NONE`.
- Natural terminal: false.
- Formal D: expected `320`, present `0`, missing `320`, mismatch `0`.
- Result conjunction and E3/E4/E5: false/false/false/false.

`LAST_PROVEN_GOOD=V60_INSTALL_ONLY_LAYOUT_COMPILE_SIM_AND_QUALIFIED_D_WRITE_PROGRESS`.

`FIRST_DIVERGENCE=PACKAGE_OBSERVER_LOGICAL_LC_ID_TO_PHYSICAL_RESOURCE_INDEX_BINDING`.

The final mapper proves:

- logical `DRAM_LC.LC13` → physical `LC6`
- logical `DRAM_LC.LC14` → physical `LC8`
- logical `DRAM_LC.LC15` → physical `LC17`
- logical `DRAM_LC.LC9` → physical `LC18`

The v60 observer instead sampled physical `13/14/15` as if logical IDs were
physical resources. Physical LC14/15 are unmapped/disabled, so the zero values
were expected and could not localize the logical chain. A separate package
receipt defect recorded only the base simulation argv, while the actual
invocation supplied all diagnostic plusargs.

Formal machine analysis:
`outputs/conv_node0004_v60_return_analysis/report.json`,
bytes `9127`, SHA256
`04c2355e720b083c54d107113ebc160558036af81ce88395f4bed3c750a7a8d2`.

## v61 successor

Identity: `r5_n4_hw_v61_lcmap_argv_fix`.

Only these surfaces changed:

1. observer LC data/config/ready consumers now use physical `6/8/17/18`;
2. `iga_lc_outport_bp_post` uses the matching physical index;
3. `simulator_argv.txt` records the complete actual diagnostic command;
4. fresh identity path-budget derivations are exactly `121/218`.

Numeric, W3, qparams, tail, workload, config, mapping, bitstream, execplan,
SCA semantics, golden, timeout, backpressure, functional RTL, ISA, hardware
and active ndp-sim are frozen. No server action occurred.

Final pre-storage ZIP:

- bytes: `5156332`
- SHA256: `c78e62cde4f8e185f801900773117017982920b9a479996a1c31af8a1dae1e96`
- sidecar file SHA256:
  `1bfe4796a54480b81ef516390ac9033c82ee9ae6ab7983b7428840eda31ceac2`
- deterministic double build: PASS.

Validation:

- family runner/install-only: PASS,
  SHA `9cd42c047b145d7ebbb47f1ddd4acd72813ea7f53207880c07eabb213b52a62a`
- shared harness: PASS,
  SHA `8d4fd342b6a65dcc7c1046236b4b4551b22db2386188fa768b64794423d5cdc7`
- shared runtime layout: PASS/errors=0,
  SHA `a04ce164d4b0c1550665bea341a77f8f3b89cbdfaebba87f5785de0d2621c36c`
- observer syntax/scope/mapping/argv: PASS,
  SHA `29183cfdc0244eb34c6152338d8376a9e7fd70f1c2edb4e1da7fc785197c28da`
- qualified predicate trace and negatives: PASS,
  SHA `0985f914cd516980b369407f298128bdae591ee57c4ffc6a74b964aa89788140`
- final ZIP audit: PASS/errors=0,
  SHA `f0ca8098ce0eb04ae969e53d116c80ec50c216e847331e3c1b7a0d50c7815067`
- exact SCA input opens from TB cwd: `86/86`
- normal/preflight-fail/compile-fail/HUP/INT/TERM controls: PASS
- wrong path/missing matrix/missing bitstream/observer declaration or consumer
  typo/wrong physical sibling/missing runtime feature negatives: fail closed.

Overall release report:
`outputs/conv_node0004_v60_return_v61_successor/report.json`,
bytes `7165`, SHA256
`e5c4f1bbb582503eed38c264a13a66bb1037a04899ccc66e70bbea1c2e0e5b5b`.

Storage rotation: PASS. v60 is under `tested`; v61 is the sole serialized
Conv pending identity at
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v61_lcmap_argv_fix.zip`.
Storage index bytes/SHA256: `141562` /
`fc34f06104e3caf9657a7d2f2a9ecf88b4e86b9752345fe18f4a1861be030d35`.

## Blocker delta

Closed by v60/v61 evidence:

- `B_CONV_NODE0004_V60_RUNTIME_INSTALL_LAYOUT`
- `B_CONV_NODE0004_V60_PRODUCTION_COMPILE_AND_SIM_START`
- `B_CONV_NODE0004_SIMULATOR_ARGV_FEATURE_RECEIPT_INCOMPLETE`
- `B_CONV_NODE0004_LOGICAL_LC13_LC14_LC15_LC9_PHYSICAL_CHAIN_UNOBSERVED`

Invalidated:

- `B_CONV_NODE0004_LC13_TO_LC14_TERMINAL_RELEASE_UNOBSERVED_AS_PHYSICAL_13_14_15`

Still invalidated and not reopened:

- `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`

Open until v61 formal return:

- `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`
- `B_CONV_NODE0004_FORMAL_D_320`

## Rule confirmation

`RULE_CONFIRMATION=CURRENT_RULES_CAUGHT_BOTH_ESCAPE_CLASSES`.

The current diagnostic-feature binding rule rejected the incomplete argv
receipt. The mapper/materialized-consumer and actual-consumer/XMR gates reject
using logical IDs as physical resource indices. No non-synonymous public rule
delta is needed.

## Claim boundary

v61 is locally release-ready only as a diagnostic package. It does not claim
production compile, DUT natural terminal, 320 formal D, E4 or E5 before its
formal server return.
