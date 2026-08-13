from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_node0004_v51_ndp_root_gate_package_v52 import (
    deterministic_zip,
    sha256,
)


SOURCE = "r5_n4_hw_v52_ndproot_gate"
INSTALL = "r5_n4_hw_v53_sca_cwd_fix"
SOURCE_SHA = "b60209bae1fc19650d22a6c7df3b5c16b45b8ea9a8d50c15fb65a6e3f1b8abf6"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs/conv_node0004_v52_runtime_install_mismatch/v53_build"
)
SERVER_RULE_SHA = "b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724"
INDEX_SHA = "1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500"
PLAN_SHA = "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70"


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("v52 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise BuildError(f"v52 source CRC failed at {bad}")
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
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"v52 source root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, INSTALL),
                encoding="utf-8",
                newline="\n",
            )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{label} anchor count={text.count(old)}")
    return text.replace(old, new, 1)


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'ndp_pre_snapshot="$(python3 "$runtime" root-snapshot '
        '--server-root "$server_root")" || exit 12\n',
        'ndp_pre_snapshot="$(python3 "$runtime" root-snapshot '
        '--server-root "$server_root")" || exit 12\n'
        '[ -d "$server_root/install" ] '
        '&& [ ! -L "$server_root/install" ] || {\n'
        '  echo "Pre-existing NDP install directory required" >&2\n'
        '  exit 13\n'
        '}\n',
        "pre-existing install preflight",
    )
    text = replace_once(
        text,
        'cfg_root="${work_root}/install/cfg_pkg/${install_name}"',
        'cfg_root="${server_root}/install/cfg_pkg/${install_name}"',
        "SCA-consistent cfg root",
    )
    text = replace_once(
        text,
        '  "root_internal_write_targets": [],\n'
        '  "existing_first_level_parents": [],',
        '  "root_internal_write_targets": [\n'
        '    "install/cfg_pkg/${install_name}"\n'
        '  ],\n'
        '  "existing_first_level_parents": ["install"],',
        "root write contract",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def package_records(package: Path) -> dict[str, str]:
    manifest_path = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }


def update_manifest(package: Path) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["source_package_sha256"] = SOURCE_SHA
    manifest["runtime_install_contract"] = {
        "schema": "sca-relative-path-runtime-install-v1",
        "tb_launch_cwd": "user supplied NDP root",
        "sca_path_prefix": f"install/cfg_pkg/{INSTALL}/",
        "runtime_cfg_root": (
            f"${{server_root}}/install/cfg_pkg/{INSTALL}"
        ),
        "preexisting_first_level_parent": "install",
        "input_consumer_count": 86,
        "input_consumer_open_required_before_simulation": True,
        "sca_d_targets_must_be_absent_before_simulation": True,
        "failure_class": (
            "PACKAGE_LOCAL_RUNTIME_INSTALL_LOCATION_VS_SCA_RELATIVE_PATH_MISMATCH"
        ),
    }
    contract = manifest.setdefault("ndp_root_toplevel_contract", {})
    contract["root_internal_write_targets"] = [
        f"install/cfg_pkg/{INSTALL}"
    ]
    contract["existing_first_level_parents"] = ["install"]
    contract["work_root"] = (
        f"/home/panqs/ndp/simresult/.{INSTALL}.run.<pid>"
    )
    receipts = manifest.setdefault("active_receipts", {})
    receipts["generation_index_sha256"] = INDEX_SHA
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA
    matrix = manifest.setdefault("release_gate_matrix", [])
    matrix.append(
        {
            "gate_id": "SCA_TB_CWD_RUNTIME_OPEN",
            "applicability": "blocking_applicable",
            "blocking": True,
            "reason": (
                "v52 server log proves SCA consumers resolve relative to "
                "the NDP-root TB cwd"
            ),
            "changed_surface": [
                "PREPARE_AND_RUN.sh cfg_root",
                "pre-existing install parent preflight",
            ],
            "evidence": [
                "all 86 SCA input consumers opened from exact TB cwd",
                "matrix deletion/bitstream deletion/wrong-prefix/"
                "external-cfg-root negatives",
            ],
        }
    )
    manifest["v52_failure_adjudication"] = {
        "source_zip_sha256": SOURCE_SHA,
        "failure_class": (
            "PACKAGE_LOCAL_RUNTIME_INSTALL_LOCATION_VS_SCA_RELATIVE_PATH_MISMATCH"
        ),
        "dynamic_result_valid_for_dut_or_numeric": False,
        "replacement": INSTALL,
    }
    manifest["files"] = package_records(package)
    write_json(path, manifest)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = package_records(package)
    write_json(path, manifest)


def build_directory(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-v52-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    patch_runner(package / "PREPARE_AND_RUN.sh")
    write_json(
        package / "provenance/v52_to_v53_sca_cwd_fix.json",
        {
            "schema": "node0004-v52-to-v53-sca-cwd-fix-v1",
            "source_v52_sha256": SOURCE_SHA,
            "source_log_sha256": (
                "e2dc1750df9e2e933b6c86050d0ad152e9f84c789f62e5a8f892eaf1e54ff9a9"
            ),
            "classification": "RUNNER_ONLY_FUNCTIONAL_PACKAGE_FIX",
            "failure_class": (
                "PACKAGE_LOCAL_RUNTIME_INSTALL_LOCATION_VS_SCA_RELATIVE_PATH_MISMATCH"
            ),
            "numeric_frozen": True,
            "workload_frozen": True,
            "configuration_identity_normalized_frozen": True,
            "golden_frozen": True,
            "observer_frozen": True,
            "timeout_frozen": True,
            "functional_rtl_modified": False,
            "changed_surface": [
                "PREPARE_AND_RUN.sh runtime cfg_root and install preflight",
                "package_manifest.json",
                "README.md",
            ],
        },
    )
    (package / "README.md").write_text(
        "# node0004 v53 SCA/TB-cwd install fix\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v52 compiled and started simulation, but the TB opened every SCA "
        "path relative to the supplied NDP root while v52 installed the "
        "payload under an external work root. v53 requires the existing "
        "`$server_root/install` directory and installs the frozen payload "
        f"under `install/cfg_pkg/{INSTALL}` so all 86 SCA input consumers "
        "resolve from the real TB cwd. The NDP root direct-child name/type "
        "set remains unchanged; only an isolated subdirectory of the "
        "pre-existing `install` entry is used.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL,
        output / f"{INSTALL}.zip",
        output / f"{INSTALL}.zip.sha256",
        output / f"{INSTALL}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v53 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v53-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v53 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v52-to-v53-sca-cwd-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v52_sha256": SOURCE_SHA,
        "source_log_sha256": (
            "e2dc1750df9e2e933b6c86050d0ad152e9f84c789f62e5a8f892eaf1e54ff9a9"
        ),
        "current_server_rule_sha256": SERVER_RULE_SHA,
        "current_generation_index_sha256": INDEX_SHA,
        "builder_plan_mutable_provenance_sha256": PLAN_SHA,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "observer_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
