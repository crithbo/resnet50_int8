# 2026-08-11 native Conv p36b return and corrected p37b successor

## Outcome

- Formal p36b return analysis remains valid: compile succeeded, c0 ran, and INT/130 produced a qualified partial return. Two exact 45-bit binary-known Buffer5 ARM row2 accepts have identical address/counter/tag state. Reset/wrap and advancing-token candidates are closed; complete producer data-beat identity is the first missing boundary.
- Natural terminal, c0 slice finish, 27/27, formal 320D, E3, E4 and E5 remain unclaimed.
- p37 ZIP `441da07145ee883585ff57dd8bc3320c1486dc2ea47f852759e2ff3443995e9a` is held and superseded without server execution. It overconstrained every lane's `same` bit although the public group tag uses `OR(lane_same)`.
- Fresh p37b accepts `valid && ready` per exact public lane, reconstructs `{valid_vector, OR(last), OR(same), lane0_last_index}`, and only then compares complete 256-bit beats. The legal mixed-lane positive lane0=`0x5f`, lanes1..7=`0x4f` reconstructs target tag `0x3fdf` and passes.

## Package

- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p37b_saepoch.zip`
- bytes: `5957133`
- SHA256: `d2f0bd8dd532975cebb12dab89fac8a4dbe0aa87e2a0ac6e38323ad7fedc2c80`
- Status: `PACKAGE_READY_NOT_RUN`, `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`.
- Command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p37b_saepoch_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`.

Exactly one prebuild aggregate and one final ZIP were produced. Deterministic double staging passed; all 87 workload/config payload members are byte-equal and both SCA files are identity-normalized equal. Numeric/W3/golden were not rerun and functional RTL was not modified.

## Exact gates

- Family audit PASS: `fdefadc497799dba01bd536c2b6892f43dcadab80063c5743f6e5183544f7e8d`; three positives and four fail-closed negatives.
- Typed-v2 source-bound PASS: `7bcd7485e47acd35fd4b85cd3757a3ad76db0a9fe5aced651086cec4a5aa5913`; semantic fingerprint `454d569a675d9a97eef177ff3e49f21e55c62bd0f49a2fe337e0478859f23f33`.
- Post-sim PASS: `6525c44fd2ab02e4a4662b66af9086caa6788794675bb1a435e4c9ae1d23ffd0`.
- Normal/preflight-fail/compile-fail/HUP/INT/TERM runner PASS: `5a577754bb116744650bc6023b422991859a68454f53dd84dbe34d1c718c1715`.
- Shared install-only layout PASS: `7f9e263773ac8e853acf7ba2ba130870634278fa6dd1a7e961d9d018933b1238`.
- Final audit PASS: `16fde4c7af0bbff2251fe2cb8db9f1dce414ba3f6b89d40af5c4fe6221215560`.

The exact ZIP was not rebuilt. A local runner receipt path was accidentally re-entered after its first run; the harness refused overwrite. Authoritative six-state and shared receipts were regenerated to fresh `v2` receipt paths and staged content-neutrally.

## Storage and rules

- Pre-rotation index SHA: `1988a91fc2179316d9640309f490a83e30515acc46a36e5f16ec4acaa50a2072`.
- Post-rotation index: bytes `334230`, SHA `4fd190e82d06fd0703c0ba8f095836ef0d27f244035d1c09720cec28a2981e34`; storage audit exit `0`; pending/tested/superseded=`3/106/39`.
- p37 is superseded; p37b is the sole native pending. Serialized v83b `ddfb1ce5...1c319` and QAdd v56 `78e98876...55fc` remain pending and unchanged.

`RULE_DELTA_PROPOSAL`: a parser that reconstructs an aggregate tag using an OR/reduction/selection across lanes should require a non-uniform-lane positive preserving the aggregate result. Uniform-lane positives alone missed the p37 semantic error. The p37b local permanent positive already closes this escape; the proposal does not hold p37b.

No server upload, run or lease was performed.
