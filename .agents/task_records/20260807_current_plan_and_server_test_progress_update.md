# Current plan and server-test progress update — mainline receipt

Date: 2026-08-07  
Source owner: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

The mainline plan was narrowly refreshed from the current storage index and exact
package-linked records. Existing historical plan evidence was preserved under an
explicit non-current section; current selection, progress, run order, and blockers
now bind only:

- GAP `r5_n71_gap_v50_ga_ob_conjunction_diag`: 60%
- QAdd `r5_qadd_n7_fullchain_returnfix_v46`: 70%
- serialized Conv `r5_n4_hw_v64_dskew_diag`: 70%
- native Conv `r5_n4_0cc_p18_pekeep3`: 60%

Percentages count formal server-run evidence only. Local complete JSON, package
construction, static validation, and expected wall-clock do not score.

## Current receipts

- plan SHA256:
  `af17d9c87d36ef5c16e40d31a8ae2c5afc65f4b41dd16fb95d2ce02aadf5f959`
- storage index SHA256:
  `22bf9e0d97292e88bb893b5b7eef5e880016da236e503fdcecade1984b6c0e74`
- current pointer:
  `artifacts/operator_config_validation/r5-server-package-build-control-v1/current_family_pointer_after_plan_update.json`
- pointer SHA256:
  `142ba9bda69a470739d62564b4e7cae5a8b9dbb5fc52bf53884fbdbe27e26f05`
- pointer ID:
  `d6e8eb7ce92db1da56e75cf8679cae6341bf4ca2810595bd7c7089dcd973db04`
- pointer result:
  `pass=true`, `errors=0`, `families=4`, `plan_coherent=true`
- machine progress report:
  `artifacts/operator_config_validation/r5-server-test-progress-v1/report.json`
  SHA256:
  `bd95ff2818f50ba7ea8cb71ed544e440515b5774a650c5801d75c1c6fe2dd067`

## Fresh correction consumed

The superseding exact ZIP receipts are:

- GAP:
  `122257a3b7441e9af2a036f8d8fff1bb7339f014f9c6177f607587525ef359d3`
- QAdd:
  `913e6831d47b9673f4c50e0efe28ba95fce14a2b685278c9e19755c5797f113a`
- serialized Conv:
  `c78e62cde4f8e185f801900773117017982920b9a479996a1c31af8a1dae1e96`
- native Conv:
  `b9dfb0d282013e45328c905c19957523afba81d505bbf5b4600dc82ace6c3611`

p16 was subsequently consumed as a formal package-local compile-failure return. The
current native package is now p17:

- native Conv p17:
  `3828628f2573c3cd970330fba60bd3393b305555085c5517ea074a919f40a978`

Native Conv p17 was subsequently consumed as a formal production compile/simulation
return. It closed the static-generate XMR escape and uniquely localized the current
c0 stall to `PE1.inport0.keep_last_index=2` versus terminal index 3. The current
package is the single-leaf config successor p18:

- native Conv p18:
  `381e0d8597e72350d5403b73c98ea4d5986d220481cf643b188252b34286eada`

GAP v48 was subsequently consumed as a formal interrupted-after-qualified-stall return.
The current GAP package is now v49:

- GAP v49:
  `eb2f5f02b3dce69aad51a3319972622b7cff8d594ef9cbf5909efb7c4114d85a`

GAP v49 was subsequently consumed as a formal interrupted return with qualified
progress through all-slice MSE4 request queue writes. It narrowed the first
divergence to slices 1–15 lacking GA outbuffer reads and exposed a package-local
signal-finalizer decision artifact without establishing a config or RTL root cause.
The current GAP package is v50:

- GAP v50:
  `e0eb03f4cba385e054b280c1e3915765a7465bb17f359bf7048669a6951a1c5a`

serialized Conv v61 was subsequently consumed as a formal config-root-cause return.
The current serialized package is now v62:

- serialized Conv v62:
  `613eb2a6e4dc14f65065c1a4cd880f0f42828b25a6ebde8383ae78f6d2bdec40`

serialized Conv v62 was then attempted by the user but exited immediately without
an error line or a server exit receipt. Static analysis proved package-owned silent
nonzero exits, but could not identify the exact dynamic branch. No DUT evidence or
progress points were added. The current package is the runner-visibility-only v63
successor, with the v62 PE keep config fix and all functional assets frozen:

- serialized Conv v63:
  `99f50faeed69d89cff3211121661b5331a9e98d8135064b41b76203f7c277712`

Serialized Conv v63 was subsequently consumed as a formal compile/run=0/0 return.
It closed runner-error visibility and dynamically proved the PE keep index-3 fix.
The new first divergence is a two-group skew between 20 prepared data groups and
18 write descriptors. The current diagnostic successor is v64:

- serialized Conv v64:
  `e2ad1cbb94bec3379b5a810352cdfe8d9d5cfa17f2870696a862650b593d7e25`

QAdd v45 was subsequently consumed as a formal external-HUP partial return. It
closed package/install/compile/simulation/op_a_dequant-start and exposed 37
package-local return-contract omissions without establishing a functional
config, numeric, or RTL root cause. The current QAdd package is now the
runner/return-evidence-only v46 successor:

- QAdd v46:
  `58f5204886fef6015501dedc7e4443936c8ba118be248d12c102b46bf5afa3c5`

Earlier source plan/report/task SHAs are superseded. The source worktree's corrected
plan/report were consumed semantically; mainline regenerated its pointer because its
plan deliberately preserves parallel historical content.

## Boundary

No ZIP or package was generated or modified. No server upload, run, or lease occurred.
No RTL, active ndp-sim, config, numeric, workload, golden, mapping, bitstream, execplan,
or SCA asset was changed.
