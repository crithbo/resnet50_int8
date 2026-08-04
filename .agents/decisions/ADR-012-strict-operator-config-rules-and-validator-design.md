# ADR-012：严格算子配置规则草案与外围 validator 设计

日期：2026-07-23

状态：accepted；R2 设计已在 R4 合入活动 `.agents/rules/算子配置规则.md`。R3 的 execplan/address/SCA/qparam/layout/provenance 闭环与退出裁决见 ADR-015。本文仍不授权修改原生 `ndp-sim` 或现有候选。

依赖：ADR-010 目标身份、ADR-011 字段/RTL 真值表。

## 1. 决策

采用**外围、只读、fail-closed、分层** validator：输入是原始 JSON 及后续 mapping/bitstream/execplan/SCA/profile/provenance，输出是独立报告；validator 不 import `ndp-sim`，不写输入目录，不用原生 encoder 的成功退出代替合法性证明。

规则分为两种模式：

1. **reproduction**：精确解释 legacy JSON 的已知物理行为，允许已裁决的历史别名，例如 SA `col→bit0/不转置,row→bit1/转置`；仍拒绝未知字段、静默截断、非法 enum、悬空拓扑和不能完成的 tag 链。
2. **development**：除 reproduction 全部条件外，必须提供模型算子、dtype/qparam、输入/输出 layout、padding 值、stage DAG、地址所有权及目标 profile 合同；SA 必须显式给出 `expected_sa_transpose`。缺合同不是 warning，而是阻塞。

## 2. 校验顺序与失败语义

校验按固定层级执行，报告保存全部问题并稳定给出 `first_error`：

1. JSON 可解析、root object、schema 版本；
2. target profile 和来源身份；
3. CONFIG enable/update 状态转移；
4. 每模块 exact-key、条件必填、typed enum、arity、signed/unsigned 范围和派生字段；
5. JSON 字段到 encoded bit 的逐字段镜像，禁止默认 0、wrap、额外 chunk；
6. mapper 资源、物理可达性、producer-consumer、ping-pong、keep/last 与 completion；
7. 地址 remap、容量、对齐、padding 请求、tailing merge、alias/lifetime；
8. 算子 qparam/layout/stage DAG 合同；
9. mapping/bitstream/execplan/SCA/provenance 哈希闭包和同输入确定性。

任一 error 使报告 `valid=false`；目前不设置可被忽略的 warning。尚未实现的必需层必须在 development 模式表现为明确的“合同/证据缺失”，不能默认为通过。

## 3. 当前 JSON 层可执行规则

实现位于 `resnet50_pipeline/operator_config_validator.py`，当前已执行：

- CONFIG 四子系统 update/reuse/disable 持久状态指纹；
- DRAM/ROW/COL loop 资源、正向进度、位宽和命名；
- LC PE port schema、唯一 terminal carrier；
- read/write stream 分型 exact-key，write 拒绝 read-only padding 字段；
- mem 3 维、buffer 2 维 arity，唯一 buffer carrier；
- `idx_size`/`idx_size_log`/`total_size` 幂及 8-bit 边界；
- base address 30-bit 解析、低 4 bit 对齐、base row<6144；
- padding/tailing inclusive bounds 和禁用维 null；
- `buf_spatial_size` 1..16，stride 长度等于 size、lane 不别名；
- buffer lifetime、n2n count、SA/GA conversion 互斥；
- SA legacy label 到物理 transpose 的确定映射；
- SA B/B′ ping-pong producer 条件；
- 递归 D buffer-loop terminal tag 集合，必须含 `last_index=0`。

纯 RTL 微模型固定以下边界：

- `keep_releases = last && last_index <= threshold`；
- read 数据优先级为 padding value > tailing zero > DDR value；
- write tailing 为 old-DDR merge，不是写零；
- SA bit0 原样、bit1 转置。

## 4. 报告与命令

只读扫描命令：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\validate_operator_configs.py ndp-sim\jsons `
  --output artifacts\operator_config_validation\r3-shadow-active-jsons-20260723.json
```

exit 0 表示全部文件 valid，exit 1 表示至少一份 fail closed。报告 schema 为 `operator-config-shadow-scan-v1`，每份文件含 `first_error`、全部 issues、profile、CONFIG、stream、SA layout、completion tag 集合及 next CONFIG state。该命令只在显式 `--output` 路径创建报告，不修改源 JSON。

## 5. 初始影子结果

当前活动目录有 55 份 JSON，不是旧计划中的 54 份；增加项是 node0004 nopp R1 候选。首轮结果：

- files=55；valid=46；invalid=9；
- 55/55 的 D terminal 静态链包含 last_index=0；
- 3 份 padding 值依赖 `None→0`；
- 3 份 write stream 共含 8 个不会被 WriteStream encoder 消费的 read-only 字段；
- 3 份 stream 用整数 0 代替 typed null enum。

这三类问题正好验证外围 validator 的目的：原生 encoder 可继续并产生 bitstream，但“可编码”不等于来源明确、schema 正确或数值已验证。现阶段不自动规范化这 9 份文件，先逐类判断是否保持 legacy reproduction、修源配置并重认证，或只在开发 schema 中禁止。

## 6. 已有测试

`tests/test_operator_config_validator.py` 当前 18 项，覆盖：

- 非对称 SA label/bit/transpose；
- development layout 合同缺失与冲突；
- keep 的 `<`、`=`、`>` 边界；
- padding/tailing 同时命中的优先级；
- write tailing old-value merge；
- 真实 node0004 nopp D terminal-0；
- outmost terminal 断链负例；
- 未知字段、空间 lane 少一项、禁用 bound 非 null、write padding 字段；
- 非法地址字符串、row=6144、20-bit stride 溢出、缺 B′ producer；
- CONFIG 首 stage 复用、更新→复用→禁用→错误复用、update=0 body 漂移。

## 7. R3 实现结果

独立 encoded-bit/mapping 层见 ADR-014。它已经覆盖完整 12 类模块、真实 bit range、parsed/64b/128b 重建、mapping review 哈希、资源与 RTL 可达性，并加入 bit 篡改、silent-default、wrap、penalty、fallback、cache 和不可达连接负例。四个持久化 strict-valid 原生产物目录逐 bit 正例通过；历史目录因未保存 penalty/cache provenance 仍不能升级为完整 mapping 证明。

可移植 v2 mapping evidence bundle 已实现，三份新产物绑定初始空 cache、同次生成 cache、exact penalty、commit/source tree、source JSON、seed/命令、stdout/stderr 和核心产物哈希，并由独立镜像验收。随后已完成真实 execplan 顺序、CONFIG 状态、SCA、remap 后逐请求地址、qparam/layout/tail/stage/provenance 与持久化双跑闭环；55 份活动 JSON 均有 strict-valid 或 intentional-reject 身份。实现、数值和剩余 E4/E5 边界统一见 ADR-015。

## 8. 下一决策点

活动规则已经切换。下一决策点是 R5 的来源策略：向上游修复并更新锁定 commit，或建立明确标识的项目补丁 toolchain；在用户明确选择前不修改活动 `ndp-sim`。
