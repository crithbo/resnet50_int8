# QLinearAdd node0007 split-C pair-matrix v29 package release

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN`
- claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_c_pairmatrix_v29.zip`
- ZIP bytes/SHA: `26171333 / c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3`
- sidecar SHA: `6b0cedd99f7ef2017f5248a3a07bdfcdab46b734c5813e2b79753e5fff461720`
- command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02`
- expected return: `r5_qadd_n7_split_c_pairmatrix_v29_return.zip`
- final audit SHA: `ab4e48f1ffeb117414063663380c1e966dc53aef24bbfaaef70d9df9db1cbde2`
- HDL scope SHA: `b03a957385183804530111f34e776f43919327017c3a83fccdc3a484860d4532`
- FINAL_ZIP_RULE_SELF_AUDIT_PASS: true; errors: 0
- safe compile / EXIT / TERM / wrong identity exits: `86 / 125 / 125 / 5`

V29 fixes the v28 cross-stage observer defect by tracking `EXEC_START`
deassertion outside `return_obs_active`, resetting counters on each stage, and
allowing ingress counts/snapshots only at exact `stage_seq=4`. Its canonical
parser fails closed for any other stage.

One low-rate package now discriminates MSE0/MSE1 index starvation, Buffer0/2
delivery stalls, GA operand asymmetry, tag/mask pairing rejection and output
stall. Qualified counters remain in `clk_sg`; snapshots use `clk_db`; levels
never count as progress.

The cumulative prefix is retained because there is no legally bound,
byte-exact hardware-produced A/B/relocation checkpoint chain. No host replay,
timeout extension, numeric/workload recomputation or functional RTL change was
made.
