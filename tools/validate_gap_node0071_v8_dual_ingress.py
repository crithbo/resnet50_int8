from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


OBSERVER = "tb_probe/native_return_observer.svh"


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_zip(path: Path) -> tuple[str, dict[str, bytes]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValidationError(f"ZIP CRC differs: {bad}")
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


def validate_text(text: str) -> dict[str, Any]:
    checks = {
        "mse3_buffer4_qualified_handshake": all(
            token in text
            for token in (
                "return_obs_mse3_buf_hs_mon",
                ".MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine",
                ".mse2buf_wvalid &",
                ".buf2mse_wreq_ready;",
                "return_obs_mse3_buf_accept_count++;",
                "DEEP_MSE3_TO_BUFFER4",
            )
        ),
        "ga_operand_capture_is_qualified": (
            text.count(
                ".u_GA_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable;"
            )
            == 2
            and "return_obs_ga_operand_capture_mon" in text
            and "return_obs_ga_operand0_capture_count++;" in text
            and "return_obs_ga_operand2_capture_count++;" in text
            and "ga_pe_inport_valid_bit" not in text
        ),
        "ga_accept_is_qualified": all(
            token in text
            for token in (
                "return_obs_ga_accept_count++;",
                "return_obs_ga_p0_enable_mon",
                "return_obs_ga_input_valid_mon",
            )
        ),
        "separate_dual_ingress_summary": (
            '"%0t | DUAL_INGRESS_COUNTS | event=%s '
            "mse0_buf_accept=%0d mse3_buf_accept=%0d "
            'ga_operand0_capture=%0d ga_operand2_capture=%0d ga_accept=%0d"'
            in text
        ),
        "canonical_heartbeat_format_unchanged": (
            '"%0t | %s | slice=%0d active_cycles=%0d gexec=%0d '
            "gconfig=%0d req=%0d rdata=%0d wdata=%0d buf4_wr=%0d "
            'buf4_rd=%0d buf5_wr=%0d buf5_rd=%0d"'
            in text
        ),
        "canonical_sg_counts_format_unchanged": (
            '"%0t | SG_COUNTS | event=%s ga_input=%0d ga_output=%0d '
            "mse4_req0=%0d mse4_req1=%0d mse4_wdata0=%0d "
            "mse4_wdata1=%0d mse4_outstanding0=%0d "
            'mse4_outstanding1=%0d"'
            in text
        ),
        "functional_drive_absent": (
            "force " not in text
            and "release " not in text
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "errors": [name for name, passed in checks.items() if not passed],
    }


def mutate_once(text: str, old: str, new: str = "") -> str:
    if old not in text:
        raise ValidationError(f"negative-control target absent: {old}")
    return text.replace(old, new, 1)


def validate(path: Path) -> dict[str, Any]:
    root, files = read_zip(path)
    observer_member = f"{root}/{OBSERVER}"
    payload = files.get(observer_member)
    if payload is None:
        raise ValidationError("observer source absent")
    text = payload.decode("utf-8")
    manifest = json.loads(
        files[f"{root}/TEST_PACKAGE_MANIFEST.json"].decode("utf-8")
    )
    contract = manifest.get("dual_ingress_localization_contract")
    positive = validate_text(text)
    contract_valid = (
        isinstance(contract, dict)
        and contract.get("summary_record") == "DUAL_INGRESS_COUNTS"
        and contract.get("canonical_progress_predicate_changed") is False
        and contract.get("level_only_activity_counts_as_progress") is False
        and contract.get("functional_behavior_changed") is False
    )
    if not positive["valid"] or not contract_valid:
        raise ValidationError(
            "positive dual-ingress validation failed: "
            + ", ".join(positive["errors"])
        )

    mutations = {
        "delete_mse3_binding": text.replace("MSE_INST[3]", "MSE_INST[0]"),
        "delete_ga_capture_binding": text.replace(
            "ga_pe_inbuffer_enable;", "ga_pe_inport_valid_bit;", 2
        ),
        "substitute_level_for_qualified_capture": text.replace(
            "ga_pe_inbuffer_enable;", "ga_pe_inport_valid_bit;", 2
        ),
        "delete_dual_ingress_summary": mutate_once(
            text, "DUAL_INGRESS_COUNTS", "DUAL_INGRESS_REMOVED"
        ),
    }
    controls: dict[str, Any] = {}
    for name, mutated in mutations.items():
        result = validate_text(mutated)
        controls[name] = {
            "failed_closed": not result["valid"],
            "errors": result["errors"],
        }
        if result["valid"]:
            raise ValidationError(
                f"negative control did not fail closed: {name}"
            )

    return {
        "schema": "gap-node0071-v8-dual-ingress-validation-v1",
        "status": "PASS",
        "zip": str(path.resolve()),
        "zip_sha256": sha256_bytes(path.read_bytes()),
        "observer_member": observer_member,
        "observer_sha256": sha256_bytes(payload),
        "positive": positive,
        "manifest_contract_valid": contract_valid,
        "negative_controls": controls,
        "negative_control_count": len(controls),
        "all_negative_controls_fail_closed": all(
            item["failed_closed"] for item in controls.values()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = validate(args.zip.resolve())
    text = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
