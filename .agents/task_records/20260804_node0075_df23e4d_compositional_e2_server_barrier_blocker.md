# node0075 df23e4d compositional E2 and server barrier adjudication

Date: `2026-08-04`

Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

Owner: `019fc775-8de0-7f10-bc4a-026a4673776f`

## Scope and ownership

This record covers only QLinearMatMul/node0075 and its node0075-owned
`MatMulInt32Accumulate` plus exact UINT8 requant tail/D endpoint.  No Conv,
GAP, QLinearAdd, Quantize/Dequantize/View family asset, functional RTL,
`.agents/plan.md`, or public rule was modified.  The approved
node0071-to-node0075 UINT8 identity alias was consumed without recomputing the
node0072/View/node0074 frozen result.

The worktree was treated as shared and dirty.  Existing and parallel changes
were neither reset nor deleted.  No server upload, run, lease, or remote
mutation was performed.

## Start inventory and collision adjudication

The read-only start inventory found historical/previous-owner node0075 assets,
including the old materializer-blocking-leaf contract and the d0aa87f
negative-psum revalidation.  Representative identities were:

- `contracts/operator_config/node0075_materializer_blocking_leaf_v1.json`
  SHA256=`f17cf7fc84c6cee591e3afbfd0fc01276f58f0fff40e32a628ca5d0696224111`;
- `contracts/operator_config/node0075_negative_psum_d0aa87f_revalidation_v1.json`
  SHA256=`3e04bcc0994272ca713acc15f34b26cfb0c38f3d1aba53253f3dbb3f2085b9f7`;
- `outputs/node0075_negative_psum_d0aa87f_revalidation/current_rtl_and_recurrence.json`
  SHA256=`fd10530f88c444e829d1248c0e73c51fb5a17639012546eaba4b0d8cf42ad2a5`.

They were retained as read-only provenance.  The df23e4d recurrence,
materializer, E2 and blocker receipts use fresh paths/test IDs, so no old-owner
node0075 result was deleted, overwritten or presented as current acceptance.

## Current-source arithmetic gate

The active source identity was Trassic master
`df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727`.  The consumed active member was:

- `NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v`
- bytes=`1951`
- SHA256=`72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3`

An independent fresh recurrence/current-source replay closed the old
`B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE` leaf:

- recurrence cases=`8,192,000`, mismatch=`0`;
- negative psum occurrences=`4,343,952`;
- negative-to-exact-zero occurrences=`272`, current-source mismatch=`0`;
- adjacent/acceptance/small-domain/single-product/full-domain/four-lane RTL
  vectors=`110,364`, mismatch=`0`;
- marker=`RTL_REPAIR_FULL_REACHABLE_PASS`;
- machine report:
  `outputs/node0075_negative_psum_df23e4d_revalidation/current_rtl_and_recurrence.json`,
  SHA256=`4d4aad044e4f241bc9af3cf244cec0069335d7da17760645c8a2f57926105c88`.

The current `GA_Inport` signed-ingress focused test also compiled and simulated
with exit `0/0` for zero, `+1`, `-1`, `-2`, and the node0075 minimum
`-44906`.  Its testbench is
`tests/rtl/node0075_df23e4d_ga_signed_ingress_tb.sv`, SHA256=
`b43ba707b7bc05042bfa2d563ebdd54f1779e19c0753710d6623ecf60333112a`.

## Handler, registry and materialization

The active ndp-sim path now has explicit entries for:

1. `MatMulInt32Accumulate`;
2. `Node0075RequantScaleInt32ToFp32`;
3. `Node0075RequantRoundFp32ToUint8`.

The materializer emits eight accumulation, eight scale and eight exact-round
operators.  It binds logical A `[16,2048]` UINT8, B `[2048,1000]` INT8,
accumulator `[16,1000]` INT32 and final D `[16,1000]` UINT8.  Each pass has a
physical width of 128 columns; pass 7 contains 104 logical columns and 24
zero-weight padding columns.  The requant contract binds scale bits
`0x3a510db3`, output zero point `60`, and the approved exact UINT8 tail.

The final materialization contains 24 mapping/bitstream configurations, a
505-line 128-bit execplan and 24 `Start_Comp` occurrences.  SCA contains 128 B
fragments and zero A/intermediate fragments.  SCA_D contains exactly 128 final
D fragments.  A remains an alias of the 16 node0071-owned slice bases and is
never copied, precomputed, relaid out or host-replayed.

Primary receipts:

- materializer report SHA256=
  `11c05a26e2d4aecf9e22279383cb143b17e13b23d0bc18557b11b9ebc8cc1330`;
- deterministic/config-binding validation SHA256=
  `3d6d8fd4836d81d914da8ff4e4fd4d70a58ab19aefb347a4d21e154d6826ea58`;
- target JSON SHA256=
  `ac01a5aba5aac67eeb214da76400b138d86a7e39c2e6ff9fb5d65bbfd40f4065`;
- execplan SHA256=
  `152e09ace080ca8cfe9da3bcb1edaa070458cb3a6d36eb77fc1b5ada79aa3272`;
- SCA SHA256=
  `0e293fc982e06a7e7b61a40899792f0a1fe1329f9c48b9b350f47650ba656b98`;
- SCA_D SHA256=
  `174eb19a92b4de4a246a806544dd1126905dde0255180e24c783585fa32c742d`.

