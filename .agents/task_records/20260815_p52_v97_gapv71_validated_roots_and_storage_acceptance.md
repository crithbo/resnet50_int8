# p52 / v97 / GAP v71 validated roots and storage acceptance

- date: 2026-08-15
- mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- registry epoch: 6
- server actions: none

## Native Conv p52

- Exact return integrity, package/execution/config identity, returned actual-source bytes and complete VCD streaming archive binding passed.
- Compile passed, target entered, and semantic-v5 stopped at the 3600-second wall ceiling. This is a non-natural partial execution; formal-D/E3/E4/E5 remain unproven.
- `VALIDATED_ROOT_CAUSE=MSE4_MEMORY_AG_INPUT1_BUFFER_TAG_STREAM_UNDERSUPPLIES_ONE_TUPLE`.
- Exact config selects input1 as the only buffer-mode input. Actual Memory_AG equations and dynamics prove all nine input1 writes are released and read without FIFO-full, same/gotten or keep-release loss; no tenth input1 tag/epoch tuple is supplied. Nine tuples produce 18 metadata descriptors/288 units while prepared data supplies 20x16=320 units.
- The exact upstream producer source/config mapping was not returned; no config workaround is validated. Status is `VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION`; no successor was built.
- Mainline receipt: 3741 bytes, SHA-256 `9fde9d0792e5db4f4d20c462e832889e6a1ecc108b8b945dc5360d90190c1548`.
- Formal analysis: 29340 bytes, SHA-256 `35e9b6eb6b5258e36525095e8fed0c0e4054690439c0e1b9bc6a67d8d0306ede`.
- Rule disposition: 677 bytes, SHA-256 `a84cb80986c05e1ac2c49454816e94d7f8139251a32655ae06197aeea12bdfea`; `RULE_CONFIRMATION_NO_CHANGE`.

## Serialized Conv v97

- Exact return was bounded-stream consumed through the 710 MB archive. Compile passed, target entered, and the sole evaluator stopped at the wall ceiling; process tree was fully reaped. The run was not natural and formal-D/E3/E4/E5 remain unproven.
- It independently validates the same root: input0/input2 KEEP heads remain resident; input1 is always source-ready, its split FIFO never becomes full, same/gotten never masks a token, and all nine input1 tokens form nine aggregate tuples. No tenth input1 tag/epoch tuple arrives.
- VCS normalized 51 catalogued bit identities into 17 packed vectors; the vectors exist and were decoded bitwise, so this does not require another run.
- The returned actual source does not cover the upstream LC_PE/IGA producer, so no producer line or config workaround is claimed. Status is `VALIDATED_ROOT_CAUSE_WAIT_FUNCTIONAL_FIX_AUTHORIZATION`; no successor was built.
- Mainline receipt: 4237 bytes, SHA-256 `37963bc7e8c310bb493666acf5c1e236aa28d5a2ac4c5b9d185c19095477f732`.
- Formal analysis: 21259 bytes, SHA-256 `a42ebbe038d79ed313c4e5925777811ee1458b2e90e40d69e20fe1d106df0c89`.
- Rule disposition: 915 bytes, SHA-256 `71ab328d799987ff7d8d9938129ce821f8c6d31b244cc3115be3d4a3d6aa108a`; `RULE_CONFIRMATION_NO_CHANGE`.

## GAP v71

- v71 is a valid out-of-band local diagnostic, not an accepted pending successor. Its config/mapping/numeric/workload/golden semantics remain byte-frozen from v70; it introduces no config repair.
- Dynamic config consumption remains `initial=0 / stride=16 / end=32`. v71 refines the v70 downstream overlap mechanism to the unique RTL root:
  `BUFFER_AG_IDX_QUEUE_SPLIT_AND_AGGREGATE_FIFOS_NOT_CLEARED_ON_SLICE_RST_REPLAY_STALE_PRIOR_STAGE_COLUMN_INDICES`.
- The queue's gotten/keep state uses `slice_rst`, but its row/column/aggregate FIFOs are wired only to `rst_n`. Stale sum_s1 bases 0 and 1 are emitted before fresh sum_s2 bases 0 and 16, producing the 1..16 overlap and ready-low chain on all selected slices.
- No production-equivalent config workaround is validated. No successor was built; status remains `WAIT_RTL_OR_EQUIVALENT_CONFIG_AUTHORIZATION`.
- Mainline receipt: 3355 bytes, SHA-256 `d19718f5be60da9960bcb23543008b93dc29f1b522d83c53da4048db806d832f`.
- Formal analysis: 4915 bytes, SHA-256 `e1863b3c8ca063d50b71d72fafc7e5dd2b43cb5296a3da7db249b46ea1efca6c`.

## Storage

- Native p52 was retired pending to tested with no successor.
- Serialized v97 was retired pending to tested with no successor; lifecycle receipt is 3362 bytes, SHA-256 `30643a045cd0db05625f74a05ddda911474fa836456d4ad56aad188d2bee3991`.
- GAP v71 was not inserted into managed storage.
- Corrected final audit passed at pending/tested/superseded `1/52/24`.
- Sole pending package is QAdd `r5_qadd_n7_tailround_lanephase_v68_cfg42_t2`.
- Final storage index: 419225 bytes, SHA-256 `ceeec1bcb2102cecaf5bd305acc00459b94838cdfd6197afa8af623c83ae0315`.
