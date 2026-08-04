# GAP repair candidate rules

最后更新：2026-07-24

适用范围：用户本轮明确授权的 GAP 功能 RTL repair 测试。默认路线和当前
`int32_mac` 绕行均不得启用本文件。读取集合由 `生成前必读索引.md` 的 repair profile
统一路由，不在此重复公共文件清单。

当前 repair 路线及服务器推进已按用户指示冻结；包、preimage 和原始回传只读。重新
启用必须取得新的明确授权和全新 package/install/run/return 身份。

## `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`

配置语义变化后，以本轮最终 address-bound config 为唯一输入完整重建：

```text
planner → encoder → mapping → bitstream → execplan → SCA/SCA_D
```

每个产物绑定来源、命令、路径、大小和 SHA-256。不得复用旧 execplan/SCA/bitstream；
新旧哈希相同不能代替本轮 provenance。

## `CDA-RTL-REPAIR-TRANSACTIONAL-RESTORE-001`

功能 RTL repair 必须全部满足：

1. 本地 `NDP_copy01` preimage 永久不改；
2. 包内 `rtl_patch` 使用精确 allowlist；
3. 安装前校验 canonical preimage SHA；
4. 安装前逐字节 backup，并写 install receipt；
5. 在隔离 RUN_DIR 全新 compile/sim；
6. run 后逐字节 restore，并写 restore receipt；
7. restore 后采集 post-restore identity，与 preimage 逐文件一致；
8. `EXIT/HUP/INT/TERM` trap 均尝试恢复；
9. 缺 receipt、恢复失败或身份不一致使整轮失败。

repair 文件不得写回本地 preimage，历史 allowlist 不得扩大。

## `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`

schema、通用 validator、ZIP exact-set、sidecar 和路径存在性只构成结构门。repair 必须
显式报告：

- `CDA-GAP-D-READBACK-COVERAGE-001`；
- `CDA-GA-OUTBUFFER-OCCUPANCY-001`；
- `CDA-GA-INVALID-SLOT-ISOLATION-001`；
- `CDA-GA-CROSS-BLOCK-INIT-001`；
- `CDA-MSE4-MONITOR-EVIDENCE-001`；
- `CDA-SERVER-FOCUSED-IDENTITY-001`；
- `CDA-GAP-ORTHOGONAL-DEFECTS-001`。

修复 CONFIG_SEMANTICS 或 RTL_CONTROL 中一项不得解除另一项。

## `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`

包生成阶段只允许：

```text
candidate_release=false
evidence_level=E2_LOCAL_ONLY
```

服务器 E4 必须同时满足：

1. 16 slice×512 条正式 128-bit D readback 逐行 golden；
2. 8 个普通 GA PE 全周期 `0<=count<=2`；
3. invalid-slot reuse=0；
4. 新 block 在新 partial 有效前 C=0；
5. MSE4 丢写只由 same-clock observer 或正式 readback 裁决；
6. focused identity 覆盖 pre-install、post-install、post-run、post-restore。

E4 后仍使用全新身份独立重跑形成 E5。

## `CDA-GAP-REPAIR-RETURN-RECEIPTS-001`

回传采用 allowlist-only ZIP+sidecar，必须包含：

- install/restore receipt；
- pre-install、post-install、post-run、post-restore identity；
- argv、各层退出状态和 signal；
- SCA/SCA_D、正式 D readback、必要 observer 和 manifest。

波形、build tree、完整 run/archive、重复内容和 nested archive 默认禁止。缺 restore
receipt 或 post-restore identity 时，即使数值正确也不验收。

历史候选的配置 diff、patch allowlist、ZIP 身份和本地测试结果只在对应 task record
追溯，不再进入生成前必读。
