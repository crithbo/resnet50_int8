# GAP v63 return / v69 successor

- family: `gap_node0071`
- package: `r5_n71_gap_v69_sum_s2_tbvcd_runtimev3clean`
- status: `PACKAGE_READY_NOT_RUN`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v69_sum_s2_tbvcd_runtimev3clean.zip`
- command: `bash r5_n71_gap_v69_sum_s2_tbvcd_runtimev3clean/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

v63 production compile/simulation启动且VCD/preload持续推进，但旧supervisor信任稀疏display heartbeat，在
sum_s2 target entry前误判SIM_TIME_FREEZE；没有形成新的DUT根因收窄。v69冻结v61 MAX_PROGRESS的
sum_s2 MSE0->Buffer0/GA/MSE4整锥，消费`tb-vcd-exit-mechanism-consistency-v3`，并通过19/19
package-local Python compile和schema-enabled本地门。

所有本地构包/最终ZIP/first-fresh/storage门通过；未执行upload、lease、connection或server run。

