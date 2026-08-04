# Human JSON lane boundary switch receipt

## Read receipt

- `.agents/agent.md`
  - bytes: 8838
  - SHA256: `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
  - sections read: 5–7
- `.agents/plan.md`
  - bytes: 14227
  - SHA256: `81d57f8143c495b9c2d7e0a33f4eeeb3824ba1b318b03a3b3731552ce045016d`
  - read to EOF

## Active boundary

- lane: human-authored JSON consumer
- double-buffer group: C
- shared peer: operator lane 5 / Dequant task
- only server root: `NDP_copy03`
- server action without explicit mainline lease: forbidden
- group-C concurrent `SERVER_RUNNING` maximum: 1
- public plan/rules writes from this lane: forbidden
- allowed rule contribution: family task-record `RULE_DELTA_PROPOSAL`
- functional RTL and packaged `rtl/**`: forbidden
- TB/observer changes, if authorized: exact package install target only,
  transactional restore and identity gates required

## Frozen Human MAC state

- corrected-v2 remains frozen:
  SHA256 `24002ec87abd2e1c5f659003c61aa6176d2d7bd18dbfebeae890e11d80b36eb6`
- rerun monitor evidence remains frozen:
  SHA256 `515b09ca64835e500830f62b275c8c5444a26df7c8ac8fc1883141d127c99026`
- `dram_loop_configs.LC2.last_index=1`: confirmed coherent
- dynamically supported candidate delta:
  `general_array.outport.src_id: 1 → 0`
- authorization for a new corrected candidate: absent
- package generation state: stopped

## Standard future handoff

- `RETURN_ANALYSIS`
- `RULE_DELTA_PROPOSAL`
- `BLOCKER_DELTA`
- when authorized and necessary, exactly one `PACKAGE_RELEASE`

