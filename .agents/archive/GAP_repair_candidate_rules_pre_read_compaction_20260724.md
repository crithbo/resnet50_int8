# 归档：精简前的 GAP repair candidate rules

本文件保留 repair_v9 的历史实例身份和精简前规则，只用于审计。

适用范围：GAP 配置语义变化、临时功能 RTL repair、服务器测试包和 E2→E5
发布流程。本文件补充而不替代：

- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/服务器测试包生成规则.md`
- `ndp-sim-ref/model_execplan/readme.md`

## 规则 ID

### `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`

配置语义发生变化后，必须以本轮 address-bound config 为唯一输入，完整重建：

`planner → encoder → mapping → bitstream → execplan → SCA/SCA_D`

每个产物必须绑定本轮来源、命令、路径、大小和 SHA-256。不得复用旧版本
execplan、SCA、SCA_D 或 bitstream；新旧文件哈希偶然相同只表示输出字节一致，不能
代替本轮 provenance。因复用 v7 execplan/SCA 而未完成完整重建的 v8 草案不得发布。

### `CDA-RTL-REPAIR-TRANSACTIONAL-RESTORE-001`

功能 RTL repair 只有在用户明确授权时才允许。必须同时满足：

1. 本地 `NDP_copy01` preimage 永久不改。
2. 包内 `rtl_patch` 使用精确文件 allowlist。
3. 安装前逐文件验证 canonical preimage hash。
4. 安装前保存逐字节 backup，并记录 install receipt。
5. 在隔离 run 目录重新 compile/sim。
6. run 后逐字节 restore，并记录 restore receipt。
7. restore 后采集 `post_restore` identity，与 preimage 逐文件核对。
8. `EXIT` trap 必须尝试恢复；任何显式恢复失败、缺 restore receipt、缺
   post-restore identity 或恢复后身份不一致，都必须使测试失败。

禁止把 repair 写回本地功能 RTL preimage，禁止扩大包内 RTL allowlist。

### `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`

通用 operator validator、ZIP exact-file-set、sidecar、路径存在性和 schema
检查只构成结构门，不构成 GAP 语义或发布门。每个 GAP repair candidate 必须显式
报告：

- `CDA-GAP-D-READBACK-COVERAGE-001`
- `CDA-GA-OUTBUFFER-OCCUPANCY-001`
- `CDA-GA-INVALID-SLOT-ISOLATION-001`
- `CDA-GA-CROSS-BLOCK-INIT-001`
- `CDA-MSE4-MONITOR-EVIDENCE-001`
- `CDA-SERVER-FOCUSED-IDENTITY-001`
- `CDA-GAP-ORTHOGONAL-DEFECTS-001`

### `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`

包生成阶段只能声明：

- `candidate_release=false`
- `evidence_level=E2_LOCAL_ONLY`

本地静态覆盖、微模型、语法检查和确定性双跑不能声明 E4/E5。服务器 E4 必须同时
通过：

1. 16 个正式 D slice，每片 512 条 128-bit readback 逐行匹配独立 golden。
2. 8 个普通 GA PE 全周期满足 `0 <= count <= 2`。
3. invalid-slot reuse 事件数为 0。
4. 新 block 在新 partial 有效前保持 `C=0`。
5. MSE4 丢写裁决使用 same-clock observer 或正式回读。
6. focused identity 覆盖 pre-install、post-install、post-run、post-restore。

E4 通过后仍必须使用全新身份独立重跑形成 E5；不得由一次运行直接升级。

### `CDA-GAP-REPAIR-RETURN-RECEIPTS-001`

服务器回传继续采用直接 ZIP 加 `.sha256` sidecar，且必须是 allowlist-only。回传
必须包含：

- RTL patch install receipt；
- RTL patch restore receipt；
- pre-install、post-install、post-run、post-restore identity；
- 运行命令与退出状态；
- 正式 D readback、必要 observer/local 日志和包 manifest。

默认禁止波形、build tree、嵌套 archive 和整个 run 目录。缺少 restore receipt 或
post-restore identity 时，即使数值正确也不得验收。

## repair_v9 当前边界

`gap_hwop0071_sum_repair_v9` 是唯一可运行候选，当前仅达到 E2：

- LC2 精确四字段修复：
  `src_id: DRAM_LC.LC0→null`、`outmost_loop: 0→1`、
  `end: 1→256`、`last_index: 1→0`。
- 16/16 slice 静态覆盖均为 256 个 32-byte transaction bases、512/512
  unique 128-bit D addresses。
- 包内 RTL allowlist 仅包含 `GA_PE_Outbuffer.sv` 和 `GA_PE_Inbuffer.sv`；
  本地 `NDP_copy01` preimage 未修改。
- ZIP SHA-256：
  `4344b4166540482d12256b1a5893b8e3dbb512a74a7d735237de0ae2bf873864`。
- E4/E5 所有服务器动态门仍待验证。
