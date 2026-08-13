from __future__ import annotations

import argparse
import copy
import hashlib
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


SOURCE = "r5_n4_hw_v60_install_only"
INSTALL = "r5_n4_hw_v61_lcmap_argv_fix"
SOURCE_SHA = "cb3342e90510e4cd1e66afb9a19977cc5eae725abccf987346757d3d34937ec8"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v60_return_v61_successor/build"
SERVER_RULE_SHA = (
    "16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde"
)
INDEX_SHA = (
    "68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be"
)
CONVERGENCE_SHA = (
    "f51525f8db7d8b8e79e57ea194c7d9f6624a320e5754df4dfd164ddc5e50687b"
)
MAPPING_PATH = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p9-tx5-c0/execplan_conv/wave-0/"
    "pipeline_output/config/op_w0/mapping_review.json"
)


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract_source(destination: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("v60 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v60 source CRC differs")
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
                raise BuildError(f"unsafe/duplicate source member:{info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"v60 source root differs:{sorted(roots)}")
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
                text.replace(SOURCE, INSTALL), encoding="utf-8", newline="\n"
            )


def bounded_span(text: str, begin: str, end: str) -> tuple[int, int, str]:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise BuildError(f"observer span differs:{begin}")
    start = text.index(begin)
    finish = text.index(end, start) + len(end)
    return start, finish, text[start:finish]


def replace_physical_indices(
    block: str, replacements: tuple[tuple[int, int], ...]
) -> str:
    result = block
    placeholders: dict[str, str] = {}
    for old, new in replacements:
        for prefix in (
            "IGA_LC",
            "iga_lc_outport",
            "iga_lc_outport_bp_post",
        ):
            token = f"{prefix}[{old}]"
            marker = f"{prefix}[__MAP_{old}_TO_{new}__]"
            result = result.replace(token, marker)
            placeholders[marker] = f"{prefix}[{new}]"
    for marker, target in placeholders.items():
        result = result.replace(marker, target)
    return result


def patch_observer(package: Path) -> tuple[str, str]:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    old_sha = hashlib.sha256(text.encode()).hexdigest()

    d_begin = "// v50 DTERM_OWNER_ACTUAL_CONSUMER_BEGIN"
    d_end = "// v50 DTERM_OWNER_ACTUAL_CONSUMER_END"
    start, finish, block = bounded_span(text, d_begin, d_end)
    block = replace_physical_indices(
        block, ((13, 6), (14, 8), (15, 17), (9, 18))
    )
    block = block.replace(
        d_begin,
        d_begin
        + "\n"
        + "    // v61 mapper binding: logical 13/14/15/9 -> physical 6/8/17/18.",
        1,
    )
    text = text[:start] + block + text[finish:]

    x_begin = "// v51 LC13_LC14_ACTUAL_CONSUMER_BEGIN"
    x_end = "// v51 LC13_LC14_ACTUAL_CONSUMER_END"
    start, finish, block = bounded_span(text, x_begin, x_end)
    block = replace_physical_indices(block, ((13, 6), (14, 8), (15, 17)))
    block = block.replace(
        x_begin,
        x_begin
        + "\n"
        + "    // v61 mapper binding: logical 13/14/15 -> physical 6/8/17.",
        1,
    )
    block = block.replace(
        "schema=LC13_LC14",
        "schema=LC13_LC14 mapping=logical13_14_15_physical6_8_17",
    )
    text = text[:start] + block + text[finish:]
    path.write_text(text, encoding="utf-8", newline="\n")
    return old_sha, sha256(path)


def actual_sim_argv_line() -> str:
    return (
        '"$simv -l $run_root/c0/sim.log +vcs+lic+wait '
        '+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json '
        '+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json '
        "+RETURN_OBSERVER "
        "+RETURN_OBS_MSE4_DESCRIPTOR +RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96 "
        "+RETURN_OBS_MSE4_INDEX +RETURN_OBS_MSE4_INDEX_LIMIT=96 "
        "+RETURN_OBS_LC18_PE7 +RETURN_OBS_LC18_PE7_LIMIT=96 "
        "+RETURN_OBS_ROWLC4_BUFAG +RETURN_OBS_ROWLC4_BUFAG_LIMIT=128 "
        "+RETURN_OBS_B5RD +RETURN_OBS_B5RD_LIMIT=96 "
        "+RETURN_OBS_DWRITE_PATH +RETURN_OBS_DWRITE_PATH_LIMIT=64 "
        "+RETURN_OBS_DATAHUB_DRAIN +RETURN_OBS_DATAHUB_DRAIN_LIMIT=64 "
        "+RETURN_OBS_WRDRAIN +RETURN_OBS_WRDRAIN_LIMIT=1 "
        "+RETURN_OBS_WRTERM +RETURN_OBS_WRTERM_LIMIT=96 "
        "+RETURN_OBS_LC9_SPLIT +RETURN_OBS_LC9_SPLIT_LIMIT=128 "
        "+RETURN_OBS_LC9_ACTUAL +RETURN_OBS_LC9_ACTUAL_LIMIT=192 "
        "+RETURN_OBS_DTERM_OWNER +RETURN_OBS_DTERM_OWNER_LIMIT=96 "
        "+RETURN_OBS_LC13_LC14 +RETURN_OBS_LC13_LC14_LIMIT=128 "
        "+RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=4096 "
        "+RETURN_OBS_HEARTBEAT_CYCLES=262144 +RETURN_HANG_DIAG "
        "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144 "
        "+RETURN_HANG_DIAG_STALL_WINDOWS=4 "
        "+RETURN_HANG_DIAG_MAX_CYCLES=8388608 "
        '+RETURN_OBS_FILE=$run_root/c0/return_observer.log"'
    )


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = (
        "printf '%s\\n'   "
        '"$simv -l $run_root/c0/sim.log +vcs+lic+wait '
        "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json "
        "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json "
        "+RETURN_OBSERVER "
        '+RETURN_OBS_FILE=$run_root/c0/return_observer.log"   '
        '> "$run_root/c0/simulator_argv.txt"'
    )
    new = (
        "printf '%s\\n'   "
        + actual_sim_argv_line()
        + '   > "$run_root/c0/simulator_argv.txt"'
    )
    if text.count(old) != 1:
        raise BuildError("v60 simulator argv receipt anchor differs")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def replace_hash(value: object, old: str, new: str) -> object:
    if isinstance(value, dict):
        return {key: replace_hash(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_hash(item, old, new) for item in value]
    if value == old:
        return new
    return value


def package_records(package: Path) -> dict[str, str]:
    manifest_path = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }


def update_path_budget(package: Path) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    manifest_path = package / "package_manifest.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    longest = budget["longest_projected_relative_path"]
    longest_chars = len(longest)
    root_chars = contract["path_budget"]["declared_target_root_max_chars"]
    projected = root_chars + 1 + longest_chars
    budget["longest_projected_relative_path_chars"] = longest_chars
    budget["max_projected_absolute_path_chars"] = projected
    budget["pass"] = projected <= budget["absolute_path_limit_chars"]
    contract["path_budget"]["max_projected_absolute_path_chars"] = projected
    write_json(contract_path, contract)
    write_json(manifest_path, manifest)


def update_manifest(
    package: Path, old_observer_sha: str, new_observer_sha: str
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest = replace_hash(manifest, old_observer_sha, new_observer_sha)
    assert isinstance(manifest, dict)
    manifest["install_name"] = INSTALL
    manifest["source_package_sha256"] = SOURCE_SHA
    receipts = manifest.setdefault("active_receipts", {})
    receipts["generation_index_sha256"] = INDEX_SHA
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA
    receipts["convergence_rule_sha256"] = CONVERGENCE_SHA
    manifest["v60_return_adjudication"] = {
        "return_sha256":
            "6cd43cd7bbea1c2e2dd37c409b7f4cca7eba2468fd2bca645945f49b4fadf0d2",
        "status": "PACKAGE_LOCAL_OBSERVER_MAPPING_AND_ARGV_RECEIPT_DEFECT",
        "replacement": INSTALL,
        "logical_to_physical": {
            "DRAM_LC.LC13": "LC6",
            "DRAM_LC.LC14": "LC8",
            "DRAM_LC.LC15": "LC17",
            "DRAM_LC.LC9": "LC18",
        },
    }
    matrix = [
        row
        for row in manifest.get("release_gate_matrix", [])
        if row.get("gate_id")
        not in {"PACKAGE_LOCAL_HDL", "DIAGNOSTIC_SEMANTICS"}
    ]
    matrix.extend(
        [
            {
                "gate_id": "PACKAGE_LOCAL_HDL",
                "applicability": "blocking_applicable",
                "blocking": True,
                "status": "PASS_PENDING_FINAL_ZIP_VALIDATION",
                "changed_surface": [
                    "tb_probe/native_return_observer.svh mapped LC indices"
                ],
            },
            {
                "gate_id": "DIAGNOSTIC_SEMANTICS",
                "applicability": "blocking_applicable",
                "blocking": True,
                "status": "PASS_PENDING_FINAL_ZIP_VALIDATION",
                "changed_surface": [
                    "logical-to-physical LC chain",
                    "exact simulator argv receipt",
                ],
            },
        ]
    )
    manifest["release_gate_matrix"] = matrix
    manifest["files"] = package_records(package)
    write_json(path, manifest)
    manifest["files"] = package_records(package)
    write_json(path, manifest)


def build_directory(output: Path) -> Path:
    package = output / INSTALL
    if package.exists():
        raise BuildError(f"refusing to overwrite:{package}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-v60-source-") as temp:
        shutil.copytree(extract_source(Path(temp)), package)
    replace_identity(package)
    old_observer_sha, new_observer_sha = patch_observer(package)
    patch_runner(package)
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    node_to_resource = {
        item["node"]: item["resource"] for item in mapping["node_to_resource"]
    }
    expected = {
        "DRAM_LC.LC13": "LC6",
        "DRAM_LC.LC14": "LC8",
        "DRAM_LC.LC15": "LC17",
        "DRAM_LC.LC9": "LC18",
    }
    if any(node_to_resource.get(key) != value for key, value in expected.items()):
        raise BuildError("mapping proof differs")
    provenance = {
        "schema": "node0004-v60-to-v61-lcmap-argv-fix-v1",
        "source_v60_sha256": SOURCE_SHA,
        "classification": "PACKAGE_LOCAL_DIAGNOSTIC_FIX",
        "v60_return_sha256":
            "6cd43cd7bbea1c2e2dd37c409b7f4cca7eba2468fd2bca645945f49b4fadf0d2",
        "mapping_review": {
            "path": MAPPING_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256(MAPPING_PATH),
            "logical_to_physical": expected,
        },
        "changed_surface": [
            "fresh identity",
            "observer logical-to-physical LC indices",
            "simulator_argv exact actual diagnostic command receipt",
            "manifest/provenance/README",
        ],
        "frozen": [
            "numeric",
            "W3",
            "qparam",
            "tail",
            "workload",
            "config",
            "mapping",
            "bitstream",
            "execplan",
            "SCA except identity-only strings",
            "golden",
            "timeout",
            "backpressure",
            "functional RTL",
            "ISA",
            "hardware",
            "active ndp-sim",
        ],
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(
        package / "provenance/v60_to_v61_lcmap_argv_fix.json",
        provenance,
    )
    readme = package / "README.md"
    readme.write_text(
        "# node0004 v61 mapped-loop diagnostic fix\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v61 keeps the v60 workload/config/bitstream/execplan/SCA/golden and "
        "runtime-layout behavior frozen. It corrects only the observer's "
        "logical-to-physical loop mapping (logical LC13/14/15/9 are physical "
        "LC6/8/17/18) and records the exact actual simulation argv including "
        "all diagnostic plusargs.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    update_path_budget(package)
    update_manifest(package, old_observer_sha, new_observer_sha)
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
        raise BuildError("refusing to overwrite existing v61 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v61-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v61 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v60-to-v61-lcmap-argv-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v60_sha256": SOURCE_SHA,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "mapping_rebuilt": False,
        "bitstream_rebuilt": False,
        "execplan_rebuilt": False,
        "sca_semantics_rebuilt": False,
        "observer_rebuilt": True,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
