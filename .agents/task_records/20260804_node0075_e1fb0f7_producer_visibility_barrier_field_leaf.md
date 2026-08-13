# 2026-08-04 node0075 e1fb0f7 producer visibility barrier field leaf

## Scope and authority

- Owner scope: QLinearMatMul/node0075 integration only.
- Unique mainline/structured return target:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- User authorization consumed: read-only use of current node0071 numeric,
  materializer/configuration, and graph-external typed-input assets; a fresh
  node0071→node0075 integration stream was permitted only if current hardware
  fields could express and prove producer final-write acceptance,
  outstanding-cleared visibility, and then node0075 pass00.
- Required stop condition applied: if current hardware fields cannot express
  or prove that barrier, stop at the exact field leaf with
  `PACKAGE_RELEASE=NONE`.
- Not authorized and not performed: functional RTL, plan, public-rule, or
  node0071/other-family modification; upload; server execution; lease.

## Current identity bound by the adjudication

- RTL commit:
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- `NDP_copy01/rtl` tree SHA256:
  `70334ce5f9addcfa409d566e7f7215b9870f815a7afc813d55f020a3af3ae647`
- RTL sync report SHA256:
  `c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c`
- `.agents/agent.md` SHA256:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` SHA256:
  `d9d63138769fea2cb26e70da9350bbcd2ea16dd4fcb15d74d21c5e194e56ca2e`
- `.agents/rules/生成前必读索引.md` SHA256:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`

The complete current plan/rule/task-record route required by the owner
authorization was reread before the adjudication. The machine report carries
the full byte receipts.

## Golden and producer inventory

The blocker is not missing per-stage or per-node golden data.

- Current plan-selected node0071 v33 producer begins with 16 legal
  graph-external typed-input slice files, 12,945,408 bytes, tree SHA256
  `c82afdf5ee9dd4b1007e3ff57b69eb76d49fae63ce45d253239cb1dab22d6044`.
- Ordered producer stages are `sum_s1`, `sum_s2`, `sum_s3`, `sum_s4`,
  `sum_s5`, `sum_s6`, `tail_mul`, and `tail_round`.
- `sum_int32` golden: 16 files, 1,056,768 bytes, tree SHA256
  `305e36b375d0aec49fb841c97ba200d66af6354a15df396b6ce4fb1bdb8f5661`.
- `scaled_fp32` golden: 16 files, 1,056,768 bytes, tree SHA256
  `49285c5215016235b6d6ef8359f0b67733b3553af471ab5d22ebb23ddc65a29c`.
- `final_uint8` golden: 16 files, 264,192 bytes, tree SHA256
  `2e42e620e6c99ae030dda2bfb2f6b3d349c9473fea6324d0a13bb56d0e206e9a`.
- Existing node0075 oracle assets comprise its A UINT8 tensor,
  `MatMulInt32Accumulate` tensor, and final UINT8 D tensor. Their exact byte
  receipts are recorded in the machine report.
- The 8,192,000-occurrence node0075 recurrence remains bound to e1fb0f7
  because active `SA_PE_Float_CSA.v` bytes match the prior witness:
  mismatch count 0 and negative-to-exact-zero count 272.

These goldens remain comparison/oracle assets. They were not preloaded,
copied, precomputed, relaid out, or replayed as a substitute for executing
node0071.

## Exact hardware-field finding

The current node0071 execplan contains eight `Start_Comp` commands and eight
opcode `3'b110` commands. Opcode presence does not provide a live barrier:

1. `Slice_Execution_Manager.sv` declares
   `localparam BARR_CMD_OP = 3'b110`, but has no barrier-valid decode, barrier
   FSM state/transition, or write-drain/outstanding/visibility input.
2. An opcode `3'b110` command arriving in `IDLE` is consumed while
   `slice2gexec_ready` remains asserted; it is a no-op.
3. `Start_Comp` retires on `slice_cmpt_finish`.
4. `WR_Data_Channel.sv` derives that finish from the last write-data flag and
   `mem2mse_wdata_ready`.
5. For local writes the ready path terminates at
   `slice_wr_req_data_ready = !data_fifo_full`. This proves ingress acceptance
   into the local write-data FIFO, not FIFO empty, memory commit, producer
   outstanding zero, or node0075-visible final bytes.
6. A read-only observer can diagnose state after the fact but cannot gate
   node0075 pass00 and therefore cannot satisfy the authorized mechanism.

First missing leaf:

`B_MATMUL_NODE0075_E1FB0F7_PRODUCER_VISIBILITY_BARRIER_FIELD_UNEXPRESSIBLE`

Parent blocker remains open:

`B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED`

## Eight-pass claim boundary

The existing node0075 local-E2 materialization proves only the configured
minimum plan:

- reload passes: 8;
- configured qualified 32-byte read occurrences: 8,192;
- configured A traffic: 262,144 bytes;
- unique A byte set: 32,768 bytes.

No joint execution was generated or run. Runtime accepted reads and runtime
accepted traffic remain unobserved; configured traffic was not promoted to
actual consumer acceptance.

## Outputs and exact receipts

- Contract:
  `contracts/operator_config/node0071_node0075_e1fb0f7_barrier_field_leaf_v1.json`
- Machine report:
  `artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-barrier-field-leaf-v1/report.json`
- Contract/report SHA256:
  `d9ba470fa723ca2c48d37688cfdb5fee173697f3cf516fd2b0380a7b5e82ee7c`
- Independent validation:
  `artifacts/operator_config_validation/r5-node0071-node0075-e1fb0f7-barrier-field-leaf-v1/validation.json`
- Validation SHA256:
  `be1dd162368c45dd6706880b564e4cff86164cfb3203406e07bc6654cc6f4988`
- Builder SHA256:
  `048bf990494817f3bcc0b4745ce7d458d617ab5dd6a01d53514fd23b2bace20c`
- Validator SHA256:
  `cc818fcea2a2bda08be4958ce743b9a0344b3f183476d82d7cab3b705902897a`
- Determinism: two consecutive build/validate cycles produced identical
  contract, report, and validation hashes.
- Validator result: 0 errors; 7 negative controls passed.

Generation stopped before a fresh integration target, mapping, bitstream,
execplan, SCA, SCA_D, formal D, or ZIP. Therefore:

- `PACKAGE_RELEASE=NONE`
- `candidate_release=false`
- final-ZIP self-audit: not applicable because no ZIP was generated.

## Rule feedback

`RULE_DELTA_PROPOSAL`:
`CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001`.

A cross-stage or cross-operator barrier may be credited only when the active
RTL identity decodes the emitted opcode/field into a live state transition
whose release proves all required producer writes accepted into the declared
visibility domain and outstanding zero, or a formally equivalent ordered
visibility condition. Command presence, `Start_Comp` serialization, last-data
acceptance into an ingress FIFO, or observer-only evidence must fail closed.

This is a non-synonymous rule-gap proposal. No public rule was modified.
