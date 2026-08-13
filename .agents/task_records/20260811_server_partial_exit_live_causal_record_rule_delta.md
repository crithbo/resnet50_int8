# 2026-08-11 server partial-exit live causal record rule delta

## Scope and adjudication

- Direct mainline request: adjudicate native Conv p33b external-INT evidence and, if non-synonymous, implement `CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001` for next fresh packages only.
- Decision: `NON_SYNONYMOUS_RULE_GAP`. Existing `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`, `CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001` and source-bound generation rules preserved the partial core return and isolated plugin failure, but none forbade a required causal parser from using SystemVerilog `final`-block output as its sole input.
- Blocking mapping is narrowly `return`: only a required dynamic causal parser that cannot adjudicate the required INT/TERM evidence is blocking. Non-causal/static/identity plugins may use a reasoned `NOT_APPLICABLE_NON_CAUSAL_PLUGIN`; extra formatting or performance preferences remain record-only.

## Direct evidence

- p33b source ZIP bytes `5931155`, SHA256 `62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df`.
- p33b formal return bytes `143523`, SHA256 `0d3cc837c58e1cd0eba8afdc6a03a1dd19809d9ece5493a36e6d95d6c60f022e`.
- Analysis `outputs/conv_native_four_lane_0ccae916_p33b_return_analysis/report.json`, bytes `15030`, SHA256 `9a7a96d9725404b71e2f636c14eb2140f87d846aae406cf827b4fbb6f5fa7fe9`.
- Exact mechanism: external `INT` omitted final-only `RING_POST`, while the independent core retained two exact-target qualified live `EVENT` rows proving ARM-only row2 accepts. The required `target_epoch_write_owner_parser` ignored those live rows and exited nonzero.

## Implemented contract

1. Every required plugin is covered exactly once by `LIVE_CAUSAL_FIXTURE` or reasoned `NOT_APPLICABLE_NON_CAUSAL_PLUGIN`; missing/duplicate coverage fails closed.
2. A live disposition binds the exact plugin argv, attempt input/output paths and a tiny final-ZIP fixture. The fixture contains qualified live `EVENT` or a signal-safe persisted marker, contains no `RING_POST`, and is executed from clean extraction with a maximum 30-second budget. Exit zero and valid JSON output are required.
3. Source-bound `first_payload_samples` now has minimum 1. The generated parser consumes live `EVENT` counts and sticky masks; a count observation with neither live event nor final summary remains incomplete.
4. The p33b mechanism is a permanent negative control: a RING_POST-only parser exits 9 on the live-only fixture.
5. The exact validator aggregates the fixture finding with the existing final-ZIP report. It does not require a per-finding rebuild.

## Exact current receipts

- `.agents/rules/服务器测试包生成规则.md`: bytes `137193`, SHA256 `2283153ad28ac3cfc21584ac705ef90e640bf157146153f4bc50dfd0e8f0af0e`.
- `.agents/rules/生成前必读索引.md`: bytes `28111`, SHA256 `d55645b911ae21c1e4a0b653f9c6c0c0ef12d8c1aead8f3bd27925d52734e767`.
- `.agents/rules/整网测试收敛优化专项规则.md`: bytes `17484`, SHA256 `bc0397f925ec384118292f1a98f02d0bf3eeacc95638bbfb7ef476d27e8606c9`.
- `tools/server_post_sim_return.py`: bytes `49817`, SHA256 `19bea6cc8bb5bd6247f7d2da67de3df967a562f1193c82a2f1a1ddb1ae483e6f`.
- `schemas/server_post_sim_return_contract_v1.schema.json`: bytes `4231`, SHA256 `49a8d581ba3b6cb7c1d825a98f28535ea186657a0db0a44f0fc62f94b01a7408`.
- `contracts/server_post_sim_return_next_fresh_dispatch_v1.json`: bytes `2743`, SHA256 `d3214a73fe4dc8204b62df99a6da657c77034aac00b474d44d67aee390502159`.
- `tests/test_server_post_sim_return.py`: bytes `16103`, SHA256 `ba47a0fa15e0c5d5b44b9db43debf5f1d4cede8e76a98c7721831c692951269c`.
- `schemas/server_source_bound_probe_plan_v1.schema.json`: bytes `7782`, SHA256 `39310c66cac8afecff25479fd247cacb978bbeeea0aa70ca2135ef48c73a52b0`.
- `tools/generate_server_source_bound_observer.py`: bytes `71372`, SHA256 `aeae2382354f4f14cf55b0f81db7b363220bc02326884ef31e292b534b286882`.
- `contracts/server_source_bound_observer_mechanism_registry_v1.json`: bytes `5352`, SHA256 `3a7c18707aeaa885f1bfa652c81d59788de5238c7a0b22b103cfd035e3d64fbe`.
- `tests/test_server_source_bound_observer.py`: bytes `23147`, SHA256 `c0bac4f37861246a4cd9afc23ccc7b98675d07d2a67d60a09970b977e73bf24e`.
- Machine report `outputs/conv_native_four_lane_0ccae916_p33b_return_analysis/shared_rule_delta_report.json`: bytes `5617`, SHA256 `df74c2edfe764141c67b1d242fa309ea37feecb58b522949d0d0b00f680b80cf`.

## Validation

- `py_compile` PASS for both modified shared Python tools.
- Focused post-sim/source-bound suite: `30/30 PASS`.
- Combined shared suite: `89/89 PASS` across post-sim return, source-bound observer, first-fresh extra audit, server package pipeline and triggered causal observability.
- Positive controls: live-only generated parser and exact required plugin both exit zero and emit valid decisions without any final-block row.
- Negative controls: p33b-equivalent final-ring-only parser exits 9; missing required-plugin disposition fails; `first_payload_samples=0` fails.
- `git diff --check` PASS for the touched surface.

## Migration and boundary

- Applies only to next fresh packages using the current shared helper/generator. Family owners must add the exact plugin dispositions and one tiny fixture per required dynamic causal parser, then run the final-ZIP validator once after clean extraction.
- p34b remains frozen at `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p34b_armtoken.zip`, bytes `5934761`, SHA256 `98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1`; it was not modified, revalidated or rebuilt.
- `.agents/plan.md` was not modified. No current/pending package, RTL, config, numeric, workload, timeout or server state was changed. No package was built and no server action was taken.
- Claim boundary: shared next-fresh local final-ZIP parser-input and partial-exit evidence closure only; no simulation success, natural terminal, formal D, E4 or E5 claim.
