# Generated heredoc/finalizer syntax escape shared gate v1

Date: 2026-08-07  
Owner task: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Input

GAP v48 returned raw simulation evidence and an atomic partial return, but the
shared EXIT/HUP/INT/TERM finalizer lost three required decision artifacts. An
outer package generator consumed the backslash in embedded Python
`+"\\n"`, leaving an unterminated string literal in the exact final runner.

- GAP v48 analysis SHA256:
  `03dc7c568ac5bfcad61967880e07e52ae8aaca31e46cfe0c071f4fc18654a0eb`
- v48鈫抳49 closure SHA256:
  `ef87a969f4e62d5f490c6e12091a6968acf93f7f8541379358deb578a4a2b520`
- current v49 ZIP SHA256:
  `eb2f5f02b3dce69aad51a3319972622b7cff8d594ef9cbf5909efb7c4114d85a`

## Rule adjudication

`RULE_CONFIRMATION`; `RULE_DELTA_PROPOSAL=NONE`.

Current rule semantics already require:

- locally discoverable syntax failures not reach the server;
- exact final-runner safe-stub execution through normal and signal finalizers;
- all declared finalizer artifacts and empty shell diagnostics;
- exact final-ZIP self-audit and fail-closed classification for a package-local
  delivery escape.

This was therefore an implementation/test omission, not a missing rule
meaning. The blocker maps narrowly to `return`: malformed fallback code can
lose canonical decisions and invalidate formal return completeness, but it
does not alter DUT simulation.

## Shared implementation

`tools/validate_server_package_runtime_layout.py` now scans the exact final-ZIP
runner and every `.sh/.bash` member:

- every generated Python heredoc body is compiled independently;
- every literal/data heredoc is enumerated, hashed and delimiter-closed;
- missing delimiter or executable syntax failure fails the final-ZIP gate;
- the report records member/body SHA, command/body lines, delimiter, syntax
  mode, pass/fail and uncovered count.

The existing `runtime_layout` registry gate remains the shared entry. Its
semantic version is raised to 3 and the blocking effect explicitly maps this
failure to required return loss.

## Controls

Real exact-ZIP regression:

- v48: expected reject, actual `pass=false`, one error; 6 heredocs found,
  5 Python compiled, 1 literal checked, failed=1, uncovered=0.
- v49: expected accept, actual `pass=true`, errors=0; 6 heredocs found,
  5 Python compiled, 1 literal checked, failed=0, uncovered=0.

The v48 error is exactly:

`generated heredoc syntax failed: PREPARE_AND_RUN.sh:134: python unterminated string literal (detected at line 16) at body line 16`

Synthetic fixtures permanently preserve both the chr(10) positive and the
v48-shaped newline escaping negative.

Validation:

- `py_compile`: PASS
- runtime-layout tests: 7/7 PASS
- runtime-layout + package-pipeline tests: 17/17 PASS
- `git diff --check`: PASS

## Outputs

Machine report:

`artifacts/operator_config_validation/r5-generated-heredoc-syntax-gate-v1/report.json`

Real receipts:

- `.../gap_v48_negative.json`
- `.../gap_v49_positive.json`

## Claim boundary

No current package was rebuilt or modified. No upload, server run, lease, RTL,
ISA, hardware, active ndp-sim, config, numeric, workload, golden, mapping,
bitstream, execplan or SCA action occurred.