The independent validator performed two complete fresh builds and compared
all 261 generated members byte-for-byte.  Its terminal status is
`DETERMINISTIC_CONFIG_BOUND_LOCAL_E2_PASS`.

## Actual qualified A reload accounting

The configured diagnostic uses the mechanically minimal
`ceil(1000/(16*8))=8` passes.  These are real configured node0075 consumer
occurrences over the same node0071-owned byte set, not a counterfactual budget:

- reads per pass=`1,024`, bytes per pass=`32,768`;
- accepted 32-byte reads per slice=`512`;
- accepted read occurrences total=`8,192`;
- total accepted/configured A traffic=`262,144` bytes;
- unique A storage=`32,768` bytes;
- occurrence SHA256=
  `0ef4664aae656101416c20dc248065ff903e774201836b5a196fff3cdb894950`;
- global unique-byte-set SHA256=
  `d219845a728d77bc35b545229b5b86a55fee0c5da0bb328e180037a4c1f9ce86`;
- slice-0 ordered-address hash per pass=
  `4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d`;
- slice-0 read-byte-set hash per pass=
  `3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06`;
- allocation release is after the final pass's last accepted read and no
  pending consumer transaction.

The local accumulator mismatch count, UINT8 D mismatch count and padded-column
mismatch count are all zero.  This is config-bound compositional E2; it is not
server natural termination, dynamic consumer acceptance, E4 or E5.

## First server-package blocking leaf

After E2 closure, the fresh-memory package gate fails at exactly:

`B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED`

The node0075-only final execplan starts with the pass-00 consumer.  It contains
no node0071 producer occurrence and no cross-operator visibility barrier.  SCA
correctly contains no A preload.  Consequently, a fresh server simulator has
no legal runtime writer for the aliased A bytes.

The following substitutions are forbidden and were not used:

- preloading frozen A through SCA, because that is intermediate tensor replay;
- copying, precomputing or performing a relayout of A into new storage;
- assuming producer base addresses are initialized, because a producer base is
  not consumer acceptance or a runtime writer;
- importing or modifying a foreign operator family's workload without scope.

The minimum unblock condition is one mainline-supplied or explicitly authorized
integrated execution stream containing a legal true-producer prefix, its final
write/visibility barrier, and then node0075 pass 00 in the same simulator
execution stream.

Machine adjudication:

- report:
  `artifacts/operator_config_validation/r5-node0075-df23e4d-compositional-e2-server-barrier-blocker-v1/report.json`,
  bytes=`7387`, SHA256=
  `80a8526998afc8175812a00784662fd54c7621eb65c37e7c0ad540ece8f130ca`;
- contract:
  `contracts/operator_config/node0075_df23e4d_compositional_e2_server_barrier_blocker_v1.json`,
  bytes=`7642`, SHA256=
  `da90bed7e65d5cd8b246664c1caa9386bc35bc41ede257920e05620e6146ca1f`;
- independent validator terminal status=
  `INDEPENDENT_SERVER_BARRIER_BLOCKER_VALIDATION_PASS`.

Terminal status is `WAIT_USER_DECISION`: continuing requires a material scope
expansion or a mainline-supplied cross-family producer prefix.
`PACKAGE_RELEASE=NONE`, `candidate_release=false`.  No ZIP exists, so there is
no final-ZIP self-audit to claim.  The preparatory node0075-scoped runtime and
observer sources are draft tooling only; they were not packaged, compiled into
a package, uploaded or executed.

## Read receipt and mutable provenance

The start-of-work complete-read identities included `.agents/agent.md` SHA256
`d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`,
`.agents/plan.md` SHA256
`f00f906bc877e186e31c279f514091b91ad5044249e49170f258ab427cb39734`,
and routing-index SHA256
`db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`.
During the shared run, mainline legitimately updated these entry files.  They were
re-read from disk before this adjudication; current identities are:

- `.agents/agent.md` SHA256=
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`;
- `.agents/plan.md` SHA256=
  `6ccdcb93c511e4e4ed19fdc1f2ed4276c6abea209ab71168faf9d04b438800bc`;
- `.agents/rules/生成前必读索引.md` SHA256=
  `5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b`.

The routed operator, hardware-field, INT8-SA and exact-UINT8-tail rule files
retained their already-read identities.  The server-package rules changed from
SHA256 `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
to SHA256 `0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e`
during the shared run and were completely re-read before final adjudication.
The index/server-rule delta adds diagnostic time-to-root-cause and legal
execution-reduction boundary guidance; it reinforces, rather than removes,
this fresh-memory provenance barrier.

## Rule feedback and claim boundary

`RULE_CONFIRMATION`:

- `CDA-VIEW-ACCEPTED-LIFETIME-001` correctly preserves producer-to-consumer
  visibility and release requirements across all eight reads;
- `CDA-SERVER-WORKLOAD-PROVENANCE-001` prevents a base address or frozen tensor
  from being treated as a fresh-memory runtime writer;
- `CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001` keeps missing dynamic evidence
  explicit;
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001` prevents compositional E2 from being
  promoted to E3/E4/E5.
- `CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001` requires a reduced
  execution to start from a graph external typed input, a verified hardware
  checkpoint or an explicitly approved frozen diagnostic stimulus; it forbids
  replaying a DUT-produced internal tensor as the boundary.

No non-synonymous rule delta is required.  The blocker delta is: the old
negative-psum arithmetic leaf and the local handler/materializer/config-bound
E2 leaves are closed; the first remaining package leaf is the integrated true
producer-final barrier stated above.
