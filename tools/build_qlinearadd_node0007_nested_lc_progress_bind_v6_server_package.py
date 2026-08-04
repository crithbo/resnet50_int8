from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    build_qlinearadd_node0007_nested_lc_progress_v5_server_package as v5,
)
from tools import build_qlinearadd_node0007_server_package as implementation
from tools.qlinearadd_node0007_server_runtime import (
    file_records,
    preflight as runtime_preflight,
)


INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_bind_v6"
SOURCE_INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_v5"
SOURCE_ZIP_SHA256 = (
    "f184410ced99830d4737bea58ccd0590e87ae0525c77d95265b0ef756a184a8e"
)
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_progress_bind_diagnostic_v6.json"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/"
    "20260730_qlinearadd_node0007_progress_v5_return_analysis.md"
)
SERVER_RULE_REL = Path(".agents/rules/服务器测试包生成规则.md")
SERVER_RULE_SHA256 = (
    "06ec5cde2920f6aa0f11e4a2ec23d9cec2621015afe706ab8ec83e3d4603089c"
)
OBSERVER_SOURCE = ROOT / "NDP_copy01/native_return_observer.svh"
OBSERVER_REL = Path("tb_probe/native_return_observer.svh")
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
PROGRESS_ALLOWLIST_COUNT = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _return_allowlist(
    readbacks: list[dict[str, object]],
) -> list[dict[str, object]]:
    records = v5._diagnostic_allowlist(readbacks)
    records.append(
        {
            "source_root": "evidence",
            "source_path": "actual_compile_argv.txt",
            "target_path": "evidence/actual_compile_argv.txt",
            "required": True,
            "max_bytes": 1 << 20,
            "missing_meaning": (
                "actual package-local include directory and observer enable "
                "macro compile binding unavailable"
            ),
        }
    )
    return records


def _run_script() -> str:
    text = v5._run_script()
    anchor = 'cd "$server_root"\nset +e\n'
    replacement = (
        'observer_source="$package_root/tb_probe/native_return_observer.svh"\n'
        '[ -r "$observer_source" ] || { '
        'echo "package observer source is not readable" >&2; exit 7; }\n'
        'cd "$server_root"\n'
        'set +e\n'
        "printf '%s\\n' \\\n"
        '  "make -f Makefile.tb_NDP_Top_new_phy compile '
        'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 '
        'RUN_DIR=$run_root '
        'VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe'
        ' +define+NATIVE_RETURN_OBSERVER_ENABLE" \\\n'
        '  >"$evidence_root/actual_compile_argv.txt"\n'
    )
    if text.count(anchor) != 1:
        raise RuntimeError("v5 compile preamble anchor differs")
    text = text.replace(anchor, replacement, 1)
    old = 'VCS_EXTRA_OPTS="+define+NATIVE_RETURN_OBSERVER_ENABLE"'
    new = (
        'VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe '
        '+define+NATIVE_RETURN_OBSERVER_ENABLE"'
    )
    if text.count(old) != 1:
        raise RuntimeError("v5 observer macro binding anchor differs")
    return text.replace(old, new, 1)


_BASE_BUILD_DIRECTORY = v5._diagnostic_build_directory


def _build_directory(destination: Path) -> Path:
    if sha256(OBSERVER_SOURCE) != OBSERVER_SHA256:
        raise RuntimeError("read-only observer source SHA256 drifted")
    package = _BASE_BUILD_DIRECTORY(destination)
    observer_target = package / OBSERVER_REL
    observer_target.parent.mkdir()
    shutil.copyfile(OBSERVER_SOURCE, observer_target)
    if sha256(observer_target) != OBSERVER_SHA256:
        raise RuntimeError("packaged observer source SHA256 mismatch")

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = implementation.load_json(manifest_path)
    manifest.update(
        {
            "schema": (
                "qlinearadd-node0007-nested-lc-progress-bind-"
                "server-package-v6"
            ),
            "server_rtl_entries": 0,
            "server_tb_or_observer_entries": 1,
            "observer_binding_fix": {
                "root_cause": "PACKAGE_OBSERVER_INCLUDE_SOURCE_NOT_BOUND",
                "source_path": OBSERVER_REL.as_posix(),
                "sha256": OBSERVER_SHA256,
                "installation_mode": "PACKAGE_LOCAL_INCLUDE_ONLY",
                "server_source_modified": False,
                "compile_include_directory": "$package_root/tb_probe",
                "compile_enable_macro": "NATIVE_RETURN_OBSERVER_ENABLE",
                "read_only": True,
                "drives_dut": False,
                "changes_timeout": False,
                "changes_workload": False,
            },
            "superseded_diagnostic": {
                "zip": (
                    "artifacts/operator_config_validation/"
                    "r5-server-test-packages/"
                    f"{SOURCE_INSTALL_NAME}.zip"
                ),
                "sha256": SOURCE_ZIP_SHA256,
                "reason": (
                    "v5 selected the guarded observer branch but did not bind "
                    "a readable observer include source"
                ),
            },
        }
    )
    manifest["files"] = file_records(package)
    implementation.write_json(manifest_path, manifest)
    runtime_preflight(package)
    return package


def configure() -> None:
    v5.INSTALL_NAME = INSTALL_NAME
    v5.CONTRACT_REL = CONTRACT_REL
    v5.TASK_RECORD_REL = TASK_RECORD_REL
    v5.SERVER_RULE_REL = SERVER_RULE_REL
    v5.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v5.PROGRESS_ALLOWLIST_COUNT = PROGRESS_ALLOWLIST_COUNT
    v5.configure()

    implementation.INSTALL_NAME = INSTALL_NAME
    implementation.MANIFEST_SCHEMA = (
        "qlinearadd-node0007-nested-lc-progress-bind-server-package-v6"
    )
    implementation.PACKAGE_DESCRIPTION = (
        "ResNet50 node0007 nested-LC read-only progress diagnostic with "
        "package-local observer include binding"
    )
    implementation.GENERATOR_REL = (
        "tools/"
        "build_qlinearadd_node0007_nested_lc_progress_bind_v6_server_package.py"
    )
    implementation.CONTRACT_REL = CONTRACT_REL
    implementation.TASK_RECORD_REL = TASK_RECORD_REL
    implementation.SERVER_RULE_REL = SERVER_RULE_REL
    implementation.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    implementation.SUPERSEDED_IDENTITY = {
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_INSTALL_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "reason": (
            "v5 progress diagnostic compile failed because its enabled "
            "relative observer include source was not bound"
        ),
        "functional_workload_unchanged": True,
    }
    implementation._return_allowlist = _return_allowlist
    implementation.run_script = _run_script
    implementation.build_directory = _build_directory


def main() -> int:
    configure()
    result = implementation.main()
    if result:
        return result
    validation_path = (
        implementation.OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    )
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    report.update(
        {
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "observer_source_packaged": True,
            "observer_source_sha256": OBSERVER_SHA256,
            "observer_compile_include_bound": True,
            "observer_compile_macro_bound": True,
            "progress_return_allowlist_count": PROGRESS_ALLOWLIST_COUNT,
        }
    )
    implementation.write_json(validation_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
