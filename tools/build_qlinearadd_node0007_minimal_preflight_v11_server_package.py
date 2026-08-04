from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json


INSTALL_NAME = "r5_qadd_n7_minpre_v11"
SOURCE_NAME = "r5_qadd_n7_first_request_chain_v10"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf"
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
INDEX_SHA256 = "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
QADD_RULE_SHA256 = "c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b"
RUNTIME_SOURCE = ROOT / "tools/qlinearadd_node0007_server_runtime.py"
RUNTIME_REL = Path("package_tools/qlinearadd_node0007_server_runtime.py")
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-minpre-v11/report.json"
)


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return re.findall(r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8"))


def _assert_receipts() -> None:
    expected = {
        SOURCE_ZIP: SOURCE_ZIP_SHA256,
        INDEX: INDEX_SHA256,
        SERVER_RULE: SERVER_RULE_SHA256,
        QADD_RULE: QADD_RULE_SHA256,
    }
    drift = {
        str(path): {"expected": wanted, "actual": sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or sha256(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")


def _extract(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    with tempfile.TemporaryDirectory(prefix="q11-") as raw:
        staging = Path(raw)
        with zipfile.ZipFile(SOURCE_ZIP) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise BuildError(f"source ZIP CRC failure: {bad}")
            archive.extractall(staging)
        source = staging / SOURCE_NAME
        if not source.is_dir():
            raise BuildError("source ZIP root differs")
        shutil.move(str(source), str(package))
    return package


def _replace_namespace(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(SOURCE_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    package = _extract(destination)
    for relative in (
        Path("PREPARE_AND_RUN.sh"),
        Path("TEST_PACKAGE_MANIFEST.json"),
        Path("workload/runtime/sca_cfg.json"),
        Path("workload/runtime/sca_cfg_D.json"),
    ):
        _replace_namespace(package / relative)

    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    hardcoded = f'install_name="{INSTALL_NAME}"'
    manifest_bound = (
        'install_name="$(python3 "$runtime" manifest-value '
        '--package-root "$package_root" --key install_name)" || exit 5\n'
        'case "$install_name" in\n'
        '  *[!A-Za-z0-9._-]*|"") echo "unsafe manifest install_name" >&2; exit 5;;\n'
        "esac"
    )
    if runner.count(hardcoded) != 1:
        raise BuildError("runner install identity replacement point differs")
    runner = runner.replace(hardcoded, manifest_bound)
    runner_path.write_text(runner, encoding="utf-8", newline="\n")

    shutil.copyfile(RUNTIME_SOURCE, package / RUNTIME_REL)
    (package / "README.md").write_text(
        "# QLinearAdd node0007 first-request diagnostic v11\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This fresh successor preserves the byte-equivalent frozen workload and "
        "read-only first-request observer from v10. The package/install identity "
        "is read from the final manifest as the single source of truth. Runtime "
        "preflight checks only arguments, fresh namespaces, package-local payload, "
        "runtime-D absence, and generic command availability; the real compile "
        "naturally adjudicates the user-supplied server source tree.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-first-request-diagnostic-server-package-v11",
            "install_name": INSTALL_NAME,
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_RUNTIME_PREFLIGHT_IDENTITY_DUPLICATION",
                "numeric_and_workload_semantics_unchanged": True,
            },
            "runtime_preflight_profile": {
                "rule_ids": [
                    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
                    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
                    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
                ],
                "identity_single_source": "TEST_PACKAGE_MANIFEST.json:install_name",
                "runner_hardcoded_expected_sha_count": 0,
                "server_source_preflight_performed": False,
                "server_source_identity_bound": False,
                "safe_compile_stub_positive_control_required": True,
                "wrong_payload_identity_negative_control_required": True,
            },
        }
    )
    manifest["final_zip_rule_self_audit"] = {
        "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "rule_receipts": {
            "generation_index": {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": INDEX_SHA256,
                "current_match": True,
            },
            "server_package_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "sha256": SERVER_RULE_SHA256,
                "current_match": True,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "sha256": QADD_RULE_SHA256,
                "current_match": True,
            },
        },
        "applicable_server_rule_ids": _rule_ids(SERVER_RULE),
        "applicable_qlinearadd_rule_ids": _rule_ids(QADD_RULE),
        "direct_final_zip_and_sidecar_validation_required": True,
        "all_required_negative_controls_required": True,
        "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
        "errors_must_equal": 0,
        "validator": "tools/validate_qlinearadd_node0007_minimal_preflight_v11.py",
        "report": REPORT_REL,
    }
    manifest["provenance"]["generation_index"] = {
        "path": INDEX.relative_to(ROOT).as_posix(),
        "sha256": INDEX_SHA256,
    }
    manifest["provenance"]["server_package_rule"] = {
        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
        "sha256": SERVER_RULE_SHA256,
    }
    manifest["provenance"]["qlinearadd_rule"] = {
        "path": QADD_RULE.relative_to(ROOT).as_posix(),
        "sha256": QADD_RULE_SHA256,
    }
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def _build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION_PATH):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, built, records = _build_once(PACKAGE_ROOT)
        if built != output:
            raise BuildError("unexpected output path")
        with tempfile.TemporaryDirectory(prefix="qadd-v11-repeat-") as raw:
            _, repeat_zip, repeat_records = _build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(output) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
            }
        if not all((repeated["package_tree_equal"], repeated["zip_equal"])):
            raise BuildError("deterministic rebuild differs")
        digest = sha256(output)
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-minimal-preflight-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha256(sidecar),
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "file_count": len(records),
            "repeated_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
