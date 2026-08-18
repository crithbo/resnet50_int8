#!/usr/bin/env python3
"""Consume the exact v90 native-flow return without modifying it."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v90b_nativeflow"
RETURN_ROOT = f"{PACKAGE_ID}_return/"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
OUT = ROOT / "outputs/conv_node0004_v90b_formal_return_analysis1"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(name: str, value: object) -> Path:
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def load_json(archive: zipfile.ZipFile, relative: str) -> dict[str, object]:
    value = json.loads(archive.read(RETURN_ROOT + relative).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"not a JSON object: {relative}")
    return value


def safe_names(archive: zipfile.ZipFile) -> list[str]:
    names = archive.namelist()
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"unsafe ZIP member: {name}")
        if not name.startswith(RETURN_ROOT):
            raise ValueError(f"wrong return root: {name}")
    if len(names) != len(set(names)):
        raise ValueError("duplicate ZIP member")
    return names


def main(return_path: Path) -> int:
    if OUT.exists():
        raise SystemExit(f"fresh analysis output already exists: {OUT}")
    OUT.mkdir(parents=True)
    errors: list[str] = []
    with zipfile.ZipFile(return_path) as archive, zipfile.ZipFile(SOURCE_ZIP) as source:
        names = safe_names(archive)
        if archive.testzip() is not None:
            errors.append("return CRC failure")
        manifest = load_json(archive, "RETURN_CORE_MANIFEST.json")
        compile_core = load_json(archive, "evidence/compile_rootcause/COMPILE_CORE.json")
        sim_exit = load_json(archive, "evidence/SIM_EXIT_RECEIPT.json")
        native = load_json(archive, "evidence/NATIVE_FLOW_ATTEMPT.json")
        actual_argv = load_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        core_status = load_json(archive, "return_core/RETURN_CORE_STATUS.json")
        returned_manifest = archive.read(RETURN_ROOT + "evidence/returned_package_manifest.json")
        source_manifest = source.read(f"{PACKAGE_ID}/package_manifest.json")
        runner = source.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh").decode("utf-8")
        log_bytes = archive.read(
            RETURN_ROOT + "evidence/compile_rootcause/compile_driver.full.log"
        )
        log = log_bytes.decode("utf-8", errors="replace")

        actual_members = set(names) - {RETURN_ROOT + "RETURN_CORE_MANIFEST.json"}
        declared_members = set(manifest.get("members", []))
        if actual_members != declared_members:
            errors.append("return manifest exact member set mismatch")
        receipt_mismatches: list[str] = []
        for item in manifest.get("core_entry_receipts", []):
            if not isinstance(item, dict):
                receipt_mismatches.append("non-object receipt")
                continue
            member = RETURN_ROOT + str(item.get("path"))
            if member not in names:
                receipt_mismatches.append(f"missing:{member}")
                continue
            data = archive.read(member)
            if item.get("bytes") != len(data) or item.get("sha256") != digest_bytes(data):
                receipt_mismatches.append(f"identity:{member}")
        if receipt_mismatches:
            errors.extend(receipt_mismatches)

    identity = (
        manifest.get("package_id"),
        manifest.get("execution_id"),
        manifest.get("attempt_id"),
    )
    identity_checks = {
        "package": identity[0] == PACKAGE_ID,
        "execution": identity[1] == "r1786677192847533492_2093368",
        "attempt": identity[2] == "a2093368",
        "compile_core": (
            compile_core.get("package_id"),
            compile_core.get("execution_id"),
            compile_core.get("attempt_id"),
        ) == identity,
        "sim_exit": (
            sim_exit.get("package_id"),
            sim_exit.get("execution_id"),
            sim_exit.get("attempt_id"),
        ) == identity,
        "native_attempt": (
            native.get("package_id"),
            native.get("execution_id"),
            native.get("attempt_id"),
        ) == identity,
        "returned_manifest_exact_source": returned_manifest == source_manifest,
    }
    errors.extend(name for name, passed in identity_checks.items() if not passed)

    fatal_lines = [
        line
        for line in log.splitlines()
        if re.search(r"^\s*(?:Error|Fatal)-\[", line, re.I)
    ]
    compile_checks = {
        "authoritative_compile_exit_zero": compile_core.get("compile_exit") == 0,
        "native_compile_exit_zero": native.get("compile_exit") == 0,
        "compile_completed_marker": "Compilation completed!" in log,
        "executable_generated": (
            "Executable: /home/panqs/ndp/NDP_copy04/install/codex_runs/"
            f"{PACKAGE_ID}/a2093368/compile/sim_results/simv"
        ) in log,
        "vcs_elaboration_zero_errors": "Verdi KDB elaboration finished with 0 error(s)" in log,
        "designware_dw_ecc_resolved": "/dw/sim_ver/DW_ecc.v" in log,
        "designware_dw_fifo_resolved": "/dw/sim_ver/DW_fifo_s1_sf.v" in log,
        "designware_dw_lod_resolved": "/dw/sim_ver/DW_lod.v" in log,
        "designware_dw_sync_resolved": "/dw/sim_ver/DW_sync.v" in log,
        "no_vcs_fatal_line": not fatal_lines,
    }
    errors.extend(name for name, passed in compile_checks.items() if not passed)

    invocation = re.search(
        r'python3 - "\$compile_log" "\$compile_driver_log" '
        r'"\$compile_first_error_txt" "\$compile_log_head_txt" '
        r'"\$compile_log_tail_txt" "\$compile_full_log" <<\'PY\'',
        runner,
    )
    unpack = "s,d,f,h,t=map(pathlib.Path,sys.argv[1:])" in runner
    defect_checks = {
        "exact_six_path_invocation_present": invocation is not None,
        "exact_five_target_unpack_present": unpack,
        "set_e_restored_before_normalizer": (
            'compile_status=$?; set -e\npython3 - "$compile_log"' in runner
        ),
        "source_identity_not_refreshed": actual_argv.get("source_identity_status") == "NOT_YET_BOUND",
        "source_identity_placeholder_returned": (
            json.loads(
                zipfile.ZipFile(return_path).read(
                    RETURN_ROOT + "evidence/compile_rootcause/compile_source_identity.json"
                ).decode("utf-8")
            ).get("status") == "NOT_YET_RECORDED"
        ),
        "simulation_never_started": sim_exit.get("simulation_started") is False,
        "sim_exit_sentinel": sim_exit.get("exit_code") == 125,
        "no_sim_log_created": all(
            item.get("status") == "NOT_CREATED"
            for item in native.get("complete_log_receipts", [])
            if item.get("label") == "production_simulation"
        ),
    }
    errors.extend(name for name, passed in defect_checks.items() if not passed)

    stale_placeholder = (
        actual_argv.get("compile_exit") == 125
        and native.get("first_true_error") == "compile driver has not started"
    )
    report = {
        "schema": "conv-node0004-v90b-formal-return-analysis-v1",
        "role_id": "family.conv.serialized",
        "package_id": PACKAGE_ID,
        "return": {
            "path": str(return_path),
            "bytes": return_path.stat().st_size,
            "sha256": digest_file(return_path),
            "crc_pass": not errors or "return CRC failure" not in errors,
            "member_count": len(names),
        },
        "source_package": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": digest_file(SOURCE_ZIP),
        },
        "identity_checks": identity_checks,
        "authoritative_result": {
            "compile_exit": 0,
            "simulation_exit": 125,
            "simulation_started": False,
            "natural_terminal": False,
            "formal_d": "NOT_REACHED",
            "observer_events": "NOT_CREATED",
        },
        "compile_checks": compile_checks,
        "fatal_compile_lines": fatal_lines,
        "last_proven_good": "Production VCS compile, elaboration and link completed; DesignWare providers resolved and the exact simv executable was generated.",
        "first_divergence": "The package-local post-compile log normalizer received six path arguments but unpacked sys.argv[1:] into five targets under restored set -e, so runner control exited before source-identity refresh, simv binding, supervisor and observer execution.",
        "classification": "PACKAGE_LOCAL_POST_COMPILE_EVIDENCE_NORMALIZER_ARITY_DEFECT",
        "defect_checks": defect_checks,
        "stale_placeholder_receipts": {
            "present": stale_placeholder,
            "non_authoritative": [
                "evidence/ACTUAL_COMPILE_SIM_ARGV.json:compile_exit=125",
                "evidence/NATIVE_FLOW_ATTEMPT.json:first_true_error=compile driver has not started",
                "bounded compile head/tail placeholders",
            ],
            "authority": [
                "evidence/compile_rootcause/COMPILE_CORE.json:compile_exit=0",
                "evidence/SIM_EXIT_RECEIPT.json:compile_exit=0",
                "complete production compile log",
            ],
        },
        "root_exclusions": {
            "server_environment": True,
            "designware_provider": True,
            "functional_rtl": True,
            "config_numeric_workload": True,
            "observer_hdl": True,
        },
        "successor": {
            "required": True,
            "authorized_change": "Remove the duplicate sixth compile_full_log argument (compile_log already names the same file) or use a verified helper; add a 6-to-5 mismatch negative gate.",
            "frozen": [
                "config", "numeric", "workload", "golden", "functional_rtl",
                "actual_source_causal_target", "38_net_26_role_observer",
                "dump_profile_0_0_0", "observer_budget_semantics", "native_flow_semantics",
            ],
        },
        "previous_version_progress": "v88b closed the retired ACK comparator as an observer/source-identity false positive; v89b failed at unresolved DesignWare before simulation.",
        "current_version_purpose": "v90b was intended to preserve the corrected actual-source observer under the direct native production flow, close the v88/v89 compile difference and enter real simulation.",
        "resolved_by_return": "The v89 DesignWare failure is not reproduced: v90 production compile/elaboration/link passed. The new first divergence is a package-local post-compile normalizer arity defect.",
        "claim_boundary": "The return proves compile/elaboration/link and the package-local runner stop. It contains no simulation-time, observer, natural-terminal, formal-D, E3, E4 or E5 evidence.",
        "conflicts": [],
        "server_actions_performed_by_family": [],
        "pass": not errors,
        "errors": errors,
    }
    write_json("formal_return_analysis.json", report)
    write_json(
        "return_integrity.json",
        {
            "schema": "conv-node0004-v90b-return-integrity-v1",
            "pass": not errors,
            "errors": errors,
            "identity_checks": identity_checks,
            "member_count": len(names),
            "return_sha256": digest_file(return_path),
            "source_package_sha256": digest_file(SOURCE_ZIP),
        },
    )
    (OUT / "task_record.md").write_text(
        "# Serialized Conv v90b formal return analysis\n\n"
        "## 上一版本进度\n\n"
        "v88b 已排除旧 ACK comparator 误报；v89b production compile 曾因 DesignWare unresolved 退出。\n\n"
        "## 本版本目的与结果\n\n"
        "v90b 旨在以 direct native production flow 保留 actual-source 38-net/26-role observer，"
        "闭合 v88/v89 编译差异并进入真实仿真。formal return 证明 compile/elaboration/link 全部成功，"
        "DesignWare 正常解析并生成 simv；因此 v89 的 unresolved 不是本轮复现根因。\n\n"
        "LAST_PROVEN_GOOD 是 simv executable 生成。FIRST_DIVERGENCE 是 package-local compile-log "
        "normalizer：shell 传入六个路径而 Python 仅解包五个，且此前已恢复 `set -e`，所以 runner 在"
        "刷新 source identity、绑定 simv、启动 supervisor/observer 前退出。分类为 "
        "`PACKAGE_LOCAL_POST_COMPILE_EVIDENCE_NORMALIZER_ARITY_DEFECT`。\n\n"
        "返回中的 `compile_exit=125` 和 `compile driver has not started` 是未刷新的占位 receipt；权威 "
        "COMPILE_CORE/SIM_EXIT 与完整 compile log 均证明 compile=0。simulation 未启动，natural terminal、"
        "formal-D、E3/E4/E5 均未到达。\n\n"
        "允许的 successor 只删除重复的第六参数或采用已验证 helper，并加入 6→5 负控；其余输入、RTL、"
        "observer 与 native-flow 语义全部冻结。`conflicts=[]`。\n",
        encoding="utf-8",
        newline="\n",
    )
    print(OUT / "formal_return_analysis.json")
    return 0 if not errors else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} /path/to/formal_return.zip")
    raise SystemExit(main(Path(sys.argv[1]).resolve()))
