from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ENABLE_MACRO = "+define+NATIVE_RETURN_OBSERVER_ENABLE"
TIME0_MARKER = "[RETURN_OBSERVER] enabled"
REQUIRED_RETURN_TARGETS = {
    "evidence/actual_compile_argv.txt",
    "evidence/actual_simulator_argv.txt",
    "evidence/progress_samples.log",
    "evidence/observer_binding.txt",
    "logs/sim.log",
    "runs/return_observer.log",
}


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_zip(path: Path) -> tuple[str, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC differs")
        files: dict[str, bytes] = {}
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in files
                or (mode and stat.S_ISLNK(mode))
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            if not info.is_dir():
                files[info.filename] = archive.read(info)
                roots.add(pure.parts[0])
        if len(roots) != 1:
            raise ValidationError("ZIP root differs")
        return next(iter(roots)), files


def validate_payload(
    root: str, files: dict[str, bytes]
) -> dict[str, Any]:
    errors: list[str] = []
    manifest_member = f"{root}/TEST_PACKAGE_MANIFEST.json"
    try:
        manifest = json.loads(files[manifest_member].decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ValidationError("package manifest unavailable") from error
    if not isinstance(manifest, dict):
        raise ValidationError("package manifest root differs")

    records = manifest.get("files")
    if not isinstance(records, dict):
        raise ValidationError("manifest file records absent")
    declared = {f"{root}/{relative}" for relative in records}
    if declared | {manifest_member} != set(files):
        errors.append("manifest exact file set differs")
    for relative, receipt in records.items():
        member = f"{root}/{relative}"
        payload = files.get(member)
        if (
            not isinstance(receipt, dict)
            or payload is None
            or len(payload) != receipt.get("size_bytes")
            or sha256_bytes(payload) != receipt.get("sha256")
        ):
            errors.append(f"manifest receipt differs: {relative}")

    observer_contract = manifest.get("package_local_observer")
    if not isinstance(observer_contract, dict):
        errors.append("observer contract absent")
        observer_contract = {}
    observer_relative = str(
        observer_contract.get(
            "relative_path", "tb_probe/native_return_observer.svh"
        )
    )
    observer_member = f"{root}/{observer_relative}"
    observer_matches = [
        name
        for name in files
        if name.endswith("/native_return_observer.svh")
    ]
    observer_payload = files.get(observer_member)
    observer_record = records.get(observer_relative)
    manifest_expected_sha = (
        observer_record.get("sha256")
        if isinstance(observer_record, dict)
        else None
    )
    legacy_expected_sha = observer_contract.get("sha256")
    identity_pointer = observer_contract.get("identity_json_pointer")
    manifest_single_source = (
        identity_pointer
        == "/files/tb_probe~1native_return_observer.svh/sha256"
        and legacy_expected_sha is None
    )
    expected_sha = (
        manifest_expected_sha
        if manifest_single_source
        else legacy_expected_sha
    )
    source_pass = (
        len(observer_matches) == 1
        and observer_payload is not None
        and sha256_bytes(observer_payload)
        == expected_sha
        and (
            not manifest_single_source
            or manifest_expected_sha is not None
        )
    )
    if not source_pass:
        errors.append("observer source binding absent or non-unique")

    runner_member = f"{root}/PREPARE_AND_RUN.sh"
    try:
        runner = files[runner_member].decode("utf-8")
    except (KeyError, UnicodeError):
        runner = ""
    include_token = "+incdir+$package_root/tb_probe"
    include_pass = include_token in runner
    if not include_pass:
        errors.append("package-local +incdir binding absent")
    enable_pass = ENABLE_MACRO in runner
    if not enable_pass:
        errors.append("observer compile enable macro absent")
    if manifest_single_source and (
        expected_sha in runner
        or "--expected-sha256" in runner
        or '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"'
        not in runner
    ):
        errors.append("runner manifest single-source binding differs")

    allowlist_value = manifest.get("return_allowlist")
    allowlist = allowlist_value if isinstance(allowlist_value, list) else []
    targets = {
        str(item.get("target_path"))
        for item in allowlist
        if isinstance(item, dict)
    }
    runtime_tokens = (
        "+RETURN_OBSERVER",
        "+RETURN_OBS_FILE=$observer_log",
        TIME0_MARKER,
        "trap 'finalize $?' EXIT",
        "trap 'signal_name=HUP",
        "trap 'signal_name=INT",
        "trap 'signal_name=TERM",
        "actual_compile_argv.txt",
        "actual_simulator_argv.txt",
        "progress_samples.log",
        "observer_enabled_and_returned=true",
    )
    runtime_pass = (
        all(token in runner for token in runtime_tokens)
        and REQUIRED_RETURN_TARGETS <= targets
    )
    if not runtime_pass:
        errors.append("runtime/time0/return/trap binding incomplete")

    contract = manifest.get("observer_binding_contract")
    contract_pass = (
        isinstance(contract, dict)
        and contract.get("rule_id")
        == "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001"
        and contract.get("time0_enabled_marker") == TIME0_MARKER
        and contract.get("enable_macro") == ENABLE_MACRO
    )
    if not contract_pass:
        errors.append("observer four-way manifest contract differs")

    return {
        "valid": not errors,
        "status": (
            "PACKAGE_OBSERVER_BINDING_COMPLETE"
            if not errors
            else "PACKAGE_OBSERVER_BINDING_INCOMPLETE"
        ),
        "errors": errors,
        "root": root,
        "source": {
            "pass": source_pass,
            "unique_source_count": len(observer_matches),
            "relative_path": observer_relative,
            "identity_source": (
                "final_manifest_single_source"
                if manifest_single_source
                else "legacy_observer_contract"
            ),
            "identity_json_pointer": identity_pointer,
            "sha256": (
                sha256_bytes(observer_payload)
                if observer_payload is not None
                else None
            ),
        },
        "include": {
            "pass": include_pass,
            "token": include_token,
        },
        "compile_enable": {
            "pass": enable_pass,
            "macro": ENABLE_MACRO,
        },
        "runtime_return": {
            "pass": runtime_pass,
            "time0_marker": TIME0_MARKER,
            "required_return_targets":
                sorted(REQUIRED_RETURN_TARGETS),
            "allowlist_targets_present":
                sorted(REQUIRED_RETURN_TARGETS & targets),
        },
        "manifest_contract": {"pass": contract_pass},
    }


def validate_with_negative_controls(path: Path) -> dict[str, Any]:
    root, files = read_zip(path)
    positive = validate_payload(root, files)
    if not positive["valid"]:
        raise ValidationError(
            "positive binding validation failed: "
            + "; ".join(positive["errors"])
        )
    observer_member = (
        f"{root}/{positive['source']['relative_path']}"
    )
    runner_member = f"{root}/PREPARE_AND_RUN.sh"

    negative_results: dict[str, Any] = {}
    mutations: dict[str, tuple[str, str]] = {
        "delete_source": ("delete", observer_member),
        "delete_incdir": (
            "replace",
            "+incdir+$package_root/tb_probe",
        ),
        "delete_enable_macro": ("replace", ENABLE_MACRO),
        "delete_runtime_return": ("replace", "+RETURN_OBSERVER"),
    }
    for label, (operation, target) in mutations.items():
        mutated = dict(files)
        if operation == "delete":
            mutated.pop(target, None)
        else:
            runner = mutated[runner_member].decode("utf-8")
            mutated[runner_member] = runner.replace(
                target, ""
            ).encode("utf-8")
        receipt = validate_payload(root, mutated)
        negative_results[label] = {
            "failed_closed": not receipt["valid"],
            "status": receipt["status"],
            "errors": receipt["errors"],
        }
        if receipt["valid"]:
            raise ValidationError(
                f"negative control did not fail closed: {label}"
            )
    return {
        "schema": "gap-node0071-observer-four-way-validation-v1",
        "status": "PASS",
        "zip": str(path.resolve()),
        "zip_sha256": sha256_bytes(path.read_bytes()),
        "positive": positive,
        "negative_controls": negative_results,
        "negative_control_count": len(negative_results),
        "all_negative_controls_fail_closed": all(
            item["failed_closed"]
            for item in negative_results.values()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = validate_with_negative_controls(args.zip.resolve())
    text = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            text, encoding="utf-8", newline="\n"
        )
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
