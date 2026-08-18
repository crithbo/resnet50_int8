# Serialized Conv node0004 v97b formal return: validated input1 tag undersupply

## Ownership and scope

- role: `family.conv.serialized`
- owner epoch: `2`
- registry epoch: `6`
- package: `r5_n4_hw_v97b_tbvcd_memtuple_xmrefix`
- execution / attempt: `r1786793347853153460_2912853 / a2912853`
- mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- server actions: none
- storage-manager calls: none
- functional RTL/config/numeric/workload/golden changes: none

## Previous progress and current purpose

v95 validated that the Memory_AG metadata side is short by exactly one 32-unit
transaction: 18 metadata descriptors cover 288 units while 20 prepared-data
groups cover 320 units.  v96 did not execute the target because of duplicated
XMR identities.  v97 repaired those XMR identities and returned the 153-signal,
three-input tuple discriminator under semantic-v5.

This analysis binds the exact return/package/execution/root/config/source/VCD
identities, then uses the same-attempt three-input tuple leaves to distinguish
input0 KEEP, input1 BUFFER, input2 KEEP, same/gotten suppression, and split-FIFO
or keep-release loss.

## Integrity and bounded streaming

- exact return: `C:/Users/15383/Downloads/r5_n4_hw_v97b_tbvcd_memtuple_xmrefix_r1786793347853153460_2912853_return.zip`
  - bytes: `710085642`
  - SHA-256: `5bc3e44f95cd5df54de5deff9c084d7dbc192215657ec4e504335b900b30aa1d`
- source package identity: bytes `5332235`, SHA-256 `bcd94e23123e95742a555897e05eace58a36002219ca110ff3f15ea92e297ad9`
- return core: 46 required receipts checked; no missing or identity error
- VCD member: bytes `709651866`, SHA-256 `bc7725043dc302e3924a005689460a623a39bcb0d629f175a0b373e38c740ed2`
- streaming EOF: byte `709651866`, line `90926817`, timescale `1ps`
- final VCD timestamp: `28413985000 ps`
- last effective non-clock change: `2446436875 ps`
- the shared resumable reader consumed the VCD in three bounded 256 MiB chunks;
  `analysis_state.json`, append-only `checkpoints.jsonl`, and incremental
  `report.md` were maintained throughout.

VCS represented 51 cataloged bit-select leaf paths as 17 whole packed variables
in the VCD.  These variables are present and identity-bound.  The 51 four-state
leaf streams were therefore derived deterministically from the exact packed
vectors.  This corrects the preliminary catalog-multiplicity interpretation;
it is not a claim based on missing signals.

## Execution and terminal boundary

- production compile/elaboration/link: pass, exit `0`
- simulation started: true
- target entry: `sig_mse_enable=1` at `2445779375 ps`
- simulator exit: `124`, signal `NONE`
- sole exit authority: shared semantic-v5 runtime evaluator
- stop reason: `WALL_CEILING`
- false freeze / false plateau: excluded
- process tree: fully reaped; TERM used, KILL not needed
- VCD: stable and closed; full-file bytes/SHA/last timestamp bind the archive
- dumpoff / dumpflush: not observed because the wall ceiling preceded the
  planned causal stop
- natural terminal: not proven
- formal-D / E3 / E4 / E5: unproven
- return status: `PARTIAL_EXECUTION_RETURN / DIAGNOSTIC_EVIDENCE_INCOMPLETE`

The non-natural terminal prevents later completion claims but does not invalidate
the earlier same-attempt tuple transaction sequence that closes the dispatched
diagnostic leaf.

## Direct config evidence

The byte-bound frozen stream4 configuration is a target-D write with:

- Memory_AG indices: `[DRAM_LC.LC13, LC_PE.PE1, DRAM_LC.LC14]`
- modes: `[keep, buffer, keep]`
- keep-last indices: `[0, 3, 1]`
- buffer spatial size: `16`
- same-attempt encoded transaction total: `32`

The same-attempt prepared side produces 20 groups of 16 units, so it requires 10
Memory_AG tuples of 32 units.  The LC9/PE1 historical consumer ledger corroborates
the intended epoch relationship, but it is comparison evidence only and does
not validate a production config workaround.

## Direct actual RTL evidence

The returned actual compiled `Memory_AG_Idx_Queue.sv` identity is bound to the
production root `/home/panqs/ndp/NDP_copy01`.  Its exact equations show:

- lines 49-54 decode buffer/keep/constant modes;
- lines 60-63 unpack `{valid,last,same,last_index}` from each input tag;
- lines 76-95 update gotten state;
- lines 127-135 apply same/gotten masking;
- lines 159-183 implement source readiness, split-FIFO write/read and valid;
- lines 195-217 select the buffer last state and compute all-match/hold/release;
- lines 233-234 write one aggregate tuple only when all three inputs match.

For input1 buffer mode, the keep-release mask is unconditionally enabled.  The
returned actual-source set ends at `mse_mem_queue_tag[1]/idx[1]` and does not
contain the upstream LC_PE/IGA producer implementation.  Thus the boundary root
is proven, while its precise upstream source line is not.

