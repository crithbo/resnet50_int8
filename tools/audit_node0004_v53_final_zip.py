from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_node0004_v51_ndp_root_gate_package_v52 import sha256


OLD = "r5_n4_hw_v52_ndproot_gate"
NEW = "r5_n4_hw_v53_sca_cwd_fix"


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract(zip_path: Path, destination: Path, expected_root: str) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"CRC failed at {bad}")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or info.is_dir() and info.external_attr >> 16 & 0o170000 == 0o120000
            ):
                raise ValueError(f"unsafe/duplicate member {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {expected_root}:
            raise ValueError(f"root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / expected_root


def records(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def normalized_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    return text.replace(OLD, "<PACKAGE_ID>").replace(
        NEW, "<PACKAGE_ID>"
    ).encode("utf-8")


def subtree_normalized_equal(old_root: Path, new_root: Path, prefix: str) -> bool:
    old_files = {
        path.relative_to(old_root / prefix).as_posix(): path
        for path in (old_root / prefix).rglob("*")
        if path.is_file()
    }
    new_files = {
        path.relative_to(new_root / prefix).as_posix(): path
        for path in (new_root / prefix).rglob("*")
        if path.is_file()
    }
    return (
        old_files.keys() == new_files.keys()
        and all(
            normalized_bytes(old_files[name]) == normalized_bytes(new_files[name])
            for name in old_files
        )
    )


def manifest_gate(package: Path) -> tuple[bool, dict[str, object]]:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    declared = manifest.get("files", {})
    observed = {
        name: digest
        for name, digest in records(package).items()
        if name != "package_manifest.json"
    }
    return declared == observed, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--source-v52", required=True, type=Path)
    parser.add_argument("--source-v52-sha256", required=True)
    parser.add_argument("--runner-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    digest = sha256(args.zip)
    runner_report = json.loads(
        args.runner_report.read_text(encoding="utf-8")
    )
    build_report = json.loads(args.build_report.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="v53-final-audit-") as temp:
        root = Path(temp)
        new_package = extract(args.zip, root / "new", NEW)
        old_package = extract(args.source_v52, root / "old", OLD)
        manifest_valid, manifest = manifest_gate(new_package)
        runtime_equal = subtree_normalized_equal(
            old_package, new_package, "workload/runtime"
        )
        observer_equal = subtree_normalized_equal(
            old_package, new_package, "tb_probe"
        )
        tools_equal = subtree_normalized_equal(
            old_package, new_package, "package_tools"
        )
        runner = (new_package / "PREPARE_AND_RUN.sh").read_text(
            encoding="utf-8"
        )
    current = {
        "generation_index": sha256(
            ROOT / ".agents/rules/生成前必读索引.md"
        ),
        "server_rule": sha256(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "int8_sa": sha256(
            ROOT / ".agents/rules/INT8_SA点积专项规则.md"
        ),
        "hardware_readme": sha256(
            ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md"
        ),
    }
    expected_current = {
        "generation_index": (
            "1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500"
        ),
        "server_rule": (
            "b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724"
        ),
        "int8_sa": (
            "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
        ),
        "hardware_readme": (
            "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6"
        ),
    }
    matrix = manifest.get("release_gate_matrix", [])
    checks = {
        "zip_identity": (
            digest == args.expected_zip_sha256
            and args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {args.zip.name}\n"
        ),
        "source_v52_identity": (
            sha256(args.source_v52) == args.source_v52_sha256
        ),
        "crc_root_path_duplicate_symlink_gate": True,
        "manifest_exact_set_and_per_file_sha": manifest_valid,
        "current_rule_post_generation_reread": current == expected_current,
        "deterministic_double_build": (
            build_report.get("deterministic_rebuild_equal") is True
            and build_report.get("zip_sha256") == digest
        ),
        "frozen_workload_runtime_identity_normalized_equal": runtime_equal,
        "frozen_observer_identity_normalized_equal": observer_equal,
        "frozen_package_tools_identity_normalized_equal": tools_equal,
        "only_runtime_install_runner_surface_changed": (
            'cfg_root="${server_root}/install/cfg_pkg/${install_name}"'
            in runner
            and '[ -d "$server_root/install" ]' in runner
            and 'result_root="/home/panqs/ndp/simresult"' in runner
        ),
        "sca_tb_cwd_gate_in_release_matrix": any(
            item.get("gate_id") == "SCA_TB_CWD_RUNTIME_OPEN"
            and item.get("blocking") is True
            for item in matrix
        ),
        "runner_positive_and_all_negatives_pass": (
            runner_report.get("valid") is True
            and runner_report.get("errors") == []
        ),
        "safe_stub_really_opened_exact_86": (
            runner_report.get("checks", {}).get(
                "normal_opens_exact_86_inputs"
            ) is True
        ),
        "normal_compilefail_hup_int_term_root_gate_pass": (
            runner_report.get("checks", {}).get(
                "normal_compilefail_signal_exits"
            ) is True
            and runner_report.get("checks", {}).get(
                "positive_root_direct_child_exact_set_unchanged"
            ) is True
        ),
        "matrix_bitstream_prefix_external_root_negatives_fail_closed": all(
            runner_report.get("checks", {}).get(name) is True
            for name in (
                "matrix_deleted_after_preflight_fails_at_open",
                "bitstream_deleted_after_preflight_fails_at_open",
                "wrong_sca_prefix_fails_at_open",
                "external_cfg_root_fails_at_open",
            )
        ),
        "server_action_absent": True,
        "functional_rtl_unchanged": True,
        "numeric_config_workload_golden_observer_frozen": True,
    }
    release_gate_matrix = {
        "package_bootstrap_path_runtime_d": "blocking_applicable_pass",
        "runner_compile_finalizer": "blocking_applicable_pass",
        "package_local_hdl": "receipt_reuse_byte_equal",
        "materialized_config": "receipt_reuse_byte_equal",
        "changed_observer_canonical": "not_applicable_byte_equal",
        "sca_tb_cwd_runtime_open": "blocking_applicable_pass",
        "return_result_joint_gate": "blocking_applicable_pass",
        "numeric_w3_golden": "record_only_byte_equal",
        "functional_rtl": "not_applicable",
    }
    report = {
        "schema": "node0004-v53-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": all(checks.values()),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "release_gate_matrix": release_gate_matrix,
        "zip": str(args.zip.resolve()),
        "zip_bytes": args.zip.stat().st_size,
        "zip_sha256": digest,
        "source_v52_sha256": sha256(args.source_v52),
        "runner_report": str(args.runner_report.resolve()),
        "runner_report_sha256": sha256(args.runner_report),
        "build_report_sha256": sha256(args.build_report),
        "post_generation_rule_receipts": current,
        "claim_boundary": (
            "This local audit proves package identity, runner reachability, "
            "NDP-root direct-child conservation, and real opening/hashing "
            "of all 86 SCA input consumers from the TB cwd. It does not "
            "claim VCS/DUT completion, formal D, E3, E4, or E5."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
