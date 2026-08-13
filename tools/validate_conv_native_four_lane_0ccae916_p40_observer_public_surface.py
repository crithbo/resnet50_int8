#!/usr/bin/env python3
"""Gate the p40 Datahub observer repair against the exact final ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p40_dhpubfix"
RTL_TOP = ROOT / "NDP_copy01/rtl/Datahub/datahub_top.sv"
RTL_CHANNEL = ROOT / "NDP_copy01/rtl/Datahub/Request_Queue/local_req_full_channel.sv"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def observer_errors(text: str) -> list[str]:
    errors: list[str] = []
    root = (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
        "slice_group_gen[0].u_datahub_top_wrapper.u_datahub_top"
    )
    if "arb_req_ready" in text:
        errors.append("private arb_req_ready XMR remains")
    for channel in (8, 9):
        grant = (
            f"dh_grant_{channel} = dh_head_{channel} && {root}.local_channel2hub_req_valid[{channel}] && "
            f"{root}.local_channel2hub_req_rwflag[{channel}];"
        )
        accept = f"dh_accept_{channel} = dh_grant_{channel} && {root}.local_channel2hub_req_ready[{channel}];"
        if text.count(grant) != 1:
            errors.append(f"channel {channel} public write-selection expression missing or duplicated")
        if text.count(accept) != 1:
            errors.append(f"channel {channel} public acceptance expression missing or duplicated")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        safe = all(
            not PurePosixPath(row.filename).is_absolute()
            and ".." not in PurePosixPath(row.filename).parts
            and "\\" not in row.filename
            and not stat.S_ISLNK(row.external_attr >> 16)
            for row in infos
        )
        if archive.testzip() is not None or not safe or len(names) != len(set(names)):
            errors.append("exact ZIP is corrupt, unsafe or contains duplicate members")
        observer_member = f"{PACKAGE}/tb_probe/native_return_observer.svh"
        helper_member = f"{PACKAGE}/package_tools/compile_core_evidence.py"
        manifest_member = f"{PACKAGE}/package_manifest.json"
        if not all(member in names for member in (observer_member, helper_member, manifest_member)):
            errors.append("required p40 exact-ZIP member absent")
            observer = b""
            helper = b""
            manifest: dict[str, Any] = {}
        else:
            observer = archive.read(observer_member)
            helper = archive.read(helper_member)
            manifest = json.loads(archive.read(manifest_member))
    observer_text = observer.decode("utf-8", "replace")
    errors.extend(observer_errors(observer_text))
    files = manifest.get("files", {})
    observer_declared = files.get("tb_probe/native_return_observer.svh", {})
    helper_declared = files.get("package_tools/compile_core_evidence.py", {})
    if observer_declared != {"sha256": sha_bytes(observer), "size_bytes": len(observer)}:
        errors.append("manifest observer receipt mismatch")
    if helper_declared != {"sha256": sha_bytes(helper), "size_bytes": len(helper)}:
        errors.append("manifest compile helper receipt mismatch")

    top = RTL_TOP.read_text(encoding="utf-8")
    channel = RTL_CHANNEL.read_text(encoding="utf-8")
    rtl_checks = {
        "module_surface_valid_declared": "wire [LOCAL_REQ_NUM-1:0]                        local_channel2hub_req_valid;" in top,
        "module_surface_rwflag_declared": "wire [LOCAL_REQ_NUM-1:0]                        local_channel2hub_req_rwflag;" in top,
        "module_surface_ready_declared": "wire [LOCAL_REQ_NUM-1:0]                        local_channel2hub_req_ready;" in top,
        "valid_is_selected_request": "assign local_channel2hub_req_valid  = (arb_req_ready[1]) ? local_channel2hub_req_rd_valid" in channel,
        "rwflag_marks_write_selection": "assign local_channel2hub_req_rwflag = (arb_req_ready[1]) ? 1'b0 : 1'b1;" in channel,
        "write_accept_is_grant_and_downstream_ready": "assign local_channel2hub_req_wr_ready = arb_req_ready[0] && local_channel2hub_req_ready;" in channel,
    }
    errors.extend(name for name, passed in rtl_checks.items() if not passed)

    positive = not observer_errors(observer_text)
    legacy_negative_text = observer_text.replace(
        ".local_channel2hub_req_valid[8] &&",
        ".local_req_full_channels[8].wr_en.u_local_req_full_channel.arb_req_ready[0] &&",
        1,
    )
    legacy_negative = bool(observer_errors(legacy_negative_text))
    missing_ready_text = observer_text.replace(".local_channel2hub_req_ready[9];", ".local_channel2hub_req_valid[9];", 1)
    missing_ready_negative = bool(observer_errors(missing_ready_text))

    structured_first_error = False
    warning_rejected = False
    with tempfile.TemporaryDirectory(prefix="p40_first_error_") as temporary:
        root = Path(temporary)
        helper_path = root / "compile_core_evidence.py"
        helper_path.write_bytes(helper)
        (root / "compile_driver.log").write_text(
            "Warning: The error message report included Ubuntu VERSION_ID=22.04\n"
            "Error-[XMRE] Cross-module reference resolution error\n"
            "token 'arb_req_ready'\n",
            encoding="utf-8",
            newline="\n",
        )
        result = subprocess.run(
            [sys.executable, str(helper_path), "finalize", "--output-root", str(root), "--exit-code", "2"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            first = (root / "compile_first_error.txt").read_text(encoding="utf-8")
            structured_first_error = first.startswith("Error-[XMRE]")
            warning_rejected = "Ubuntu VERSION_ID" not in first.splitlines()[0]
    controls = {
        "positive_exact_observer": positive,
        "legacy_private_xmr_negative": legacy_negative,
        "missing_ready_negative": missing_ready_negative,
        "structured_first_error_selected": structured_first_error,
        "platform_warning_false_positive_rejected": warning_rejected,
    }
    errors.extend(name for name, passed in controls.items() if not passed)
    report = {
        "schema": "conv-native-four-lane-p40-observer-public-surface-gate-v1",
        "pass": not errors,
        "valid": not errors,
        "errors": errors,
        "package_identity": PACKAGE,
        "exact_zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "observer": {"member": f"{PACKAGE}/tb_probe/native_return_observer.svh", "bytes": len(observer), "sha256": sha_bytes(observer)},
        "rtl_public_surface_provenance_hint": {
            "authoritative_for_server_compile": False,
            "datahub_top": {"path": RTL_TOP.relative_to(ROOT).as_posix(), "bytes": RTL_TOP.stat().st_size, "sha256": sha(RTL_TOP)},
            "local_req_full_channel": {"path": RTL_CHANNEL.relative_to(ROOT).as_posix(), "bytes": RTL_CHANNEL.stat().st_size, "sha256": sha(RTL_CHANNEL)},
            "checks": rtl_checks,
        },
        "semantic_controls": controls,
        "claim_boundary": "Static exact-ZIP observer/public-surface and first-error collector gate only; actual production compile remains unproven until a formal p40 return.",
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(args.output, report)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.output)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
