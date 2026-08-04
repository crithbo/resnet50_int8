# GAP node0071 v2 screenshot SCA path failure and v3 cwd package

## Scope

- Unique mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- Screenshot SHA-256:
  `a4a900636544d1ad49a6da8c86a27327ab49989f9c6c6aa3b8521478ed51a9db`
- Frozen source package:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.zip`
- Source package SHA-256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- No server file outside the screenshot was inspected.
- GAP sum, tail, golden and semantic configuration were not recomputed.

## RETURN_ANALYSIS

The v2 package has the correct formal identity:

```text
package/install = r5_n71_gap_v2_obs
run             = run_r5_n71_gap_v2_obs
return          = r5_n71_gap_v2_obs_return
```

Inside the ZIP, the two loader files are:

```text
r5_n71_gap_v2_obs/workload/sca_cfg.json
r5_n71_gap_v2_obs/workload/sca_cfg_D.json
```

The runner installs `workload` to:

```text
${server_root}/install/cfg_pkg/r5_n71_gap_v2_obs
```

Therefore the installed leaf expected by the screenshot is correct:

```text
/home/panqs/ndp/NDP_copy02/install/cfg_pkg/r5_n71_gap_v2_obs/sca_cfg.json
```

The failure is the simulation process working directory. Compilation uses
`make -C "$server_root"`, but that directory change applies only to `make`.
The v2 runner subsequently executes the absolute `simv` path directly without
changing its own cwd. The TB and every path inside SCA are defined relative to
the server root. If the package is launched from its extracted directory, the
TB resolves:

```text
install/cfg_pkg/r5_n71_gap_v2_obs/sca_cfg.json
```

against the package/caller cwd and fails exactly as shown.

Classification:

```text
TB_FIXED_RELATIVE_PATH_INCOMPATIBLE_WITH_PACKAGE_RUNNER_CWD
```

This is not an install namespace/leaf error and is not assigned to user command
error: the documented one-command runner is required to be independent of the
caller's cwd.

## FIRST_DIVERGENCE

```text
SCA_CFG_OPEN_FAILED_BEFORE_NUMERIC_EXECUTION
```

At `7,794,000 ps`, `tb_NDP_Top_new_phy.sv:3075/3077` cannot open the v2
`sca_cfg.json`. Generic APB initialization has already printed, but the approved
SCA preload, execplan, eight-stage `Start_Comp` sequence and formal readback have
not been established. The later `Reg Started.` and bank-frame monitor creation
are post-error prints and do not prove a successful configuration load.

This screenshot supplies no valid node0071 numeric execution evidence.

## Package-side repair

The minimal repair is runner-only:

```bash
(
  cd "$server_root"
  "$run_root/sim_results/simv" \
    +SCA_CFG="install/cfg_pkg/${install_name}/sca_cfg.json" \
    +SCA_CFG_D="install/cfg_pkg/${install_name}/sca_cfg_D.json"
)
```

A fresh identity was required because v2 is immutable and its failed server
namespace cannot be reused.

## PACKAGE_RELEASE

Fresh package:

```text
identity = r5_n71_gap_v3_cwd
status   = PACKAGE_READY_NOT_RUN
```

Artifacts:

- `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v3_cwd.zip`
- bytes: `1777317`
- SHA-256:
  `3d6c8c580e178717b1c0a9bf70f5c55fd8cbcc8a74c7e9b5673f36b743604c80`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v3_cwd.zip.sha256`
- validation:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v3_cwd.validation.json`

One command:

```bash
bash /absolute/path/to/r5_n71_gap_v3_cwd/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected return:

```text
r5_n71_gap_v3_cwd_return.zip
r5_n71_gap_v3_cwd_return.zip.sha256
```

Package validation:

- source v2 ZIP and sidecar bound;
- 119 frozen payload files exact-tree equal;
- SCA/SCA_D changed only by the fresh install namespace;
- two fresh builds produced byte-identical ZIPs;
- fresh-extract runtime preflight did not mutate the package;
- exact package file count `122`;
- preload count `25`;
- formal readback contract count `48`;
- runtime readback targets preloaded `0`;
- explicit allowlist-only return and conjunction result gate retained;
- functional RTL modified `false`;
- numeric analysis repeated `false`;
- sum/tail numeric execution repeated `false`;
- server action `false`.

## BLOCKER_DELTA

- Opened from screenshot:
  `B_GAP_NODE0071_V2_RUNNER_CWD_NOT_BOUND`.
- Closed package-side by fresh `r5_n71_gap_v3_cwd`.
- Still open: v3 server execution, natural terminal, 48-item formal readback,
  all GAP specialist dynamic gates, E4/E5, final RTL commit binding and
  production/performance/resource closure.

## RULE_DELTA_PROPOSAL

None. `CDA-SERVER-ONE-COMMAND-001`,
`CDA-SCA-D-TB-READBACK-LENGTH-001` and the existing wrong-cwd rejection already
cover this defect.

## Boundary

No plan, public rule or functional RTL was modified. No server was inspected,
uploaded to, or run. The package remains `candidate_release=false` and
`E2_LOCAL_COMPLETE_NODE`; it is not E4/E5 or production.
