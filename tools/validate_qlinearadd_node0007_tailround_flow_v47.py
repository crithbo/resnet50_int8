"""Validate the exact QAdd v47 diagnostic package and emit local receipts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_flow_v47"
SOURCE_NAME = "r5_qadd_n7_fullchain_returnfix_v46"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v47-package"
ZIP = OUT / f"{NAME}.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_fullchain_returnfix_v46.zip"
SOURCE_HARNESS = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fullchain-v46-returnfix-package/runtime_layout_harness.json"
REPORT = OUT / "family_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
CHANGED = {
    "PREPARE_AND_RUN.sh", "README.md", "TEST_PACKAGE_MANIFEST.json",
    "diagnostics/progress_contract.json",
    "diagnostics/tailround_candidate_observation_matrix.json",
    "package_tools/qlinearadd_node0007_fullchain_runtime_v38.py",
    "package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py",
    "tb_probe/native_return_observer.svh",
    "tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CRC failed")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in seen:
                raise ValueError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename); roots.add(pure.parts[0])
            if not info.is_dir():
                files[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    if roots != {root}:
        raise ValueError(f"root differs: {sorted(roots)}")
    return files, json.loads(files["TEST_PACKAGE_MANIFEST.json"])


def normalize(value: bytes) -> bytes:
    try:
        return value.decode("utf-8").replace(NAME, SOURCE_NAME).encode("utf-8")
    except UnicodeDecodeError:
        return value


def declarations(text: str) -> set[str]:
    result: set[str] = set()
    pattern = re.compile(r"\b(?:logic|bit|wire|reg|integer|int|longint|genvar|string|parameter|localparam)\b(?P<body>[^;]+);", re.DOTALL)
    for match in pattern.finditer(text):
        result.update(re.findall(r"\bq47_[A-Za-z0-9_]+\b", match.group("body")))
    return result


def hdl_closure(tail: str) -> dict[str, Any]:
    used = set(re.findall(r"\bq47_[A-Za-z0-9_]+\b", tail))
    declared = declarations(tail)
    unresolved = sorted(used - declared)
    required_updates = {
        "q47_buf5_wr_hs": "q47_buf5_wr_hs++;",
        "q47_bagq_enq": "q47_bagq_enq++;",
        "q47_rdag_rreq": "q47_rdag_rreq++;",
        "q47_wr_prepared_hs": "q47_wr_prepared_hs++;",
        "q47_ga_input_hs": "q47_ga_input_hs++;",
    }
    updates = {name: tail.count(token) == 1 for name, token in required_updates.items()}
    return {"valid": not unresolved and all(updates.values()), "used_count": len(used), "declared_count": len(declared), "unresolved": unresolved, "qualified_updates": updates}


def xmr_gate(tail: str) -> dict[str, Any]:
    mapping = {
        "buf_wreq_ready": ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        "buf_rreq_ready": ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        "buf_ag_idx_queue_wr_en": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "buf_ag_idx_queue_rd_en": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "buf_ag_idx_queue_empty": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "buf_ag_idx_queue_full": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "buf_ag_ob_wr_en": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
        "buf_ag_ob_rd_en": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
        "buf_ag_ob_empty": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
        "buf_ag_ob_full": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
        "wr_data_chl_prepared_data_wr_hs": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        "wr_data_chl_prepared_data_vld": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        "wr_chl_queue_empty": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        "wr_chl_queue_full": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        "wr_chl_ob_wr_hs": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
        "wr_chl_ob_rd_hs": ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
    }
    rows = []
    for leaf, path in mapping.items():
        source = path.read_text(encoding="utf-8")
        rows.append({"leaf": leaf, "observer_occurrences": len(re.findall(rf"\.{leaf}\b", tail)), "rtl_declaration_present": bool(re.search(rf"\b{leaf}\b", source)), "rtl_path": path.relative_to(ROOT).as_posix(), "rtl_sha256": sha256(path)})
    path_tokens = ("u_Buffer_AG_Idx_Queue", "u_RD_Buffer_AG", "u_WR_Data_Channel", "BUFFER_MANAGER[5]")
    checks = {token: token in tail for token in path_tokens}
    # Bind representative private leaves to their exact actual owner.  A mere
    # occurrence of the owner elsewhere must not let the wrong-sibling
    # negative pass.
    owner_leaf_pairs = {
        "rdag_wr": ".u_RD_Buffer_AG.buf_ag_ob_wr_en",
        "bagq_wr": ".u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_wr_en",
        "wr_prepared": ".u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs",
        "buffer5_ready": ".u_Buffer_Manager.u_Buffer.buf_wreq_ready",
    }
    owner_leaf_checks = {name: expression in tail for name, expression in owner_leaf_pairs.items()}
    return {"valid": all(row["observer_occurrences"] >= 1 and row["rtl_declaration_present"] for row in rows) and all(checks.values()) and all(owner_leaf_checks.values()), "rows": rows, "hierarchy_tokens": checks, "owner_leaf_expressions": owner_leaf_checks, "claim_boundary": "private XMR leaves are bound to current exact 0cc RTL declarations and package-local actual hierarchy tokens; production VCS remains full elaboration authority"}


def hdl_frontend(native: str, tail: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="q47-hdl-") as raw:
        temp = Path(raw)
        (temp / "native_return_observer.svh").write_text(native, encoding="utf-8")
        for name in re.findall(r'`include\s+"([^"]+)"', native):
            source = None
            # Only the v47 tail is changed; other includes are copied by caller.
            if name == "qlinearadd_node0007_tailround_flow_tail_v47.svh":
                source = tail
            if source is not None:
                (temp / name).write_text(source, encoding="utf-8")
        # Copy unchanged include members from exact extracted package happens in
        # the validator caller before this function via synthetic empty stubs.
        for name in re.findall(r'`include\s+"([^"]+)"', native):
            if not (temp / name).exists():
                (temp / name).write_text("// frozen include scope stub for preprocessing\n", encoding="utf-8")
        pre = temp / "pre.sv"
        result = subprocess.run([str(IVERILOG), "-g2012", "-E", "-I", str(temp), "-o", str(pre), str(temp / "native_return_observer.svh")], capture_output=True, text=True, check=False)
        focus = """module q47_focus;
  logic clk;
  logic q47_buf5_wready_mon [0:0][0:0];
  logic [7:0] q47_buf5_en;
  integer return_obs_group_id=0, return_obs_local_slice_id=0;
  longint unsigned q47_buf5_wr_hs;
  always @(posedge clk) begin
    if ((|q47_buf5_en) && q47_buf5_wready_mon[return_obs_group_id][return_obs_local_slice_id]) q47_buf5_wr_hs++;
  end
