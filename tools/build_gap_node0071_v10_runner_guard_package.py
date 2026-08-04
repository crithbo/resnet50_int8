from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (  # noqa: E402
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import (  # noqa: E402
    file_records,
)


SOURCE_NAME = "r5_n71_gap_v9_ingress_rule"
INSTALL_NAME = "r5_n71_gap_v10_runner_guard"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_SHA256 = (
    "d37f40e768001d3588cd22f25040ba4e229ffc138221a42b13d7e446436e644c"
)
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
OLD_RUNNER_OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
RUNNER_EXPECTED_RE = re.compile(
    r'(--expected-sha256\s+\\?\s*")?([0-9a-f]{64})(")?'
)
RULE_RECEIPTS = [
    {
        "path": ".agents/rules/生成前必读索引.md",
        "sha256":
            "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
        "reason": "current generation routing index",
        "current_match": True,
    },
    {
        "path": ".agents/rules/算子配置规则.md",
        "sha256":
            "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
        "reason": "current common operator materialization rules",
        "current_match": True,
    },
    {
        "path": ".agents/rules/NDP硬件字段语义.md",
        "sha256":
            "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
        "reason": "current NDP field semantics",
        "current_match": True,
    },
    {
        "path": ".agents/rules/服务器测试包生成规则.md",
        "sha256":
            "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa",
        "reason": "current server-package rules",
        "current_match": True,
    },
    {
        "path": ".agents/rules/GAP_int32_mac_bypass_rules.md",
        "sha256":
            "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
        "reason": "frozen GAP int32_mac sum-stage family",
        "current_match": True,
    },
    {
        "path": ".agents/rules/GAP_probe_v7_validator_rules.md",
        "sha256":
            "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf",
        "reason": "current GAP dynamic observer gates",
        "current_match": True,
    },
    {
        "path": ".agents/rules/精确UINT8量化尾专项规则.md",
        "sha256":
            "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
        "reason": "frozen exact UINT8 tail family",
        "current_match": True,
    },
]


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_identity(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(SOURCE_NAME, INSTALL_NAME)
    if isinstance(value, list):
        return [replace_identity(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_identity(item) for key, item in value.items()}
    return value


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("source v9 ZIP SHA256 differs")
    package = destination / INSTALL_NAME
    package.mkdir(parents=True, exist_ok=False)
    prefix = f"{SOURCE_NAME}/"
    seen: set[str] = set()
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source v9 ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not info.filename.startswith(prefix)
            ):
                raise BuildError(f"unsafe source ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(info.filename).relative_to(SOURCE_NAME)
            rel = relative.as_posix()
            if rel in seen:
                raise BuildError(f"duplicate source member: {rel}")
            seen.add(rel)
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    return package


def run_package_tool(command: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return {
        "command": command,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def package_preflight(package: Path) -> dict[str, Any]:
    receipt = run_package_tool(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_complete_server_runtime.py"
            ),
            "preflight",
            "--package-root",
            str(package),
        ],
        package,
    )
    if receipt["exit_code"] != 0:
        raise BuildError(
            f"package preflight failed: {receipt['stdout']} {receipt['stderr']}"
        )
    result = json.loads(receipt["stdout"])
    if result.get("valid") is not True:
        raise BuildError("package preflight receipt is not valid")
    return result


def observer_guard(package: Path, observer_sha: str) -> dict[str, Any]:
    receipt = run_package_tool(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_package_observer_guard.py"
            ),
            "--package-root",
            str(package),
            "--expected-sha256",
            observer_sha,
            "--runner",
            str(package / "PREPARE_AND_RUN.sh"),
        ],
        package,
    )
    if receipt["exit_code"] != 0:
        raise BuildError(
            f"observer guard failed: {receipt['stdout']} {receipt['stderr']}"
        )
    result = json.loads(receipt["stdout"])
    if result.get("valid") is not True or result.get("identity_match") is not True:
        raise BuildError("observer guard positive receipt differs")
    return result


def immutable_records(package: Path) -> dict[str, Any]:
    records = file_records(package, exclude_manifest=False)
    for relative in (
        "TEST_PACKAGE_MANIFEST.json",
        "README.md",
        "PREPARE_AND_RUN.sh",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
    ):
        records.pop(relative)
    return records


def numeric_records(package: Path) -> dict[str, Any]:
    records = file_records(package / "workload", exclude_manifest=False)
    records.pop("sca_cfg.json")
    records.pop("sca_cfg_D.json")
    return records


def rewrite_runner(package: Path, observer_sha: str) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(SOURCE_NAME) < 1:
        raise BuildError("source identity absent from v9 runner")
    if text.count(OLD_RUNNER_OBSERVER_SHA256) != 1:
        raise BuildError("old observer SHA binding is not unique")
    text = text.replace(SOURCE_NAME, INSTALL_NAME)
    text = text.replace(OLD_RUNNER_OBSERVER_SHA256, observer_sha)
    runner.write_text(text, encoding="utf-8", newline="\n")
    final = runner.read_text(encoding="utf-8")
    if (
        SOURCE_NAME in final
        or OLD_RUNNER_OBSERVER_SHA256 in final
        or final.count(observer_sha) != 1
        or f'install_name="{INSTALL_NAME}"' not in final
    ):
        raise BuildError("runner identity/SHA rebinding differs")


def rewrite_sca(package: Path) -> None:
    for relative in ("workload/sca_cfg.json", "workload/sca_cfg_D.json"):
        path = package / relative
        value = json.loads(path.read_text(encoding="utf-8"))
        replaced = replace_identity(value)
        if replaced == value:
            raise BuildError(f"source namespace absent: {relative}")
        write_json(path, replaced)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = extract_source(destination)
    numeric_before = numeric_records(package)
    immutable_before = immutable_records(package)
    observer_path = package / OBSERVER_RELATIVE
    observer_sha = sha256(observer_path)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    if (
        source_manifest.get("package_local_observer", {}).get("sha256")
        != observer_sha
    ):
        raise BuildError("source v9 observer manifest receipt differs")

    rewrite_runner(package, observer_sha)
    rewrite_sca(package)
    (package / "README.md").write_text(
        "# GAP node0071 v10 runner observer-identity repair\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It reuses "
        "the frozen v9 numeric workload, configs, goldens, exact tail and "
        "observer algorithm byte-for-byte. The package-only repair binds "
        "`PREPARE_AND_RUN.sh` to the actual package-local observer SHA before "
        "compile. Run once with:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = replace_identity(source_manifest)
    final_contract = manifest.setdefault(
        "final_zip_rule_self_audit_contract", {}
    )
    applicable = list(final_contract.get("applicable_rule_ids", []))
    for rule_id in (
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    ):
        if rule_id not in applicable:
            applicable.append(rule_id)
    final_contract.update(
        {
            "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "read_receipt": RULE_RECEIPTS,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only":
                "558dce2c256f91bcf537750262b717db00c97ea415849d544cc13d365049a47e",
            "final_zip_independent_validator_required": True,
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v10",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "package-only runner observer-SHA binding repair; frozen GAP "
                "sum/tail/config/golden/workload/observer algorithm unchanged; "
                "no functional fix and no E3/E4/E5"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
            "rule_receipts": {
                "generation_index_sha256": RULE_RECEIPTS[0]["sha256"],
                "common_operator_rule_sha256": RULE_RECEIPTS[1]["sha256"],
                "ndp_field_rule_sha256": RULE_RECEIPTS[2]["sha256"],
                "server_rule_sha256": RULE_RECEIPTS[3]["sha256"],
                "gap_int32_rule_sha256": RULE_RECEIPTS[4]["sha256"],
                "gap_probe_rule_sha256": RULE_RECEIPTS[5]["sha256"],
                "exact_uint8_tail_rule_sha256":
                    RULE_RECEIPTS[6]["sha256"],
                "current_match": True,
                "plan_sha256_mutable_provenance_only":
                    "558dce2c256f91bcf537750262b717db00c97ea415849d544cc13d365049a47e",
            },
            "runner_observer_sha_repair": {
                "source_v9_zip_sha256": SOURCE_SHA256,
                "first_divergence":
                    "OBSERVER_GUARD_EXPECTED_SHA_MISMATCH_BEFORE_COMPILE",
                "old_runner_expected_sha256": OLD_RUNNER_OBSERVER_SHA256,
                "actual_and_new_expected_sha256": observer_sha,
                "observer_algorithm_changed": False,
                "numeric_workload_changed": False,
                "allowed_changed_paths": [
                    "TEST_PACKAGE_MANIFEST.json",
                    "README.md",
                    "PREPARE_AND_RUN.sh",
                    "workload/sca_cfg.json",
                    "workload/sca_cfg_D.json",
                ],
            },
        }
    )
    package_observer = manifest.setdefault("package_local_observer", {})
    package_observer["sha256"] = observer_sha
    manifest.setdefault("observer_binding_contract", {})[
        "source_sha256"
    ] = observer_sha
    provenance = manifest.setdefault("generation_provenance", {})
    provenance.update(
        {
            "tool":
                "tools/build_gap_node0071_v10_runner_guard_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change":
                "fresh identity/SCA namespace/manifest/README and exact "
                "runner observer-SHA binding only",
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)

    checked = package_preflight(package)
    guard = observer_guard(package, observer_sha)
    if numeric_before != numeric_records(package):
        raise BuildError("frozen numeric workload drifted")
    if immutable_before != immutable_records(package):
        raise BuildError("immutable non-receipt payload drifted")
    return package, {
        "observer_sha256": observer_sha,
        "package_preflight": checked,
        "observer_guard": guard,
        "numeric_workload_file_count": len(numeric_before),
        "immutable_nonreceipt_file_count": len(immutable_before),
        "numeric_workload_tree_equal": True,
        "immutable_nonreceipt_tree_equal": True,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v10-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if (
            sha256(repeated_zip) != first_sha
            or file_records(repeated, exclude_manifest=False) != first_tree
        ):
            raise BuildError("repeat build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        validation = {
            "schema":
                "gap-node0071-runner-guard-repair-validation-v10",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v9_quarantined": True,
            **proof,
            "repeated_build": repeated,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
        }
        write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v10 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