## Same-attempt dynamic adjudication

- clock-qualified split-FIFO writes per input: `[5, 9, 2]`
- aggregate Memory_AG tuple writes: `9`
- input1 is queue-ready for every aggregate tuple
- input1 source-ready remains `1`
- input1 split FIFO never becomes full
- input1 same/gotten mask never becomes `0`
- input0 and input2 KEEP FIFO heads are valid at every aggregate tuple
- metadata aggregate queue never becomes full
- input1 token 8 asserts last; its tuple is written at `2446411875 ps`
- input1 token 9 follows as non-last; its tuple is written at `2446421875 ps`
- no tenth input1 token appears
- tuple / metadata descriptors / prepared groups: `9 / 18 / 20`
- metadata / prepared capacity: `288 / 320` units

`LAST_PROVEN_GOOD = 2446426875 ps`: the eighteenth/final metadata descriptor is
accepted and all nine tuples remain losslessly accounted.

`FIRST_DIVERGENCE = 2446428125 ps`: the nineteenth 16-unit prepared group is
accepted after input1 has supplied and Memory_AG has consumed only nine tags;
there is no metadata capacity for this group.

## Candidate matrix and root

| Candidate | Disposition | Decisive evidence |
|---|---|---|
| input0 KEEP ends early | EXCLUDED | input0 head valid at all nine tuples |
| input1 BUFFER supply ends early | VALIDATED_ROOT_LEAF | nine accepted/dequeued tokens, no tenth |
| input2 KEEP ends early | EXCLUDED | input2 head valid at all nine tuples |
| same/gotten suppresses tuple ten | EXCLUDED | input1 mask stays enabled |
| split FIFO / keep release loses tuple ten | EXCLUDED | source ready, never full, queue ready, buffer-mode RTL release |

`VALIDATED_ROOT_CAUSE = MSE4_MEMORY_AG_INPUT1_BUFFER_TAG_STREAM_UNDERSUPPLIES_ONE_TUPLE`

Root class: `UPSTREAM_INPUT1_TAG_GENERATION_OR_EPOCH_LAST_ACCOUNTING`.

Prepared data needs ten 32-unit metadata tuples, while the actual Memory_AG
input1 stream supplies only nine.  Memory_AG accepts and consumes all nine
without an in-module loss.  The missing tenth tuple is therefore upstream of
the returned Memory_AG input boundary.

## Workaround, audit, and disposition

- `CONFIG_WORKAROUND = NONE_VALIDATED`
- no workaround is recommended because the exact upstream producer source and
  config-to-producer transition chain were not returned
- `RULE_GAP_AUDIT`: not triggered; the target leaf closed uniquely
- `PACKAGE_BUILD_FAILURE_RULE_AUDIT`: not triggered; v97 compiled, started and
  executed the target, so v96 is not part of a consecutive pretarget-failure pair
- `RULE_CONFIRMATION_NO_CHANGE`: semantic-v5 and the direct tuple cone were
  sufficient for this return
- implementation feedback: future packages using these leaves should catalog
  the 17 packed variables directly, matching VCS's emitted VCD representation
- successor: none
- terminal disposition:
  `VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION`

Further package-only diagnostic expansion is not meaningful.  Any modification
to the upstream tag producer, epoch/last accounting, or config requires separate
user authorization and an actual-source/config-consumer proof for that producer.

## Formal artifacts

- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/formal_return_analysis.json`
  - bytes `21259`, SHA-256 `a42ebbe038d79ed313c4e5925777811ee1458b2e90e40d69e20fe1d106df0c89`
- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/DIRECT_CONFIG_ACTUAL_RTL_EVIDENCE.json`
  - bytes `13853`, SHA-256 `43e1459d6bf8c5e2e4015a3257367bff8036c749655b2662c3cea23d0ad2c84f`
- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/RULE_AUDIT_DISPOSITION.json`
  - bytes `915`, SHA-256 `71ab328d799987ff7d8d9938129ce821f8c6d31b244cc3115be3d4a3d6aa108a`
- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/mainline_return_receipt.json`
  - final receipt binds this task record and all formal artifacts
- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/streaming/analysis_state.json`
  - bytes `31243`, SHA-256 `e2cdaab4b2df86a8299f919b2ba71bfcf4aef373dbe12ab72819216dbf60d59e`
- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/streaming/checkpoints.jsonl`
  - bytes `2925`, SHA-256 `0e15807c7d09a80b3e4fe2496f095f717457f63c6e87505ae0de2fddb6539b5a`
- `outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_r1786793347853153460_2912853/streaming/report.md`
  - bytes `1722`, SHA-256 `31e77becdf62e696e20991300f9b496562cf7826e17464a2ce1cb8810ec87221`

Claim boundary: the exact package/config/actual Memory_AG/VCD/dynamic chain proves
the upstream input1 tag undersupply at the Memory_AG boundary.  It does not name
the uncaptured producer source line, validate a config workaround, or claim
natural/formal completion.  Conflicts: `[]`.