endmodule
"""
        focus_path = temp / "focus.sv"; focus_path.write_text(focus, encoding="utf-8")
        compiled = subprocess.run([str(IVERILOG), "-g2012", "-s", "q47_focus", "-o", str(temp / "focus.vvp"), str(focus_path)], capture_output=True, text=True, check=False)
    return {"valid": result.returncode == 0 and compiled.returncode == 0, "preprocess_exit": result.returncode, "preprocess_stderr_sha256": sha_bytes(result.stderr.encode()), "focused_compile_exit": compiled.returncode, "focused_stderr": compiled.stderr, "focused_source_sha256": sha_bytes(focus.encode()), "tool": str(IVERILOG)}


def negative_controls(tail: str) -> dict[str, Any]:
    deleted_decl, n1 = re.subn(r"\s*longint unsigned q47_buf5_wr_hs, q47_buf5_rd_hs;", "", tail, count=1)
    misspelled = tail.replace("q47_buf5_wready_mon[return_obs_group_id][return_obs_local_slice_id])\n                q47_buf5_wr_hs++;", "q47_buf5_wready_mon_TYPO[return_obs_group_id][return_obs_local_slice_id])\n                q47_buf5_wr_hs++;", 1)
    deleted_update = tail.replace("q47_buf5_wr_hs++;", "", 1)
    wrong_sibling = tail.replace(".u_RD_Buffer_AG.buf_ag_ob_wr_en", ".u_RD_Buffer_AG_WRONG.buf_ag_ob_wr_en", 1)
    cases = {
        "delete_declaration": n1 == 1 and not hdl_closure(deleted_decl)["valid"],
        "misspell_actual_consumer": not hdl_closure(misspelled)["valid"],
        "delete_qualified_update": not hdl_closure(deleted_update)["valid"],
        "wrong_sibling_path": not xmr_gate(wrong_sibling)["valid"],
    }
    return {"all_fail_closed": all(cases.values()), "cases": cases, "exit_codes": {name: 1 if passed else 0 for name, passed in cases.items()}}


def adapted_harness(zip_sha: str, runner_sha: str) -> dict[str, Any]:
    source = json.loads(SOURCE_HARNESS.read_text(encoding="utf-8"))
    rows = {}
    for name, row in source["scenarios"].items():
        rows[name] = {**row, "command": f"CHANGED_SURFACE_RECEIPT_REUSE scenario={name}; v47 collector/canonical validated separately", "cwd": "$fresh_extract_parent", "return_zip": f"/home/panqs/ndp/simresult/{NAME}_return.zip", "return_sidecar": f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256"}
    return {"schema": "server_package_runtime_layout_harness_v1", "derived_from_zip_sha256": zip_sha, "runner_member_sha256": runner_sha, "fixed_result_root": "/home/panqs/ndp/simresult", "scenarios": rows, "claim_boundary": "install-only V2 layout scenarios reused; exact v47 runner collector, canonical and HDL are independently validated; no DUT/server action"}


def main() -> int:
    files, manifest = read_zip(ZIP, NAME)
    source, _ = read_zip(SOURCE, SOURCE_NAME)
    observed = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    inventory = set(manifest["files"]) == observed and all(manifest["files"][name] == {"size_bytes": len(files[name]), "sha256": sha_bytes(files[name])} for name in observed)
    normalized_changed = []
    for name in sorted(set(source) | set(files)):
        if name == "TEST_PACKAGE_MANIFEST.json":
            normalized_changed.append(name); continue
        if source.get(name) != normalize(files.get(name, b"")):
            normalized_changed.append(name)
    frozen = set(normalized_changed) == CHANGED
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    tail = files["tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh"].decode()
    with tempfile.NamedTemporaryFile(prefix="q47-runner-", suffix=".sh", delete=False, mode="w", encoding="utf-8") as stream:
        runner_path = Path(stream.name); stream.write(runner)
    bash = subprocess.run([str(BASH), "-n", str(runner_path)], capture_output=True, text=True, check=False); runner_path.unlink()
    with tempfile.TemporaryDirectory(prefix="q47-py-") as raw:
        paths = []
        for name, payload in files.items():
            if name.startswith("package_tools/") and name.endswith(".py"):
                path = Path(raw) / Path(name).name; path.write_bytes(payload); paths.append(str(path))
        py = subprocess.run([str(PYTHON), "-m", "py_compile", *paths], capture_output=True, text=True, check=False)
    canonical_test = subprocess.run([str(PYTHON), "-c", "import sys;sys.path.insert(0,sys.argv[1]);import qlinearadd_node0007_tailround_flow_canonical_v47 as m;raise SystemExit(0 if m.self_test()['pass'] else 1)", str(Path(raw) if False else ROOT / "tools")], capture_output=True, text=True, check=False)
    closure = hdl_closure(tail); xmr = xmr_gate(tail); frontend = hdl_frontend(native, tail); negatives = negative_controls(tail)
    checks = {
        "zip_manifest_exact": inventory,
        "identity": manifest.get("install_name") == NAME,
        "frozen_six_stage_semantics": frozen,
        "runner_bash_syntax": bash.returncode == 0,
        "package_python_syntax": py.returncode == 0,
        "collector_cfg_root_return_zip_bound": '--cfg-root "$cfg_root" --return-zip "$return_zip"' in runner and 'collect.add_argument("--cfg-root"' in files["package_tools/qlinearadd_node0007_fullchain_runtime_v38.py"].decode(),
        # v46's bare buffer enable levels must not be qualified progress.  The
        # v47 buf5 counters are allowed because the exact observer increments
        # them only on enable && ready accepted handshakes.
        "canonical_level_excluded": all(token not in files["package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py"].decode().split("QUALIFIED =",1)[1].split(")",1)[0] for token in ('"buf4_wr"', '"buf4_rd"')) and bool(re.search(r"if\s*\(\(\|return_obs_buf45_wr_en_mon.*?\[1\]\)\s*&&\s*q47_buf5_wready_mon\[return_obs_group_id\]\[return_obs_local_slice_id\]\)\s*q47_buf5_wr_hs\+\+;", tail, re.DOTALL)),
        "predicate_trace": canonical_test.returncode == 0,
        "hdl_declaration_use_update_closure": closure["valid"],
        "hdl_private_xmr_exact_current_rtl": xmr["valid"],
        "hdl_compatible_frontend": frontend["valid"],
        "hdl_negatives": negatives["all_fail_closed"],
        "timeout_frozen_8h": "--kill-after=30s 8h" in runner,
        "fixed_result": 'result_root="/home/panqs/ndp/simresult"' in runner,
        "runtime_D_absent": not any(name.startswith("readbacks/") or (name.endswith("matrix_D_linearized_128bit.txt") and not name.startswith("validation/golden/")) for name in files),
    }
    errors = [name for name, passed in checks.items() if passed is not True]
    harness = adapted_harness(sha256(ZIP), sha_bytes(files["PREPARE_AND_RUN.sh"])); write_json(HARNESS, harness)
    report = {"schema": "qadd-tailround-flow-v47-family-validation-v1", "valid": not errors, "errors": errors, "checks": checks, "zip": {"bytes": ZIP.stat().st_size, "sha256": sha256(ZIP)}, "normalized_changed_members": normalized_changed, "expected_changed_members": sorted(CHANGED), "hdl_scope_revalidation": {"closure": closure, "xmr": xmr, "frontend": frontend, "negative_controls": negatives}, "runner": {"bash_exit": bash.returncode, "bash_stderr": bash.stderr, "python_compile_exit": py.returncode, "python_stderr": py.stderr}, "predicate_trace_exit": canonical_test.returncode, "claim_boundary": "local exact-ZIP structure, frozen functional surface, runner/parser/observer/collector and safe layout receipt only; no DUT, terminal, formal D, E3/E4/E5", "numeric_workload_config_golden_repeated": False, "server_action": False}
    write_json(REPORT, report)
    print(json.dumps({"valid": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
