# GAP node0071 v40 return and v41 branch-isolated config fix

- analysis owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- date: 2026-08-06
- scope: GAP-family return adjudication, config-only successor, local validation,
  final-ZIP release audit, and storage rotation
- functional RTL modified: false
- server accessed/uploaded/run: false

## Current control receipts

- agent: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- plan at final receipt: `a560d6bc6ef2fc3d0218cab0788d862bf8c9a6ec0b911cbfeebebaf8d2e1b2b1`
  (mutable provenance only)
- index: `2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706`
- server rules: `5540e9c724e9c313e9a874a8251ad291328d4df80f01382ca091520893e757a1`
- config rules: `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- NDP field rules: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- GAP int32 rules: `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b`
- GAP probe rules: `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1`
- exact UINT8 tail rules:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- cloud RTL authority: `xlsjdjdk/Trassic2.0_RTL`
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`

## RETURN_ANALYSIS

Input:

- return bytes/SHA:
  `231089 / fdec51572f3017bf5cc0af70ee66873128c784b04a5988b6b8f9ea69aadf6a48`
- source bytes/SHA:
  `1833762 / 7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4`
- adjacent sidecar absent; accepted only at external transport layer under the
  user-attested no-sidecar rule.

All internal CRC/root/path/duplicate/symlink/RETURN_MANIFEST
exact-set/allowlist/per-file/source/package/install/run/return/preflight gates
passed. Compile exited 0. Simulation and runner exited 125 under `INT`;
natural terminal is false. Only `sum_s1` started and no stage completed.
Formal D is expected/present/missing=`48/0/48`; mismatch bytes is zero but is
unevaluable. E3/E4/E5 are all false.

The return's actual compile root is `/home/panqs/ndp/NDP_copy01`; compile
success binds the observer/XMR surface and actual argv to that tree. The
return does not contain an exact Git commit receipt, so the actual compiled
commit remains `UNBOUND_BY_RETURN` despite the current cloud authority being
0ccae916.

LAST_PROVEN_GOOD: MSE0 and MSE3 each complete Memory_AG occurrences 1..185.
Both Buffer_AG paths preserve 217 enqueue and 185 dequeue occurrences, leaving
the exact FIFO depth 32 without loss or overflow.

FIRST_DIVERGENCE:
`MEMORY_AG_SUPPLY_OCCURRENCE_186_ABSENT_WHILE_BUFFER_AG_OCCURRENCES_186_TO_217_ACCUMULATE_TO_FIFO_DEPTH_32`.

HANG_ROOT_CAUSE:
`LONG_RUNNING_HANG_AT_SHARED_LC_AND_READY_CYCLE_BUFFER_AG_FULL_MEMORY_AG_EMPTY`.
The shared Buffer/Memory DRAM-LC roots allow the buffered branch to advance 32
occurrences and fill; the shared destination-ready conjunction then suppresses
the Memory occurrence required to drain that queue. This dynamically selects
route 2 of `CDA-GAP-INT32MAC-BRANCH-ISOLATION-001`.

Machine reports:

- `artifacts/operator_config_validation/r5-gap-node0071-v40-return-analysis/report.json`
  bytes/SHA:
  `12572 / 82881faedb53fa55bbc413e1293ff870702532424759a7441bc95c81104dc865`
- `artifacts/operator_config_validation/r5-gap-node0071-v40-return-analysis/closure_report.json`
  bytes/SHA:
  `6807 / 73507832de15545015fc8085e8c1b8c0e01ce27ca983826b75e4f078f58bf37c`

## v41 successor

Identity: `r5_n71_gap_v41_branch_isolated_config_fix`.

Classification: `CONFIG_ONLY_CORRECTNESS_BASELINE`, `candidate_release=false`,
evidence ceiling `E2_LOCAL_ONLY`.

The eight strict stage configs allocate independent Buffer branch roots:
sum GROUP0/1/2 use LC8/9, LC12/13, LC16/17 respectively; tail GROUP0/2 use
LC8/9 and LC16/17. Memory roots, addresses, GA, buffer configuration, timeout,
backpressure and functional RTL are unchanged.

Frozen set:

- 64 input/golden files byte-equal to v40
- observer byte-equal to v40
- numeric/sum/tail/workload/golden not recomputed

Validation:

- strict config: 8/8 pass
- native exact mapping: 8/8 pass, penalty 0, no fallback
- mapping double build: 8/8 byte-equal
- final ZIP double build: byte-equal
- runner to safe compile/simulator stub: exit 0
- TERM shared finalizer: exit 0
- focused package-local HDL scope: exit 0
- config/identity/feature/finalizer/HDL negative controls: all fail closed
- final ZIP self-audit: PASS, errors=0
- storage audit: exit 0

Key reports:

- config manifest SHA:
  `b082ca1924b3f7598e22a78396e0602f338b2504d20102dc4756ab80993211f0`
- mapping report SHA:
  `ecc9871e9afed36901e2cfb5544c824e4986d917b32a4820e6079bedc8f76100`
- runner report SHA:
  `e9f8f8b0e2aadce538928e939f254695b25f2edf6ac0d5ba030e60b8e106222f`
- signal report SHA:
  `8b987ae41ec1d91a8269b1ce205b79d80256eba638cc728f77fc03be20cfb669`
- HDL report SHA:
  `c0d0cf5a2195daffd6f2f620355a600d5fe729aee814739ac9f15d8b4c9183df`
- final audit SHA:
  `f1f84733e68fcd6f188e2fdee128aaf194a454337e8f52649fb0a863d5db5e85`

## PACKAGE_RELEASE

`PACKAGE_READY_NOT_RUN`

- pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v41_branch_isolated_config_fix.zip`
- bytes/SHA:
  `1936886 / 11dd499aa99b2d2a67220a0d803e1878da8e1d932f51cee1b0e7c3430e957ed6`
- sidecar is internal under
  `pending_receipts/gap_node0071/r5_n71_gap_v41_branch_isolated_config_fix/`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_n71_gap_v41_branch_isolated_config_fix_return.zip`

The consumed v40 package and receipts were moved without overwrite to
`tested/gap_node0071/r5_n71_gap_v40_lc_supply_conservation_diag/`.
The GAP family has exactly one pending ZIP. Storage index SHA:
`6c669749ce195d4d02aa1c29230bb9b93eb128d319ddf0d7d05500bbf0aee74b`.

## Blocker and rule delta

Closed:
`B_GAP_NODE0071_BUFFER_AG_TO_MEMORY_SUPPLY_SHARED_LC_OCCURRENCE_OR_BACKPRESSURE_PENDING_LEAF`.

Open until formal v41 return:

- dynamic natural terminal
- exact 48 formal D targets
- actual compiled commit binding

RULE_CONFIRMATION:
`CDA-GAP-INT32MAC-BRANCH-ISOLATION-001`,
`CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`,
`CDA-CONFIG-BOUNDARY-MICROTRACE-001`,
`CDA-SERVER-RESULT-GATE-CONJUNCTION-001`,
`CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`, and
`CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`.

RULE_DELTA_PROPOSAL: `NONE`.
