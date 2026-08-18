#!/usr/bin/env python3
"""Build v91 from the exact v90 package, changing only derived identity and
the post-compile log-normalizer arity defect."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
OLD_ID = "r5_n4_hw_v90b_nativeflow"
PACKAGE_ID = "r5_n4_hw_v91b_normfix"
FAMILY = "conv_serialized_node0004"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{OLD_ID}.zip"
)
ANALYSIS = ROOT / "outputs/conv_node0004_v90b_formal_return_analysis1/formal_return_analysis.json"
OUT = ROOT / "outputs/conv_node0004_v91b_normfix_release1"
BUILD_ROOT = OUT / "build" / PACKAGE_ID
FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"
TEXT_SUFFIXES = {
    ".json", ".md", ".sh", ".py", ".sv", ".svh", ".v", ".vh", ".txt"
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_extract() -> list[dict[str, object]]:
    receipts: list[dict[str, object]] = []
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("source ZIP CRC failure")
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename:
                raise RuntimeError(f"unsafe source member: {info.filename}")
            if not name.parts or name.parts[0] != OLD_ID:
                raise RuntimeError(f"source root mismatch: {info.filename}")
            relative = PurePosixPath(*name.parts[1:])
            if not relative.parts:
                continue
            data = archive.read(info)
            target = BUILD_ROOT.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            transformed = False
            if target.suffix.lower() in TEXT_SUFFIXES:
                text = data.decode("utf-8")
                updated = text.replace(OLD_ID, PACKAGE_ID)
                transformed = updated != text
                data = updated.encode("utf-8")
            target.write_bytes(data)
            mode = info.external_attr >> 16
            if mode & stat.S_IXUSR:
                target.chmod(0o755)
            receipts.append({
                "source_member": info.filename,
                "target_member": f"{PACKAGE_ID}/{relative.as_posix()}",
                "source_bytes": info.file_size,
                "source_sha256": sha(archive.read(info)),
                "target_bytes": len(data),
                "target_sha256": sha(data),
                "identity_text_relocated": transformed,
            })
    return receipts


def file_map() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
        data = path.read_bytes()
        result.append({
            "path": path.relative_to(BUILD_ROOT).as_posix(),
            "bytes": len(data),
            "sha256": sha(data),
        })
    return result


def deterministic_zip() -> None:
    temporary = FINAL_ZIP.with_name(f".{FINAL_ZIP.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for path in sorted(item for item in BUILD_ROOT.rglob("*") if item.is_file()):
            relative = path.relative_to(BUILD_ROOT.parent).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 8, 14, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            )
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("generated ZIP CRC failure")
    os.replace(temporary, FINAL_ZIP)


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    BUILD_ROOT.mkdir(parents=True)
    import_receipts = safe_extract()

    runner_path = BUILD_ROOT / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    defective = (
        'python3 - "$compile_log" "$compile_driver_log" "$compile_first_error_txt" '
        '"$compile_log_head_txt" "$compile_log_tail_txt" "$compile_full_log" <<\'PY\''
    )
    corrected = (
        'python3 - "$compile_log" "$compile_driver_log" "$compile_first_error_txt" '
        '"$compile_log_head_txt" "$compile_log_tail_txt" <<\'PY\''
    )
    if runner.count(defective) != 1:
        raise RuntimeError("exact v90 defective normalizer invocation not found once")
    runner = runner.replace(defective, corrected)
    if "s,d,f,h,t=map(pathlib.Path,sys.argv[1:])" not in runner:
        raise RuntimeError("five-target normalizer unpack missing")
    runner_path.write_text(runner, encoding="utf-8", newline="\n")
    runner_path.chmod(0o755)

    shutil.copyfile(ANALYSIS, BUILD_ROOT / "provenance/v90b_formal_return_analysis.json")
    write_json(
        BUILD_ROOT / "contracts/compile_log_normalizer_arity_contract.json",
        {
            "schema": "server-compile-log-normalizer-arity-contract-v1",
            "package_id": PACKAGE_ID,
            "source_package_id": OLD_ID,
            "activation_epoch": "node0004-compile-normalizer-arity-fix-v1",
            "input_paths": [
                "compile_log", "compile_driver_log", "compile_first_error_txt",
                "compile_log_head_txt", "compile_log_tail_txt",
            ],
            "python_unpack_targets": ["s", "d", "f", "h", "t"],
            "compile_log_is_complete_log": True,
            "duplicate_compile_full_log_argument": False,
            "positive_exact_arity_required": True,
            "six_to_five_negative_control_required": True,
            "claim_boundary": "Package-local post-compile evidence normalization only; no compile, simulation or DUT claim.",
        },
    )

    runner_contract_path = BUILD_ROOT / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = sha(runner_path.read_bytes())
    runner_contract["compile_log_normalizer_arity_contract"] = (
        f"{PACKAGE_ID}/contracts/compile_log_normalizer_arity_contract.json"
    )
    write_json(runner_contract_path, runner_contract)

    post_contract_path = BUILD_ROOT / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = sha(
        (BUILD_ROOT / "contracts/server_post_sim_return_request.json").read_bytes()
    )
    write_json(post_contract_path, post_contract)

    observer_contract = json.loads(
        (BUILD_ROOT / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8")
    )
    manifest_path = BUILD_ROOT / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "package_id": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "status": "PACKAGE_BUILT_AWAITING_CURRENT_GATES",
        "source_package": OLD_ID,
        "diagnostic_predecessor": OLD_ID,
        "runtime_preflight_native_flow_activation_epoch": "runtime-preflight-native-flow-v1",
        "package_local_normalizer_fix_epoch": "node0004-compile-normalizer-arity-fix-v1",
        "observer_only_contract_sha256": sha(
            (json.dumps(observer_contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        ),
        "previous_version_progress": "v90b production compile/elaboration/link passed, resolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf and generated simv, but a package-local six-argument to five-target compile-log normalizer exited under set -e before source identity refresh and simulation start.",
        "current_purpose": "Remove only the duplicate sixth normalizer argument so the already successful native compile can proceed through source identity binding, simv supervision and the frozen 38-net/26-role observer.",
        "server_actions_performed": [],
    })
    manifest["files"] = []
    write_json(manifest_path, manifest)

    readme = f"""# {PACKAGE_ID}

