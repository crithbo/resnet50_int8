# ADR-004：用版本化硬件批准合同自动重审G4

状态：已采用；等待硬件侧提供真实批准内容  
日期：2026-07-12

## 决定

新增严格、只读的硬件批准入口`contracts/hardware_approval.json`，并以`schemas/hardware_approval.schema.json`和`resnet50_pipeline.hardware_approval`共同约束。项目不生成示例批准文件，也不猜测任何硬件值；文件缺失或任一字段无效时，G4保持`not_passed`且W5保持未授权。

批准合同必须由可识别的批准人和组织给出，且至少冻结以下事实：

- 完整RTL commit、ISA版本、register-map版本；
- 16-slice拓扑、PE阵列、neighbor transfer数量和DRAM几何/地址单位；
- 整网采用batch、ring/channel或逐算子mixed profile，以及每类算子批准的W4 layout ID；
- activation、weight、bias、qparams、psum、output的owner、轴顺序、对齐、tail和地址单位；
- accumulator、overflow、nearest-even requant、qparams传输和psum生命周期；
- opcode、字段位宽、instruction mask以及load/start/wait/status/error/dump协议；
- 至少一条带SHA-256的原始批准证据。

## 自动门行为

`tools/audit_w4_gate.py`默认查找上述合同，也可通过`--hardware-approval`只读验证指定文件。验证结果分为：

1. 文件缺失：记录`present=false, valid=false`，原三项硬件阻塞继续存在；
2. 文件存在但不完整、含未知字段或内容不一致：记录具体错误，继续阻塞；
3. 文件严格有效：同时满足approved profile、冻结版本和approved physical layout三项硬件门槛；若其余W4回归仍通过，才令`g4_status=passed`和`w5_authorized=true`。

合同批准某个已有candidate，只表示硬件权威选中了该版本；不会回写或销毁W4候选证据。未被选择的candidate可保留用于追溯，但不得驱动W5产物。

## 为什么这一步不会因硬件定型而作废

该工作只定义真实硬件信息的接收、校验、版本追踪和门禁，不预先选择算法、tile、地址或bitstream。硬件定型后只需填入获批事实并重跑审计；如果硬件版本以后变化，则提交新的批准合同和证据，旧合同仍可用于复现旧结果。

## 当前结论

仓库中没有`contracts/hardware_approval.json`。当前正式审计仍为software candidate readiness通过、G4未通过、W5未授权；不得将测试fixture当作真实批准记录复制进合同目录。
