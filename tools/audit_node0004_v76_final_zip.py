from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v76_sourcebound_boundfix"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--source-bound-report", type=Path, required=True)
    parser.add_argument("--post-sim-report", type=Path, required=True)
    parser.add_argument("--bounded-report", type=Path, required=True)
    parser.add_argument("--runner-report", type=Path, required=True)
    parser.add_argument("--return-contract-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    checks: dict[str, bool] = {}
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["single_root"] = {
            name.split("/", 1)[0] for name in names if name
        } == {PACKAGE}
        checks["safe_members"] = all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            and not stat.S_ISLNK(info.external_attr >> 16)
            for name, info in zip(names, infos)
        )
        checks["no_duplicates"] = len(names) == len(set(names))
        files = {
            name.split("/", 1)[1]: archive.read(name)
            for name in names
            if "/" in name and not name.endswith("/")
        }
        manifest = json.loads(files["package_manifest.json"])
        actual = {
            relative: sha256_bytes(value)
            for relative, value in files.items()
            if relative != "package_manifest.json"
        }
        checks["manifest_exact"] = manifest.get("files") == actual
        receipts = manifest.get("active_receipts", {})
        checks["current_receipts"] = (
            receipts.get("source_bound_generator_sha256")
            == sha256_file(ROOT / "tools/generate_server_source_bound_observer.py")
            and receipts.get("server_package_rule_sha256")
            == sha256_file(ROOT / ".agents/rules/服务器测试包生成规则.md")
            and receipts.get("server_post_sim_return_helper_sha256")
            == sha256_file(ROOT / "tools/server_post_sim_return.py")
        )
        checks["frozen_surfaces"] = all(
            manifest.get(key) is False
            for key in (
                "numeric_analysis_repeated",
                "node0004_workload_rebuilt",
                "configuration_rebuilt",
                "functional_rtl_modified",
                "server_action",
            )
        )
        checks["required_post_sim_members"] = all(
            name in files
            for name in (
                "package_tools/server_post_sim_return.py",
                "package_tools/node0004_v76_post_sim_plugin.py",
                "contracts/server_post_sim_return_request.json",
                "contracts/server_post_sim_return_contract.json",
            )
        )

    build = read_json(args.build_report)
    source_bound = read_json(args.source_bound_report)
    post_sim = read_json(args.post_sim_report)
    bounded = read_json(args.bounded_report)
    runner = read_json(args.runner_report)
    return_contract = read_json(args.return_contract_report)
    checks["deterministic_double_build"] = (
        build.get("deterministic_rebuild_equal") is True
        and build.get("zip_sha256") == sha256_file(args.zip)
    )
    checks["source_bound_exact_regeneration"] = source_bound.get("pass") is True
    checks["post_sim_core_return"] = post_sim.get("pass") is True
    checks["over_budget_replay"] = bounded.get("pass") is True
    checks["runner_controls"] = runner.get("valid") is True
    checks["return_joint_gate"] = return_contract.get("valid") is True

    errors = [name for name, value in checks.items() if not value]
    release_gate_matrix = {
        "package_bootstrap_and_identity": {
            "applicability": "blocking_applicable",
            "pass": all(
                checks[name]
                for name in ("crc", "single_root", "safe_members", "no_duplicates", "manifest_exact")
            ),
        },
        "runner_compile_finalizer_and_return": {
            "applicability": "blocking_applicable",
            "pass": checks["runner_controls"] and checks["return_joint_gate"],
        },
        "source_bound_observer": {
            "applicability": "blocking_applicable",
            "pass": checks["source_bound_exact_regeneration"],
        },
        "post_sim_core_return": {
            "applicability": "blocking_applicable",
            "pass": checks["post_sim_core_return"],
        },
        "changed_bounded_projection": {
            "applicability": "blocking_applicable",
            "pass": checks["over_budget_replay"],
        },
        "numeric_workload_config_golden_rtl": {
            "applicability": "receipt_reuse_frozen",
            "pass": checks["frozen_surfaces"],
        },
    }
    report = {
        "schema": "conv-node0004-v76-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "release_gate_matrix": release_gate_matrix,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": sha256_file(args.zip),
        },
        "claim_boundary": (
            "Final package and changed post-sim bounded collector gates only; no server run, "
            "natural-terminal, formal-D, E4 or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
