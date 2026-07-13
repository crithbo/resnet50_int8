# ADR-004：用版本化硬件批准合同自动重审G4

状态：已采用；门禁解释已由ADR-007与W4-28 C0覆盖更新，仍等待硬件侧真实批准
日期：2026-07-12

## 决定

新增严格、只读的硬件批准入口`contracts/hardware_approval.json`，并以`schemas/hardware_approval.schema.json`和`resnet50_pipeline.hardware_approval`共同约束。项目不生成示例批准文件，也不猜测任何硬件值；文件缺失或任一字段无效时，G4保持`not_passed`且W5保持未授权。

批准合同必须由可识别的批准人和组织给出，且至少冻结以下事实：

- 完整RTL commit、ISA版本、register-map版本；
- 28-slice拓扑、七个4-slice小环和28-slice大环的物理顺序、PE阵列、neighbor transfer数量和DRAM几何/地址单位；
- 整网采用ADR-007的精确profile28 ID（七个HIGH小环主profile或LOW 28-slice大环候选），以及每类算子批准的RTL28 layout ID；旧`batch/ring_channel/mixed`名称不再接受；
- activation、weight、bias、qparams、psum、output的owner、轴顺序、对齐、tail和地址单位；
- accumulator、overflow、nearest-even requant、qparams传输和psum生命周期；
- opcode、字段位宽、instruction mask以及load/start/wait/status/error/dump协议；
- 至少一条带SHA-256的原始批准证据。

## 自动门行为

`tools/audit_w4_gate.py`默认查找上述合同，也可通过`--hardware-approval`只读验证指定文件。验证结果分为：

1. 文件缺失：记录`present=false, valid=false`，全部当前硬件门继续阻塞；
2. 文件存在但不完整、含未知字段或内容不一致：记录具体错误，继续阻塞；
3. 文件严格有效：只证明批准结构、clean elaboration声明和目标身份可解析；还必须由current architecture登记审批所选布局为gate-eligible，并同时具备RTL28七算子族layout、28-slice 93边物理审计、28-slice profile成本及其余逻辑回归，才令`g4_status=passed`和`w5_authorized=true`。合成fixture永远只验证结构，不能授权W5。

合同批准某个已有candidate，只表示硬件权威选中了该版本；不会回写或销毁W4候选证据。ADR-007之前的全部`w4_*16*` candidate只能保留用于追溯，不能被新合同选择，也不得驱动W5产物。

## 为什么这一步不会因硬件定型而作废

该工作只定义真实硬件信息的接收、校验、版本追踪和门禁，不预先选择算法、tile、地址或bitstream。硬件定型后只需填入获批事实并重跑审计；如果硬件版本以后变化，则提交新的批准合同和证据，旧合同仍可用于复现旧结果。

## 当前结论

仓库中没有`contracts/hardware_approval.json`。C0已把schema/validator迁移到0.2/RTL28并把旧16报告隔离为legacy；当前`software_candidate_readiness=fail`、G4未通过、W5未授权，因为28算子layout、28物理93边、28 profile成本和clean elaboration/正式批准仍缺失。不得将测试fixture当作真实批准记录复制进合同目录。
