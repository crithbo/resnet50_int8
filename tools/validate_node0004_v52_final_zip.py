from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL = "r5_n4_hw_v52_ndproot_gate"
SOURCE = "r5_n4_hw_v51_lc13_lc14_diag"
SOURCE_SHA = "23d421c38b310bc458c6305fea33d9372a217a3bc2fced6e796e6368510964f0"
CURRENT = {
    "agent": (
        ".agents/agent.md",
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ),
    "plan": (
        ".agents/plan.md",
        "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70",
    ),
    "index": (
        ".agents/rules/生成前必读索引.md",
        "1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500",
    ),
    "server": (
        ".agents/rules/服务器测试包生成规则.md",
        "b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724",
    ),
    "common": (
        ".agents/rules/算子配置规则.md",
        "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    ),
    "ndp": (
        ".agents/rules/NDP硬件字段语义.md",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
    "int8_sa": (
        ".agents/rules/INT8_SA点积专项规则.md",
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    ),
    "readme": (
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
    ),
}
REQUIRED_RULES = {
    "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
    "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
    "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    result: dict[str, bytes] = {}
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"crc:{bad}")
        roots: set[str] = set()
        names: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                info.filename in names
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
            ):
                errors.append(f"unsafe:{info.filename}")
            names.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            if stat.S_ISLNK(info.external_attr >> 16):
                errors.append(f"symlink:{info.filename}")
            if not info.is_dir() and len(pure.parts) > 1:
                relative = PurePosixPath(*pure.parts[1:]).as_posix()
                if relative in result:
                    errors.append(f"duplicate:{relative}")
                result[relative] = archive.read(info)
        if roots != {root}:
            errors.append(f"root:{sorted(roots)}")
    return result, errors


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_identity(value: bytes) -> bytes:
    return value.replace(INSTALL.encode(), b"<IDENTITY>").replace(
        SOURCE.encode(), b"<IDENTITY>"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--source-v51", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--root-gate-report", required=True, type=Path)
    parser.add_argument("--v51-final-audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    entries, zip_errors = read_zip(args.zip.resolve(), INSTALL)
    source, source_errors = read_zip(args.source_v51.resolve(), SOURCE)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    build = load(args.build_report)
    root_gate = load(args.root_gate_report)
    v51_audit = load(args.v51_final_audit)
    digest = sha_file(args.zip)
    files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}
    receipts = manifest.get("active_receipts", {})
    rules = set(receipts.get("rules", []))
    runner = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime_v7.py", b""
    ).decode("utf-8", errors="replace")
    matrix = manifest.get("release_gate_matrix", [])
    by_gate = {row.get("gate_id"): row for row in matrix}

    frozen_prefixes = ("workload/", "tb_probe/")
    frozen = sorted(
        name
        for name in set(entries) | set(source)
        if name.startswith(frozen_prefixes)
    )
    frozen_diff = [
        name
        for name in frozen
        if normalize_identity(entries.get(name, b""))
        != normalize_identity(source.get(name, b""))
    ]
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "package_manifest.json",
        "package_tools/node0004_hang_localization_runtime.py",
        "package_tools/node0004_hang_localization_runtime_v7.py",
        "provenance/v51_to_v52_ndp_root_gate.json",
    }
    changed_common = sorted(
        name
        for name in set(entries) & set(source)
        if normalize_identity(entries[name])
        != normalize_identity(source[name])
    )
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))
    unexpected_delta = sorted(
        (set(changed_common) | set(added) | set(removed)) - allowed_changed
    )

    current = {
        name: sha_file(ROOT / relative)
        for name, (relative, _) in CURRENT.items()
    }
    fixed = manifest.get("fixed_server_result_publication", {})
    checks = {
        "zip_identity": (
            digest == args.expected_sha256
            and args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {args.zip.name}\n"
        ),
        "zip_safety": not zip_errors and not source_errors,
        "source_v51_identity": sha_file(args.source_v51) == SOURCE_SHA,
        "manifest_identity": manifest.get("install_name") == INSTALL,
        "manifest_exact_set": set(files) == paths,
        "manifest_hashes": all(
            name in entries and sha_bytes(entries[name]) == value
            for name, value in files.items()
        ),
        "classification": (
            manifest.get("candidate_release") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("functional_rtl_modified") is False
        ),
        "deterministic_build": (
            build.get("deterministic_rebuild_equal") is True
            and build.get("zip_sha256") == digest
            and build.get("node0004_workload_rebuilt") is False
            and build.get("numeric_analysis_repeated") is False
            and build.get("configuration_rebuilt") is False
            and build.get("observer_rebuilt") is False
        ),
        "frozen_compute_payload_byte_equal": not frozen_diff,
        "delta_allowlisted": not unexpected_delta,
        "v51_prior_gates_reused": (
            v51_audit.get("valid") is True
            and v51_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True
        ),
        "root_gate_controls": (
            root_gate.get("valid") is True
            and root_gate.get("errors") == []
            and root_gate.get("checks", {}).get(
                "normal_compilefail_signal_exits"
            )
            is True
            and root_gate.get("checks", {}).get(
                "root_directory_negative_fail_closed"
            )
            is True
            and root_gate.get("checks", {}).get(
                "root_file_negative_fail_closed"
            )
            is True
            and root_gate.get("checks", {}).get(
                "missing_parent_negative_fail_closed"
            )
            is True
            and root_gate.get("checks", {}).get(
                "unblocked_drift_negative_rejected"
            )
            is True
        ),
        "current_rule_receipts": all(
            current[name] == expected
            for name, (_, expected) in CURRENT.items()
        ),
        "manifest_current_receipts": (
            receipts.get("generation_index_sha256")
            == CURRENT["index"][1]
            and receipts.get("server_package_rule_sha256")
            == CURRENT["server"][1]
            and receipts.get("common_operator_rule_sha256")
            == CURRENT["common"][1]
        ),
        "required_rules_bound": REQUIRED_RULES <= rules,
        "root_gate_release_matrix": (
            by_gate.get("NDP_ROOT_TOPLEVEL_EXACT_SET", {}).get(
                "applicability"
            )
            == "blocking_applicable"
            and by_gate.get("NDP_ROOT_TOPLEVEL_EXACT_SET", {}).get(
                "blocking"
            )
            is True
        ),
        "production_runner_gate": all(
            token in runner
            for token in (
                'root-snapshot --server-root "$server_root"',
                "ndp_root_toplevel_post.json",
                "ndp_root_toplevel_gate.json",
                '[ "$final" -ne 0 ] || [ "$root_gate" -eq 0 ] || final="$root_gate"',
            )
        ),
        "production_runtime_gate": all(
            token in runtime
            for token in (
                "def root_snapshot(",
                "def compare_root_snapshots(",
                "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED",
            )
        ),
        "fixed_atomic_return": (
            fixed.get("result_root") == "/home/panqs/ndp/simresult"
            and fixed.get("return_zip")
            == f"/home/panqs/ndp/simresult/{INSTALL}_return.zip"
            and fixed.get("return_sidecar")
            == f"/home/panqs/ndp/simresult/{INSTALL}_return.zip.sha256"
            and fixed.get("configurable") is False
        ),
        "local_server_path_not_created": (
            root_gate.get("checks", {}).get(
                "local_server_path_not_created_or_mapped"
            )
            is True
        ),
    }
    report = {
        "schema": "node0004-v52-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": all(checks.values()),
        "valid": all(checks.values()),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": digest,
        },
        "source_v51_sha256": sha_file(args.source_v51),
        "current_receipts": current,
        "changed_common": changed_common,
        "added": added,
        "removed": removed,
        "unexpected_delta": unexpected_delta,
        "frozen_compute_payload_diff": frozen_diff,
        "root_gate_report_sha256": sha_file(args.root_gate_report),
        "v51_final_audit_sha256": sha_file(args.v51_final_audit),
        "expected_return": (
            f"/home/panqs/ndp/simresult/{INSTALL}_return.zip"
        ),
        "server_command": (
            f"bash {INSTALL}/PREPARE_AND_RUN.sh "
            "/absolute/path/to/NDP_copy0x"
        ),
        "claim_boundary": (
            "This is a runner-only successor. It proves the exact final "
            "runner preserves the NDP root direct-child name/type set "
            "across normal, compile-fail, HUP, INT and TERM controls. "
            "It does not claim Conv numerical or dynamic E4/E5 success."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
