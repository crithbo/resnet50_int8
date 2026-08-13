# Conv node0004 v53 HOLD → v59 install-subtree successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Final state: `PACKAGE_READY_NOT_RUN`
- Machine report: `outputs/conv_node0004_v53_install_subtree_successor/report.json`

## Disposition

The held `r5_n4_hw_v53_sca_cwd_fix` package was never eligible to run under
`CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`, because package-owned
run/evidence state was still assigned to the fixed result area. It is now
archived under
`artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_serialized_node0004/r5_n4_hw_v53_sca_cwd_fix/`.

Fresh identity `r5_n4_hw_v59_install_subtree` is the sole serialized-node0004
pending package. Its pickup ZIP is
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v59_install_subtree.zip`
with SHA256
`e5023a50e827ae3d4b0fc6bb9ac327c9aa38d9e72db068cc4fd567f8e76a216d`.

## Exact runtime layout

- cfg: `$server_root/install/cfg_pkg/r5_n4_hw_v59_install_subtree`
- run/evidence/compile:
  `$server_root/install/codex_runs/r5_n4_hw_v59_install_subtree/<attempt>/...`
- required pre-existing, real, non-symlink parents:
  `install`, `install/cfg_pkg`, `install/codex_runs`
- TB cwd: `$server_root`
- fixed result root:
  `/home/panqs/ndp/simresult`, final return ZIP/sidecar/atomic staging only
- NDP-root direct child name+type exact-set: unchanged in every local control

The exact final runner opened all 86 SCA input consumers from the TB cwd in
the normal/HUP/INT/TERM controls. Missing matrix, missing bitstream and wrong
prefix/external cfg mutations all fail closed. The finalizer was reached for
normal, preflight-fail, compile-fail, HUP, INT and TERM.

## Validation receipts

- deterministic double build: PASS
- family runner validator: PASS, errors=0
- shared runtime-layout validator: PASS, errors=0
- next-fresh build profile: PASS, shadow-only
- final ZIP rule self-audit: PASS, errors=0
- post-storage delivery audit: PASS, errors=0
- storage index: PASS; serialized pending exact-set is only
  `r5_n4_hw_v59_install_subtree`

The v53→v59 normalized ZIP comparison has 109 common members; 103 are
byte-equal. The only changed members are runner/README/manifest, the
package-local runtime path adapter, and the two SCA path-binding files.
Numeric/W3/qparams/tail/workload bytes/golden/observer semantics/timeout/
backpressure/functional RTL/ISA/hardware/active ndp-sim were not rebuilt or
modified.

## Run boundary

Server command:

`bash r5_n4_hw_v59_install_subtree/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`

Expected return:

`/home/panqs/ndp/simresult/r5_n4_hw_v59_install_subtree_return.zip`

No upload, server run or lease was performed. Production compile, simulation,
natural terminal, formal 320-D, E4 and E5 remain open until the formal return
is consumed.

## Rule feedback

`RULE_CONFIRMATION`: the current install-subtree, root-top-level, fixed-result
atomic-publication and final-ZIP self-audit rules were sufficient for this
mechanical successor. No non-synonymous rule delta is proposed.
