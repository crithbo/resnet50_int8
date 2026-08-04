# Human-authored JSON lane long-term boundary receipt

## Current-disk read receipt

All listed files were read to EOF for this boundary refresh.

| File | Bytes | SHA256 |
|---|---:|---|
| `.agents/agent.md` | 8838 | `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0` |
| `.agents/plan.md` | 15541 | `0914c90145b81e360754621730ff59cf5f8bb8b0400349314a98c818531aecfe` |
| `.agents/rules/生成前必读索引.md` | 5650 | `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7` |
| `.agents/rules/算子配置规则.md` | 12450 | `f7e3f80e7fb4edd2b42d7ff41a70bba55abfde6797013648dfedccdc6385e023` |
| `.agents/rules/NDP硬件字段语义.md` | 13225 | `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59` |
| `.agents/rules/服务器测试包生成规则.md` | 18061 | `f3fe8dd18c9e2009db4a2736c6c1e86841760d8ec023bb7b57562f27f5faff04` |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | 5461 | `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7` |
| `.agents/rules/GAP_int32_mac_bypass_rules.md` | 5417 | `f53fecb9106705d113354b4ab81356cbdc8179e602b2f7e584390bafe57e67a8` |

Actual native consumers also read to EOF:

| File | Bytes | SHA256 |
|---|---:|---|
| `ndp-sim/model_execplan/main.py` | 7346 | `661623ebf37f0c2fe31a530fc53c756e58408000a371d7cc528301314a4dac7e` |
| `ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py` | 11797 | `1e59210c4401dbe6c694ffdb34939531238c0e3c949ff965a3f74667eb46cfae` |
| `ndp-sim/model_execplan/src/execution_plan_generator/json_loader.py` | 19576 | `f1f6e0316812ebc8382f445b780e3143383ea0c034485d4393711302ab691ffc` |
| `ndp-sim/model_execplan/src/execution_plan_generator/address_planner.py` | 30150 | `2208ffa925c509d2479e2763f323551a36e1b6c1680a112e7519f6356a312ea0` |
| `ndp-sim/model_execplan/src/execution_plan_generator/output_writer.py` | 48029 | `434dde3c5a34ab8f3992095771876e7fad56e443eec08eb469c093b30f87beae` |
| `ndp-sim/bitstream/main.py` | 13598 | `067723b4ef118932b3a69623fa8bb4f2ed70d06eda3a5a24886c9562611ff415` |
| `ndp-sim/bitstream/parse.py` | 22540 | `a6bd0f9dc288b518389a677570cf34a08ebec72a430e9a85c085570d3be869f0` |
| `ndp-sim/bitstream/config/mapper.py` | 68728 | `c7685cc297e4e11ccafa23758a46d20986e5db931fcb3c4e21f5f4a0a2534226` |
| `ndp-sim/bitstream/config/general.py` | 11738 | `eb9d5ee9ef273182e05b718aca378f87d0a1ccb5366ae463d8482c8c94c3482f` |

## Effective long-term contract

### Input authority

- Consume only a user-specified human-authored JSON or an explicitly
  user-authorized corrected candidate.
- Bind one operator family/representative instance per task lifecycle.
- Preserve the original read-only with absolute/repository path, bytes,
  SHA256, and `human_authored_input=true`.
- Trusted native configurations are oracle evidence only; no silent
  substitution, splicing, or repair.
- Diagnose fields first. A corrected candidate requires explicit user
  authorization, a new identity, preserved original, and exact diff.

### Generation and evidence

- Before each generation/rebuild, reread the current mandatory rules,
  target-specific rules, and actual consumers and record real hashes.
- Reverse the candidate into stage, occurrence, bank/address, buffer
  supply-demand, tag/last, lifetime, LC backpressure, MSE, GA, and SA
  contracts before invoking the native planner/mapper/encoder/execplan/SCA
  chain.
- No hand-built bitstream and no unrelated derived-artifact reuse.
- Keep LOCAL_E2, structural oracle, CGRA_SIM, diagnostic observer, formal D,
  E4, and E5 claims separate.
- Without a same-gate passing baseline, use first-failure/no-baseline
  language, not regression.
- Missing sidecar, exit receipt, result gate, identity, or a truncated
  snapshot fails closed.

### Write and package boundary

- Do not modify `.agents/plan.md`, `.agents/rules/**`, other-family assets,
  functional RTL, or any `rtl/**`.
- Submit only task records, machine analyses, `RULE_DELTA_PROPOSAL`,
  `BLOCKER_DELTA`, and when authorized one `PACKAGE_RELEASE`.
- Prior public-rule edits remain for mainline review and are not reverted;
  no further direct public-rule edits are permitted.
- Any allowed TB/observer operation targets only the exact package-installed
  file and requires transactional backup/install/compile/run/restore plus
  pre/post/post-run/post-restore identities.
- No force/deposit and no change to DUT stimulus, handshake, completion, or
  timeout.
- Package has zero `rtl/**` entries, deterministic ZIP plus sidecar, and an
  allowlist-only return.
- Perform one complete pre-delivery self-check, not repeated full validation
  during intermediate edits.

### Server schedule

- Fixed double-buffer group: C.
- Only server root: `NDP_copy03`.
- Shared with the Dequant/operator lane assigned to group C.
- Mainline lease is mandatory for upload or execution.
- Group C permits at most one `SERVER_RUNNING`.
- No root takeover before restore/finalizer completion.
- At this receipt, all groups have no active `SERVER_RUNNING` lease.

### Standard mainline handoff

- package/return ZIP identity;
- exit state and natural-completion state;
- stock-RTL identity;
- last trusted boundary and first divergence;
- formal D and observer adjudicated separately;
- `BLOCKER_DELTA`;
- `RULE_DELTA_PROPOSAL`;
- if needed and authorized, exactly one minimal `PACKAGE_RELEASE` with one
  command, sidecar, and one pre-delivery self-check.

## Frozen Human MAC state

- corrected-v2 SHA256:
  `24002ec87abd2e1c5f659003c61aa6176d2d7bd18dbfebeae890e11d80b36eb6`
- rerun monitor ZIP SHA256:
  `515b09ca64835e500830f62b275c8c5444a26df7c8ac8fc1883141d127c99026`
- `dram_loop_configs.LC2.last_index=1`: confirmed correct.
- dynamically supported candidate delta:
  `general_array.outport.src_id: 1 → 0`.
- authorization for a new corrected candidate: absent.
- current action: assets frozen; no successor generation.

