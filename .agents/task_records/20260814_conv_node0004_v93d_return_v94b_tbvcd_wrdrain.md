# serialized Conv v93d return / v94b successor

- family: `conv_serialized_node0004`
- package: `r5_n4_hw_v94b_tbvcd_wrdrain`
- status: `PACKAGE_READY_NOT_RUN`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v94b_tbvcd_wrdrain.zip`
- command: `bash r5_n4_hw_v94b_tbvcd_wrdrain/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

v93d production compile/simulation和完整VCD成立；actual ACK方程6,151,454/6,151,454零矛盾。首分歧由v92的
RD_Buffer_AG/backpressure推进为`WR_Data_Channel prepared_data_count=32`后prepared backpressure及
`wr_data_chl_ready`拉低，继而RD_Buffer_AG dequeue停止。v94b保留冻结功能面，增加19个WR_Data leaf，
并使用`tb-vcd-exit-mechanism-consistency-v3`的唯一shared evaluator、四态回放、quiescent archive身份
和flush/close/reap fail-closed。

所有本地构包/最终ZIP/first-fresh/storage门通过；未执行upload、lease、connection或server run。

