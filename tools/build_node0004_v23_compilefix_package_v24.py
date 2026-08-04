from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v23_final_release_diag"
INSTALL_NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
SOURCE_ZIP_SHA256 = (
    "9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27"
)
RETURN_ZIP_SHA256 = (
    "e8efef64b095f5d6cc2b5e4d734b6d1a94a14741d3b608dfc008ef6894905842"
)
PLAN_MUTABLE_SHA256 = (
    "79971afee8e6465ea560518f5c130a76a93d762673ea1bf71d70b59c83b81891"
)
INDEX_SHA256 = (
    "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
)
SERVER_RULE_SHA256 = (
    "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


class BuildError(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(
            f"patch anchor count differs for {path}: {text.count(old)}"
        )
    path.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("v23 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v23 source ZIP CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe v23 member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v23 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    replace_once(
        path,
        "    longint unsigned return_obs_fr_pe_accepts;\n",
        (
            "    longint unsigned return_obs_fr_pe_accepts;\n"
            "    logic return_obs_fr_prev_buffer5_write;\n"
            "    longint unsigned return_obs_fr_buffer5_write_edges;\n"
        ),
    )
    replace_once(
        path,
        "        return_obs_fr_pe_accepts = 0;\n",
        (
            "        return_obs_fr_pe_accepts = 0;\n"
            "        return_obs_fr_buffer5_write_edges = 0;\n"
        ),
    )
    replace_once(
        path,
        "            return_obs_fr_prev_pe_valid = 0;\n",
        (
            "            return_obs_fr_prev_pe_valid = 0;\n"
            "            return_obs_fr_prev_buffer5_write = 1'b0;\n"
        ),
    )
    replace_once(
        path,
        (
            "        else if (return_obs_fr_enabled && return_obs_active) begin\n"
            "            for (int return_obs_fr_r = 0;\n"
        ),
        (
            "        else if (return_obs_fr_enabled && return_obs_active) begin\n"
            "            if (\n"
            "                (|return_obs_buf45_wr_en_mon\n"
            "                    [return_obs_group_id]\n"
            "                    [return_obs_local_slice_id][1]) &&\n"
            "                !return_obs_fr_prev_buffer5_write\n"
            "            )\n"
            "                return_obs_fr_buffer5_write_edges++;\n"
            "            for (int return_obs_fr_r = 0;\n"
        ),
    )
    replace_once(
        path,
        (
            "            return_obs_fr_prev_pe_valid =\n"
            "                return_obs_fr_pe_valid_mon\n"
            "                    [return_obs_group_id][return_obs_local_slice_id];\n"
        ),
        (
            "            return_obs_fr_prev_pe_valid =\n"
            "                return_obs_fr_pe_valid_mon\n"
            "                    [return_obs_group_id][return_obs_local_slice_id];\n"
            "            return_obs_fr_prev_buffer5_write =\n"
            "                |return_obs_buf45_wr_en_mon\n"
            "                    [return_obs_group_id]\n"
            "                    [return_obs_local_slice_id][1];\n"
        ),
    )
    replace_once(
        path,
        "                    return_obs_buf45_wr_edge_count[1],\n",
        "                    return_obs_fr_buffer5_write_edges,\n",
    )
    text = path.read_text(encoding="utf-8")
    if "return_obs_buf45_wr_edge_count" in text:
        raise BuildError("undeclared v23 observer identifier survived")
    required = (
        "logic return_obs_fr_prev_buffer5_write;",
        "longint unsigned return_obs_fr_buffer5_write_edges;",
        "return_obs_fr_buffer5_write_edges++;",
        "return_obs_fr_buffer5_write_edges,",
    )
    if not all(token in text for token in required):
        raise BuildError("v24 observer edge fix closure incomplete")
    return base.sha256(path)


def patch_return_manifest_contract(package: Path) -> None:
    collector = (
        package
        / "package_tools/node0004_hang_localization_runtime_v7.py"
    )
    replace_once(
        collector,
        "    records.sort(key=lambda item: item[\"path\"])\n",
        (
            "    package_root = Path(__file__).resolve().parents[1]\n"
            "    _copy_limited(\n"
            "        package_root / \"package_manifest.json\",\n"
            "        return_dir / \"evidence/returned_package_manifest.json\",\n"
            "        \"evidence/returned_package_manifest.json\",\n"
            "        records,\n"
            "        True,\n"
            "    )\n"
            "    records.sort(key=lambda item: item[\"path\"])\n"
        ),
    )
    replace_once(
        collector,
        (
            "    write_json(return_dir / \"RETURN_ALLOWLIST.json\", allowlist)\n"
            "    with zipfile.ZipFile(\n"
        ),
        (
            "    write_json(return_dir / \"RETURN_ALLOWLIST.json\", allowlist)\n"
            "    package_manifest_path = package_root / \"package_manifest.json\"\n"
            "    return_manifest = {\n"
            "        \"schema\": \"node0004-return-manifest-v24\",\n"
            "        \"install_name\": install_name,\n"
            "        \"source_package_manifest\": {\n"
            "            \"returned_path\": \"evidence/returned_package_manifest.json\",\n"
            "            \"size_bytes\": package_manifest_path.stat().st_size,\n"
            "            \"sha256\": sha256(package_manifest_path),\n"
            "        },\n"
            "        \"return_allowlist\": {\n"
            "            \"path\": \"RETURN_ALLOWLIST.json\",\n"
            "            \"size_bytes\": (return_dir / \"RETURN_ALLOWLIST.json\").stat().st_size,\n"
            "            \"sha256\": sha256(return_dir / \"RETURN_ALLOWLIST.json\"),\n"
            "        },\n"
            "        \"records\": records,\n"
            "    }\n"
            "    write_json(return_dir / \"RETURN_MANIFEST.json\", return_manifest)\n"
            "    with zipfile.ZipFile(\n"
        ),
    )

    wrapper = (
        package
        / "package_tools/node0004_hang_localization_runtime.py"
    )
    replace_once(
        wrapper,
        '        expected = {"RETURN_ALLOWLIST.json"}\n',
        (
            '        expected = {"RETURN_ALLOWLIST.json", '
            '"RETURN_MANIFEST.json"}\n'
        ),
    )
    replace_once(
        wrapper,
        "        if set(by_relative) != expected:\n",
        (
            "        manifest_info = by_relative.get(\"RETURN_MANIFEST.json\")\n"
            "        if manifest_info is None:\n"
            "            raise base.DiagnosticRuntimeError(\n"
            "                \"return manifest missing\"\n"
            "            )\n"
            "        return_manifest = json.loads(archive.read(manifest_info))\n"
            "        if (\n"
            "            return_manifest.get(\"schema\")\n"
            "            != \"node0004-return-manifest-v24\"\n"
            "            or return_manifest.get(\"install_name\") != root[:-7]\n"
            "        ):\n"
            "            raise base.DiagnosticRuntimeError(\n"
            "                \"return manifest identity differs\"\n"
            "            )\n"
            "        allow_receipt = return_manifest.get(\"return_allowlist\", {})\n"
            "        if (\n"
            "            allow_receipt.get(\"size_bytes\") != allow_info.file_size\n"
            "            or allow_receipt.get(\"sha256\")\n"
            "            != _stream_sha256(archive, allow_info)\n"
            "        ):\n"
            "            raise base.DiagnosticRuntimeError(\n"
            "                \"return manifest allowlist receipt differs\"\n"
            "            )\n"
            "        package_receipt = return_manifest.get(\n"
            "            \"source_package_manifest\", {}\n"
            "        )\n"
            "        package_relative = package_receipt.get(\"returned_path\")\n"
            "        package_info = by_relative.get(package_relative)\n"
            "        if (\n"
            "            package_info is None\n"
            "            or package_receipt.get(\"size_bytes\")\n"
            "            != package_info.file_size\n"
            "            or package_receipt.get(\"sha256\")\n"
            "            != _stream_sha256(archive, package_info)\n"
            "        ):\n"
            "            raise base.DiagnosticRuntimeError(\n"
            "                \"returned package manifest receipt differs\"\n"
            "            )\n"
            "        if return_manifest.get(\"records\") != records:\n"
            "            raise base.DiagnosticRuntimeError(\n"
            "                \"return manifest record set differs\"\n"
            "            )\n"
            "        if set(by_relative) != expected:\n"
        ),
    )


def update_manifest(package: Path, observer_sha: str) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": (
                "resnet50-node0004-final-release-diagnostic-compilefix-"
                "package-v24"
            ),
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item.get("reason") == "server package routing":
            item["path"] = ".agents/rules/生成前必读索引.md"
            item["sha256"] = INDEX_SHA256
        elif item.get("reason") == "common server package gates":
            item["path"] = ".agents/rules/服务器测试包生成规则.md"
            item["sha256"] = SERVER_RULE_SHA256
        elif item.get("reason") == "Conv INT8 SA accumulate release gate":
            item["path"] = ".agents/rules/INT8_SA点积专项规则.md"
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["v23_return_analysis"] = {
        "return_zip_sha256": RETURN_ZIP_SHA256,
        "source_v23_zip_sha256": SOURCE_ZIP_SHA256,
        "status": "PACKAGE_LOCAL_OBSERVER_COMPILE_FAILURE",
        "last_proven_good_this_return": (
            "PACKAGE_INSTALL_AND_OBSERVER_STATIC_PREFLIGHT_PASS"
        ),
        "first_divergence_this_return": (
            "VCS_PARSE_PACKAGE_LOCAL_OBSERVER_UNDECLARED_IDENTIFIER"
        ),
        "compile_exit_status": 2,
        "run_exit_status": 125,
        "simulation_started": False,
        "conv_dataflow_advanced": False,
        "frozen_conv_last_proven_good": (
            "SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE"
        ),
        "frozen_conv_first_divergence": (
            "SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID"
        ),
    }
    manifest["package_local_compile_fix"] = {
        "source_observer_sha256": (
            "3ecc3f0e0f276a5d4cfa9ca8267cedcad2a0b1198929217f99046595524e8723"
        ),
        "source_line": 3926,
        "undeclared_identifier": "return_obs_buf45_wr_edge_count",
        "fix": (
            "declare/reset/update a final-release-local Buffer5 write "
            "rising-edge counter and bind FINAL_RELEASE_BOUNDARY_V1 to it"
        ),
        "functional_semantics_changed": False,
    }
    manifest["return_manifest_contract"] = {
        "schema": "node0004-return-manifest-v24",
        "manifest_path": "RETURN_MANIFEST.json",
        "allowlist_path": "RETURN_ALLOWLIST.json",
        "returned_package_manifest_path": (
            "evidence/returned_package_manifest.json"
        ),
        "exact_set_validator_updated": True,
    }
    manifest["superseded_v23_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "QUARANTINED_PACKAGE_LOCAL_OBSERVER_COMPILE_FAILURE",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(path, manifest)


def readme() -> str:
    return f"""# ResNet50 node0004 v24 final-release diagnostic compile fix

This remains `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

It freezes the v23 workload/configuration/bitstream/execplan/SCA/golden and
functional RTL. It only:

1. defines and updates the Buffer5 write rising-edge counter referenced by the
   final-release observer; and
2. returns `RETURN_MANIFEST.json` plus the exact source package manifest
   receipt required by the current return contract.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip`.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v24-source-") as temp:
        source = safe_extract(Path(temp))
        shutil.copytree(source, package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_return_manifest_contract(package)
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )
    update_manifest(package, observer_sha)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer XMR gate failed: {receipt['errors']}")
    return package


def main() -> int:
    output = OUTPUT_ROOT.resolve()
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    validation = output / f"{INSTALL_NAME}.validation.json"
    for target in (package, zip_path, sidecar, validation):
        if target.exists():
            raise BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v24-repeat-") as temp:
        repeat = Path(temp)
        repeat_package = build_directory(repeat)
        repeat_zip = repeat / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v24 deterministic repeat differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report: dict[str, Any] = {
        "schema": "node0004-final-release-diagnostic-compilefix-build-v24",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_v23_sha256": SOURCE_ZIP_SHA256,
        "v23_return_sha256": RETURN_ZIP_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "deterministic_rebuild_equal": deterministic,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
