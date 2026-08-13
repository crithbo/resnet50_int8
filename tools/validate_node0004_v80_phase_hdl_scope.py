from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v80_ack_phase_diag"
TARGET = Path("NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv")
FIFO = Path("NDP_copy01/rtl/utils/FIFO/FIFO.sv")
INCLUDES = Path("NDP_copy01/rtl/includes")
EXPECTED_TARGET_SHA = "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declared(source: str, name: str) -> bool:
    # Exact identifier presence in a declaration or module port.  This is the
    # focused fallback for Icarus, whose frontend does not parse SV bind.
    patterns = (rf"\b(?:input|output|inout|wire|reg|logic)\b[^;\n]*\b{re.escape(name)}\b",)
    return any(re.search(pattern, source) for pattern in patterns)


def mapping(observer: str) -> dict[str, str]:
    match = re.search(
        r"bind\s+Buffer_AG_Idx_Queue\s+codex_probe_buf_ack_phase_witness\s+"
        r"codex_probe_buf_ack_phase_witness_inst\s*\((.*?)\)\s*;",
        observer,
        re.S,
    )
    if not match:
        return {}
    return dict(re.findall(r"\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\)", match.group(1)))


def compile_one(iverilog: Path, output: Path, sources: list[Path], top: str, defines: list[str] | None = None) -> dict:
    command = [str(iverilog), "-g2012", "-Wall", "-I", str(INCLUDES)]
    for item in defines or []:
        command.extend(["-D", item])
    command.extend(["-s", top, "-o", str(output), *map(str, sources)])
    run = subprocess.run(command, text=True, capture_output=True)
    return {"command": command, "exit": run.returncode, "stdout": run.stdout, "stderr": run.stderr}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    errors: list[str] = []
    target_text = TARGET.read_text(encoding="utf-8")
    if sha(TARGET) != EXPECTED_TARGET_SHA:
        errors.append("target_rtl_sha_mismatch")
    member = f"{PACKAGE}/tb_probe/buffer_ack_phase_observer.svh"
    with zipfile.ZipFile(args.zip) as archive:
        observer = archive.read(member).decode("utf-8")
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
    bind_map = mapping(observer)
    if not bind_map:
        errors.append("bind_mapping_missing")
    undeclared = sorted(name for name in bind_map.values() if not declared(target_text, name))
    if undeclared:
        errors.append("undeclared_actuals:" + ",".join(undeclared))
    proof = manifest.get("observer_public_surface_or_xmr_proof", {}).get("buffer_ack_phase_observer", {})
    if proof.get("target_file_sha256") != EXPECTED_TARGET_SHA:
        errors.append("manifest_target_sha_mismatch")
    macro_widths = {
        "mse_buf_queue_row_idx": "`SE_BUF_ROW_INPORT_IDX_WIDTH-1:0",
        "mse_buf_queue_row_tag": "`SE_BUF_INPORT_TAG_WIDTH-1:0",
        "mse_buf_queue_col_tag": "`SE_BUF_INPORT_TAG_WIDTH-1:0",
    }
    width_checks = {name: token in observer for name, token in macro_widths.items()}
    if not all(width_checks.values()):
        errors.append("observer_macro_width_binding_missing")

    with tempfile.TemporaryDirectory(prefix="n4v80_hdl_") as raw:
        root = Path(raw)
        obs = root / "buffer_ack_phase_observer.svh"
        obs.write_text(observer, encoding="utf-8")
        target_compile = compile_one(args.iverilog, root / "target.vvp", [FIFO, TARGET], "Buffer_AG_Idx_Queue")
        observer_compile = compile_one(
            args.iverilog,
            root / "observer.vvp",
            [obs],
            "codex_probe_buf_ack_phase_witness",
            ["CODEX_SOURCE_BOUND_FOCUS"],
        )
    if target_compile["exit"] != 0:
        errors.append("actual_target_focused_compile_failed")
    if observer_compile["exit"] != 0:
        errors.append("observer_module_focused_compile_failed")

    # Negatives are derived from the exact final bind consumer expression.
    actuals = list(bind_map.values())
    deleted = actuals[0] if actuals else ""
    typo = deleted + "_TYPO" if deleted else ""
    sibling = "mse_buf_queue_bp_pre_sibling"
    negatives = {
        "deleted_actual_fails": bool(deleted) and not declared(target_text.replace(deleted, "", 1), deleted),
        "typo_actual_fails": bool(typo) and not declared(target_text, typo),
        "wrong_sibling_fails": not declared(target_text, sibling),
    }
    if not all(negatives.values()):
        errors.append("scope_negative_did_not_fail_closed")

    report = {
        "schema": "node0004-v80-buffer-ack-phase-hdl-scope-v1",
        "pass": not errors,
        "errors": errors,
        "zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "target": {"path": str(TARGET), "sha256": sha(TARGET)},
        "bind_actuals": bind_map,
        "undeclared_actuals": undeclared,
        "width_checks": width_checks,
        "target_compile": target_compile,
        "observer_compile": observer_compile,
        "negatives": negatives,
        "tool_boundary": "Icarus does not parse SV bind; the exact target and observer module are compiled separately, while exact final bind actuals are scope-checked against the immutable target source with consumer-derived negatives.",
        "claim_boundary": "Focused syntax/elaboration and exact identifier/scope/width binding only; no full-design VCS, DUT execution, numeric, natural-terminal or formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
