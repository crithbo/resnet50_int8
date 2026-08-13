#!/usr/bin/env python3
"""Build the fresh v57g runner/return-only successor from exact v57f."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_qadd_n7_tailround_lanephase_qual_v57f"
TARGET = "r5_qadd_n7_tailround_lanephase_qual_v57g"
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_SHA = "eeb922f3828b0e1dd6532bf0903e516351f0a4a0a9a0439b917e8e1b2532415e"
SOURCE_BYTES = 70704126
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57g-package"
OUT_ZIP = LOCAL / f"{TARGET}.zip"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
THREAD_ID = "019ff02d-9e93-7d61-8c98-c928fdea157c"
MAINLINE_THREAD_ID = "019ff027-e7db-72a3-b282-cfad8708da05"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}
TEXT_SUFFIXES = {".json", ".txt", ".md", ".py", ".sh", ".sv", ".svh", ".v", ".vh"}
FROZEN_PREFIXES = (
    "workload/",
    "validation/",
    "tb_probe/",
    "diagnostics/source_bound_probe_plan.json",
    "diagnostics/source_bound_probe_binding.json",
    "package_tools/source_bound_causal_parser.py",
    "package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py",
)
COMPILE_EVIDENCE = (
    "compile_argv.json",
    "compile_source_identity.json",
    "compile_exit.txt",
    "compile_driver.log",
    "compile_first_error.txt",
    "compile_log_head.txt",
    "compile_log_tail.txt",
    "compile_downstream_state.json",
    "package_preflight.json",
    "installed_preflight.json",
    "runtime_layout_receipt.json",
    "ndp_root_toplevel_pre.json",
    "fixed_result_preflight.json",
)


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError(f"JSON root must be an object: {path}")
    return value


def records(package: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if relative != "TEST_PACKAGE_MANIFEST.json":
            result[relative] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha(path),
            }
    return result


def extract_source(destination: Path) -> Path:
    if not SOURCE.is_file() or SOURCE.stat().st_size != SOURCE_BYTES or sha(SOURCE) != SOURCE_SHA:
        raise BuildError("exact v57f source ZIP identity differs")
    with zipfile.ZipFile(SOURCE) as archive:
        infos = archive.infolist()
        if archive.testzip() is not None:
            raise BuildError("exact v57f source ZIP fails CRC")
        names: set[str] = set()
        roots: set[str] = set()
        for info in infos:
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in info.filename
                or info.filename in names
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            if member.parts:
                roots.add(member.parts[0])
            names.add(info.filename)
        if roots != {SOURCE_ID}:
            raise BuildError(f"exact v57f source root differs: {sorted(roots)}")
        archive.extractall(destination)
    source = destination / SOURCE_ID
    target = destination / TARGET
    source.rename(target)
    return target


def protected_snapshot(package: Path) -> dict[str, bytes]:
    return {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.relative_to(package).as_posix().startswith(FROZEN_PREFIXES)
    }


def replace_identity(package: Path) -> None:
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_ID in text:
            path.write_text(
                text.replace(SOURCE_ID, TARGET),
                encoding="utf-8",
                newline="\n",
            )


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise BuildError(f"runner block start differs: {start[:80]!r}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise BuildError(f"runner block end differs: {end[:80]!r}")
    end_index += len(end)
    return text[:start_index] + replacement + text[end_index:]


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = 'attempt="a$$"\n'
    if text.count(anchor) != 1:
        raise BuildError("runner attempt initialization anchor differs")
    text = text.replace(anchor, anchor + "bootstrap_root=\n", 1)

    tools = "for tool in python3 timeout make date tail grep; do"
    if text.count(tools) != 1:
        raise BuildError("runner tool preflight anchor differs")
    text = text.replace(tools, "for tool in python3 timeout make date tail head grep cp; do", 1)

    stage_anchor = '  python3 - "$stage" "$return_zip" "$install_name" <<\'PY\'\n'
    if text.count(stage_anchor) != 1:
        raise BuildError("minimal return publisher anchor differs")
    copy_lines = "".join(
        f'  [ -z "$bootstrap_root" ] || [ ! -f "$bootstrap_root/{name}" ] || cp -- "$bootstrap_root/{name}" "$stage/{name}"\n'
        for name in COMPILE_EVIDENCE
    )
    text = text.replace(stage_anchor, copy_lines + stage_anchor, 1)
    manifest_start = 'manifest={"schema":"server-partial-return-v1","install_name":ident,\n'
    manifest_end = '(stage/"RETURN_MANIFEST.json").write_text(json.dumps(manifest,sort_keys=True)+"\\n")'
    minimal_manifest = (
        'present=sorted(p.name for p in stage.iterdir() if p.is_file())\n'
        'manifest={"schema":"server-partial-return-v1","install_name":ident,\n'
        '"classification":"PRECHECK_OR_COMPILEFAIL_PARTIAL_RETURN",\n'
        '"allowlist":present+["RETURN_MANIFEST.json"]}\n'
        '(stage/"RETURN_MANIFEST.json").write_text(json.dumps(manifest,sort_keys=True)+"\\n")'
    )
    text = replace_block(text, manifest_start, manifest_end, minimal_manifest)

    finalize_anchor = '  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] &&      [ -n "$run_root" ] && [ -d "$run_root" ]; then\n'
    if text.count(finalize_anchor) != 1:
        raise BuildError("runner finalizer branch anchor differs")
    collect_lines = "".join(
        f'  [ -z "$bootstrap_root" ] || [ ! -f "$bootstrap_root/{name}" ] || [ -z "$evidence_root" ] || [ ! -d "$evidence_root" ] || cp -- "$bootstrap_root/{name}" "$evidence_root/{name}"\n'
        for name in COMPILE_EVIDENCE
    )
    text = text.replace(finalize_anchor, collect_lines + finalize_anchor, 1)

    layout_anchor = 'compile_root="$COMPILE_ROOT"\n'
    if text.count(layout_anchor) != 1:
        raise BuildError("runner compile-root anchor differs")
    bootstrap_setup = (
        'bootstrap_root="$server_root/install/codex_runs/$package_id/.compile-return-$return_tag"\n'
        '[ ! -e "$bootstrap_root" ] || runner_fail 14 "bootstrap compile-return root already exists"\n'
        'mkdir -p -- "$bootstrap_root" || runner_fail 14 "bootstrap compile-return root cannot be created"\n'
        '[ -d "$bootstrap_root" ] && [ -w "$bootstrap_root" ] || runner_fail 14 "bootstrap compile-return root is not writable"\n'
    )
    text = text.replace(layout_anchor, layout_anchor + bootstrap_setup, 1)

    compile_start = "printf 'timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile"
    compile_end = '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; see compile_driver.log"'
    evidence_names = " ".join(COMPILE_EVIDENCE)
    compile_block = r'''compile_argv=(timeout --foreground --signal=TERM --kill-after=30s 2h
  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0
  TB_DUMP_FSDB=0 "RUN_DIR=$compile_root"
  "VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE $package_root/tb_probe/source_bound_causal_observer.svh")
python3 - "$bootstrap_root/compile_argv.json" "$server_root" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
target=pathlib.Path(sys.argv[1]); cwd=sys.argv[2]; argv=sys.argv[3:]
target.write_text(json.dumps({"schema":"server-exact-compile-argv-v1","cwd":cwd,"argv":argv,"makefile":"Makefile.tb_NDP_Top_new_phy","target":"compile"},sort_keys=True)+"\n")
PY
python3 - "$bootstrap_root/compile_source_identity.json" "$server_root/Makefile.tb_NDP_Top_new_phy" "$source_bound_observer" "$package_root/tb_probe" <<'PY'
import hashlib,json,pathlib,sys
def record(path):
    path=pathlib.Path(path)
    row={"path":str(path),"exists":path.is_file()}
    if path.is_file():
        data=path.read_bytes(); row.update({"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()})
    return row
tree=pathlib.Path(sys.argv[4])
files=[record(path) for path in sorted(tree.rglob("*")) if path.is_file()]
value={"schema":"server-compile-source-identity-v1","makefile":record(sys.argv[2]),"explicit_package_source":record(sys.argv[3]),"package_include_tree":{"path":str(tree),"files":files}}
pathlib.Path(sys.argv[1]).write_text(json.dumps(value,sort_keys=True)+"\n")
PY
for receipt_name in package_preflight.json installed_preflight.json runtime_layout_receipt.json ndp_root_toplevel_pre.json fixed_result_preflight.json; do
  [ ! -f "$evidence_root/$receipt_name" ] || cp -- "$evidence_root/$receipt_name" "$bootstrap_root/$receipt_name"
done
cat >"$bootstrap_root/compile_downstream_state.json" <<'EOF'
{"schema":"server-compile-downstream-state-v1","compile_succeeded":false,"simulation_started":false,"sim_log":"placeholder-only-until-compile-success","formal_D":"not-produced-before-simulation"}
EOF
printf '%s\n' "${compile_argv[*]}" >"$evidence_root/actual_compile_argv.txt"
printf 'RUNTIME_LAYOUT_COMPILE_START\n' >"$evidence_root/compile_started.marker"
cd "$server_root"
set +e
"${compile_argv[@]}" >"$bootstrap_root/compile_driver.log" 2>&1
compile_status=$?
printf '%s\n' "$compile_status" >"$bootstrap_root/compile_exit.txt"
head -n 200 "$bootstrap_root/compile_driver.log" >"$bootstrap_root/compile_log_head.txt"
tail -n 200 "$bootstrap_root/compile_driver.log" >"$bootstrap_root/compile_log_tail.txt"
python3 - "$bootstrap_root/compile_driver.log" "$bootstrap_root/compile_first_error.txt" <<'PY'
import pathlib,re,sys
source=pathlib.Path(sys.argv[1]).read_text(encoding="utf-8",errors="replace").splitlines()
patterns=(r"(?i)(^|\s)(error|fatal)(\s|:|\[)",r"(?i)no rule to make target",r"(?i)not found",r"(?i)syntax error")
first=next((line for line in source if any(re.search(pattern,line) for pattern in patterns)),"NO_COMPILER_ERROR_PATTERN_FOUND")
pathlib.Path(sys.argv[2]).write_text(first[:8192]+"\n",encoding="utf-8")
PY
cp -- "$bootstrap_root/compile_driver.log" "$compile_root/sim_results/compile_driver.log"
for bootstrap_name in ''' + evidence_names + r'''; do
  [ ! -f "$bootstrap_root/$bootstrap_name" ] || cp -- "$bootstrap_root/$bootstrap_name" "$evidence_root/$bootstrap_name"
done
[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; bootstrap root-cause evidence is return-allowlisted"
'''
    text = replace_block(text, compile_start, compile_end, compile_block.rstrip("\n"))
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_return_contracts(package: Path) -> None:
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = load_json(request_path)
    entries = request.get("core_entries")
    if not isinstance(entries, list):
        raise BuildError("post-sim core_entries differs")
    by_archive = {
        str(row["archive"]): row
        for row in entries
        if isinstance(row, dict) and isinstance(row.get("archive"), str)
    }
    by_archive.pop("runs/compile_driver.log", None)
    for name in COMPILE_EVIDENCE:
        by_archive[f"evidence/{name}"] = {
            "source_root": "attempt",
            "source": f"evidence/{name}",
            "archive": f"evidence/{name}",
            "required": name in {
                "compile_argv.json",
                "compile_source_identity.json",
                "compile_exit.txt",
                "compile_driver.log",
                "compile_first_error.txt",
                "compile_log_head.txt",
                "compile_log_tail.txt",
                "compile_downstream_state.json",
            },
        }
    request["core_entries"] = list(by_archive.values())
    request["claim_boundary"] = (
        "Runner/return-only compile-failure root-cause evidence plus the frozen isolated "
        "tail_round diagnostic; no producer/full-chain/E3/E4/E5 claim."
    )
    write_json(request_path, request)

    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = load_json(contract_path)
    contract["request_sha256"] = sha(request_path)
    contract["claim_boundary"] = request["claim_boundary"]
    write_json(contract_path, contract)


def write_runner_contract(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    variables = [
        "install_name",
        "package_id",
        "return_tag",
        "result_root",
        "return_zip",
        "return_sha",
        "package_root",
        "runtime",
        "base_runtime",
        "root_guard",
        "layout_helper",
        "post_sim_helper",
        "post_sim_request",
        "source_bound_observer",
        "source_bound_decision_name",
        "return_finalizer_state_name",
        "compile_status",
        "simulation_status",
        "simulation_started",
        "signal_name",
        "finalized",
        "sim_pid",
        "sampler_pid",
        "server_root",
        "cfg_root",
        "run_root",
        "evidence_root",
        "compile_root",
        "attempt",
        "bootstrap_root",
        "source_bound_filtered_log",
    ]
    contract = {
        "schema": "server-runner-return-resilience-contract-v1",
        "package_id": TARGET,
        "runner_path": f"{TARGET}/PREPARE_AND_RUN.sh",
        "runner_sha256": sha(runner),
        "nounset_required": True,
        "package_owned_variables": variables,
        "bootstrap_root_variable": "bootstrap_root",
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"],
        "first_fallible_tokens": ["compile_argv=(timeout"],
        "compile_evidence_tokens": {
            "argv": "compile_argv.json",
            "source_identity": "compile_source_identity.json",
            "exit_code": "compile_exit.txt",
            "driver_log": "compile_driver.log",
            "first_error": "compile_first_error.txt",
            "bounded_head": "compile_log_head.txt",
            "bounded_tail": "compile_log_tail.txt",
        },
        "return_allowlist_tokens": list(COMPILE_EVIDENCE[:8]),
    }
    write_json(
        package / "contracts/server_runner_return_resilience_contract.json",
        contract,
    )


def patch_layout(package: Path) -> None:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = load_json(path)
    projected = contract["path_budget"]["additional_projected_paths"]
    bootstrap_log = f"install/codex_runs/{TARGET}/.compile-return-<execution>/compile_driver.log"
    if bootstrap_log not in projected:
        projected.append(bootstrap_log)
    write_json(path, contract)


def patch_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load_json(path)
    manifest.update(
        {
            "schema": "qlinearadd-node0007-tailround-lanephase-server-package-v57g",
            "package_id": TARGET,
            "install_name": TARGET,
            "first_fresh_extra_audit": {
                "epoch_id": EPOCH,
                "notification_acknowledged": True,
                "first_fresh_after_change": True,
                "bound_package_id": TARGET,
                "prior_first_fresh_pass_receipt": None,
                "upload_hold_until_final_audit_pass": True,
            },
            "source_assets": {
                **manifest.get("source_assets", {}),
                "v57f_exact_source_zip": {
                    "path": SOURCE.relative_to(ROOT).as_posix(),
                    "bytes": SOURCE_BYTES,
                    "sha256": SOURCE_SHA,
                },
            },
            "successor": {
                "source": SOURCE_ID,
                "source_sha256": SOURCE_SHA,
                "classification": "RUNNER_RETURN_ONLY_SUCCESSOR",
                "reason": (
                    "v57f predates the active compile-failure bootstrap/core-return contract"
                ),
                "changed_surface": [
                    "fresh identity",
                    "runner bootstrap compile evidence",
                    "compile-failure core/minimal return allowlist",
                    "runner resilience machine contract",
                ],
                "frozen_surface": [
                    "workload/config/numeric/golden modulo fresh identity tokens",
                    "source-bound observer/logger/parser semantics modulo fresh identity tokens",
                    "2h compile and simulation timeout",
                    "functional RTL",
                ],
            },
            "runner_only_successor": {
                "source_package_id": SOURCE_ID,
                "source_zip_sha256": SOURCE_SHA,
                "config_numeric_workload_rtl_frozen": True,
                "server_action": False,
            },
            "rule_change_ack": {
                "epoch_id": EPOCH,
                "first_fresh_after_change": True,
                "prior_first_fresh_pass_receipt_sha256": None,
                "upload_hold_until": "FIRST_FRESH_EXTRA_AUDIT_PASS",
            },
            "rule_receipts": {
                name: {
                    "path": rule.relative_to(ROOT).as_posix(),
                    "bytes": rule.stat().st_size,
                    "sha256": sha(rule),
                    "current_match": True,
                }
                for name, rule in RULES.items()
            },
            "release_gate_matrix": [
                {
                    "gate_id": "package_identity_bootstrap",
                    "applicable": True,
                    "reason": "fresh identity and exact final ZIP",
                    "changed_surface": ["identity", "runner bootstrap evidence root"],
                    "evidence": ["exact clean extract", "manifest exact-set", "deterministic double build"],
                    "blocking": True,
                },
                {
                    "gate_id": "actual_runner_control_flow",
                    "applicable": True,
                    "reason": "runner and compile-failure finalization changed",
                    "changed_surface": ["PREPARE_AND_RUN.sh"],
                    "evidence": ["server runner return resilience exact-ZIP validator"],
                    "blocking": True,
                },
                {
                    "gate_id": "package_local_hdl_compile_readiness",
                    "applicable": False,
                    "reason": "package-local HDL is identity-normalized byte-equal to v57f",
                    "changed_surface": [],
                    "evidence": ["frozen-surface byte comparison", "source-bound exact generation"],
                    "blocking": False,
                },
                {
                    "gate_id": "materialized_config_consumer_contract",
                    "applicable": False,
                    "reason": "no functional config/workload change",
                    "changed_surface": [],
                    "evidence": ["identity-normalized workload/config byte equality"],
                    "blocking": False,
                },
                {
                    "gate_id": "observer_canonical_contract",
                    "applicable": False,
                    "reason": "observer/parser semantics are identity-normalized byte-equal",
                    "changed_surface": [],
                    "evidence": ["source-bound exact final-ZIP semantic controls"],
                    "blocking": False,
                },
                {
                    "gate_id": "return_result_conjunction",
                    "applicable": True,
                    "reason": "compile-failure return allowlist changed",
                    "changed_surface": ["post-sim request", "minimal return"],
                    "evidence": ["post-sim exact final-ZIP scenarios", "compile evidence tokens"],
                    "blocking": True,
                },
                {
                    "gate_id": "numeric_golden",
                    "applicable": False,
                    "reason": "numeric/golden bytes frozen",
                    "changed_surface": [],
                    "evidence": ["frozen-surface byte comparison"],
                    "blocking": False,
                },
                {
                    "gate_id": "first_fresh_extra_audit",
                    "applicable": True,
                    "reason": "first qlinearadd package under the active runner/compilefail epoch",
                    "changed_surface": ["runner", "return"],
                    "evidence": ["independent first-fresh exact final-ZIP audit"],
                    "blocking": True,
                },
            ],
            "final_zip_rule_self_audit": {
                "required": True,
                "status": "PENDING_EXACT_ZIP_AND_FIRST_FRESH_AUDIT",
            },
            "provenance": {
                "analysis_owner_thread": THREAD_ID,
                "return_target_thread": MAINLINE_THREAD_ID,
                "generator": Path(__file__).relative_to(ROOT).as_posix(),
            },
        }
    )
    manifest["files"] = records(package)
    write_json(path, manifest)


def verify_frozen_surface(package: Path, before: dict[str, bytes]) -> dict[str, Any]:
    after_paths = {
        path.relative_to(package).as_posix(): path
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.relative_to(package).as_posix().startswith(FROZEN_PREFIXES)
    }
    errors: list[str] = []
    if set(before) != set(after_paths):
        errors.append("protected exact-set differs")
    identity_changed: list[str] = []
    exact_equal: list[str] = []
    for relative in sorted(set(before) & set(after_paths)):
        expected = before[relative].replace(SOURCE_ID.encode("ascii"), TARGET.encode("ascii"))
        actual = after_paths[relative].read_bytes()
        if actual != expected:
            errors.append(f"protected bytes differ beyond identity: {relative}")
        elif actual == before[relative]:
            exact_equal.append(relative)
        else:
            identity_changed.append(relative)
    return {
        "schema": "qlinearadd-node0007-v57g-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "source_package_id": SOURCE_ID,
        "target_package_id": TARGET,
        "source_zip_sha256": SOURCE_SHA,
        "protected_file_count": len(before),
        "exact_byte_equal_count": len(exact_equal),
        "identity_only_change_count": len(identity_changed),
        "identity_only_changed_files": identity_changed,
        "config_numeric_workload_rtl_changed": False if not errors else None,
        "claim_boundary": "Identity-token normalization only; no server or numeric execution claim.",
    }


def build_tree(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = extract_source(destination)
    before = protected_snapshot(package)
    replace_identity(package)
    patch_runner(package)
    patch_return_contracts(package)
    patch_layout(package)
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nFresh v57g changes only package identity and runner/return compile-failure evidence. "
        "Functional config, workload, numeric/golden, diagnostic semantics and RTL remain frozen.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_runner_contract(package)
    frozen = verify_frozen_surface(package, before)
    if not frozen["pass"]:
        raise BuildError(f"frozen surface differs: {frozen['errors']}")
    patch_manifest(package)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest["files"] = records(package)
    write_json(manifest_path, manifest)
    return package, frozen


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            member = f"{TARGET}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(member, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    required = [SOURCE, *RULES.values()]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise BuildError(f"missing inputs: {missing}")
    if LOCAL.exists():
        raise BuildError(f"fresh output directory required: {LOCAL}")
    LOCAL.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="q57ga-") as first, tempfile.TemporaryDirectory(prefix="q57gb-") as second:
        package_a, frozen_a = build_tree(Path(first))
        package_b, frozen_b = build_tree(Path(second))
        zip_a = Path(first) / f"{TARGET}.zip"
        zip_b = Path(second) / f"{TARGET}.zip"
        deterministic_zip(package_a, zip_a)
        deterministic_zip(package_b, zip_b)
        if zip_a.read_bytes() != zip_b.read_bytes() or frozen_a != frozen_b:
            raise BuildError("deterministic double build differs")
        shutil.copy2(zip_a, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    write_json(LOCAL / f"{TARGET}.frozen_surface.json", frozen_a)
    receipt = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57g-build-v1",
        "status": "BUILT_UPLOAD_HOLD_PENDING_EXACT_FINAL_ZIP_AND_FIRST_FRESH_AUDIT",
        "package_id": TARGET,
        "zip": {
            "path": OUT_ZIP.relative_to(ROOT).as_posix(),
            "bytes": OUT_ZIP.stat().st_size,
            "sha256": sha(OUT_ZIP),
        },
        "sidecar": {
            "path": sidecar.relative_to(ROOT).as_posix(),
            "bytes": sidecar.stat().st_size,
            "sha256": sha(sidecar),
        },
        "source_zip": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA,
        },
        "deterministic_double_build": True,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "runner_return_only_successor": True,
        "configuration_changed": False,
        "numeric_workload_golden_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(LOCAL / f"{TARGET}.build.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