Formal serialized Conv observer-only successor for the package-local compile-log normalizer fix.

Previous progress: v90b production compile/elaboration/link passed, DesignWare modules resolved and the exact simv executable was generated. The runner then stopped before simulation because it passed six paths to a Python normalizer that unpacked five.

Current purpose: remove only the duplicate sixth `compile_full_log` argument; `compile_log` already names that exact complete log. The corrected native flow should continue to actual-source binding, simv supervision and the frozen 38-net/26-role observer.

Run only when separately authorized:

    bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01

Config, numeric, workload, golden, functional RTL, causal target, dump profile 0/0/0, observer budget and native-flow semantics are frozen. The retired ACK comparator remains absent.
"""
    (BUILD_ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    manifest["files"] = [row for row in file_map() if row["path"] != "package_manifest.json"]
    write_json(manifest_path, manifest)
    deterministic_zip()
    write_json(
        OUT / "build_receipt.json",
        {
            "schema": "node0004-v91b-normalizerfix-build-v1",
            "package_id": PACKAGE_ID,
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "bytes": SOURCE_ZIP.stat().st_size,
                "sha256": sha_file(SOURCE_ZIP),
            },
            "source_member_count": len(import_receipts),
            "identity_relocation_count": sum(
                1 for row in import_receipts if row["identity_text_relocated"]
            ),
            "authorized_functional_change": "remove duplicate sixth compile_full_log normalizer argument",
            "zip": {
                "path": FINAL_ZIP.relative_to(ROOT).as_posix(),
                "bytes": FINAL_ZIP.stat().st_size,
                "sha256": sha_file(FINAL_ZIP),
            },
            "pass": True,
            "errors": [],
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
