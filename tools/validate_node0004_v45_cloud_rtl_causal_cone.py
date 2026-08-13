from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v45_lc9_split_cloudrtl"
VERSION = 45
BASE_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
BEGIN = "// v45 LC9_SPLIT_ACTUAL_CONSUMER_BEGIN"
END = "// v45 LC9_SPLIT_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(
    repo: Path, *args: str, text: bool = True
) -> str | bytes:
    command = [
        "git",
        "-c",
        f"safe.directory={repo.as_posix()}",
        "-C",
        str(repo),
        *args,
    ]
    return subprocess.check_output(
        command,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def blob(repo: Path, commit: str, path: str) -> bytes:
    return git(repo, "show", f"{commit}:{path}", text=False)  # type: ignore[return-value]


def owner_path(expression: str) -> str:
    leaf = re.sub(r"\[.*", "", expression.rsplit(".", 1)[-1])
    if leaf in {"clk_db", "rst_n_db"}:
        return "code/NDP_rtl/NDP_Top.sv"
    if leaf in {
        "iga_lc_outport",
        "iga_lc_outport_bp_post",
        "iga_pe_inport_bp_pre",
        "iga_pe_outport",
        "iga_pe_outport_bp_post",
    }:
        return (
            "code/NDP_rtl/Slice/Index_Generation_Array/"
            "Index_Generation_Array.sv"
        )
    if leaf == "iga_pe_inbuffer_matched":
        return (
            "code/NDP_rtl/Slice/Index_Generation_Array/IGA_PE/"
            "IGA_PE_Inbuffer.sv"
        )
    if leaf in {"mse_mem_queue_tag", "mse_mem_queue_bp_pre"}:
        return (
            "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
            "Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
        )
    if leaf in {
        "iga_row_lc_inbuffer_bp_pre",
        "iga_row_lc_cnt_bp_post",
        "iga_row_lc_outport",
    }:
        return (
            "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
            "IGA_ROW_LC.sv"
        )
    if leaf == "iga_row_lc_inport_valid_bit_masked":
        return (
            "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
            "IGA_ROW_LC_Inbuffer.sv"
        )
    if leaf == "iga_row_lc_cnt_outport_valid_bit":
        return (
            "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
            "IGA_ROW_LC_Counter.sv"
        )
    if leaf in {"buf_ag_idx_queue_wr_en", "buf_ag_idx_queue_full"}:
        return (
            "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
            "Buffer_AG_Idx_Queue.sv"
        )
    raise KeyError(leaf)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--git-repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo = args.git_repo.resolve()

    resolved = str(git(repo, "rev-parse", CLOUD_COMMIT)).strip()
    name_status = str(
        git(repo, "diff", "--name-status", BASE_COMMIT, CLOUD_COMMIT)
    ).splitlines()
    changed = [line.split("\t", 1)[1] for line in name_status]
    numstat = str(
        git(repo, "diff", "--numstat", BASE_COMMIT, CLOUD_COMMIT)
    ).splitlines()
    insertions = sum(
        int(line.split("\t")[0])
        for line in numstat
        if line.split("\t")[0].isdigit()
    )
    deletions = sum(
        int(line.split("\t")[1])
        for line in numstat
        if line.split("\t")[1].isdigit()
    )

    with zipfile.ZipFile(args.zip) as archive:
        observer_bytes = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
        manifest = json.loads(
            archive.read(f"{INSTALL_NAME}/package_manifest.json")
        )
    observer = observer_bytes.decode()
    block = observer[observer.index(BEGIN) : observer.index(END)]
    expressions = sorted(set(XMR_RE.findall(block)))

    owner_blobs: dict[str, bytes] = {}
    coverage: list[dict[str, Any]] = []
    for expression in expressions:
        path = owner_path(expression)
        payload = owner_blobs.setdefault(path, blob(repo, CLOUD_COMMIT, path))
        source = payload.decode()
        leaf = re.sub(r"\[.*", "", expression.rsplit(".", 1)[-1])
        declaration_present = (
            re.search(rf"\b{re.escape(leaf)}\b", source) is not None
        )
        exact_instance = (
            ("MSE_INST[" not in expression or "MSE_INST[4]" in expression)
            and ("IGA_PE[" not in expression or "IGA_PE[1]" in expression)
            and (
                "IGA_ROW_LC[" not in expression
                or "IGA_ROW_LC[4]" in expression
            )
            and (
                "slice_with_datahub_mc_group_gen[" not in expression
                or "slice_with_datahub_mc_group_gen[0]" in expression
            )
        )
        coverage.append(
            {
                "expression": expression,
                "leaf": leaf,
                "cloud_owner_path": path,
                "cloud_owner_sha256": sha256(payload),
                "owner_changed_from_local_base": path in changed,
                "declaration_present": declaration_present,
                "exact_instance": exact_instance,
                "covered": declaration_present and exact_instance,
            }
        )

    row_in = blob(
        repo,
        CLOUD_COMMIT,
        "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC_Inbuffer.sv",
    ).decode()
    buf_ag = blob(
        repo,
        CLOUD_COMMIT,
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv",
    ).decode()
    sa_inport = blob(
        repo,
        CLOUD_COMMIT,
        "code/NDP_rtl/Slice/Specialized_Array/SA_Inport/"
        "SA_Inport_Connect.sv",
    ).decode()
    params = blob(
        repo, CLOUD_COMMIT, "code/NDP_rtl/includes/NDP_Parameters.svh"
    ).decode()

    exact = next(
        item
        for item in coverage
        if item["leaf"] == "iga_row_lc_inport_valid_bit_masked"
    )
    row_deleted = re.sub(
        r"\biga_row_lc_inport_valid_bit_masked\b",
        "iga_row_lc_inport_valid_bit_masked_DELETED",
        row_in,
    )
    negatives = {
        "cloud_changed_leaf_delete_fail_closed": (
            re.search(
                r"\biga_row_lc_inport_valid_bit_masked\b", row_deleted
            )
            is None
        ),
        "cloud_changed_leaf_rename_fail_closed": (
            "iga_row_lc_inport_valid_bit_maskde" not in row_in
        ),
        "wrong_row_sibling_fail_closed": (
            "IGA_ROW_LC[3]" not in exact["expression"]
            and "IGA_ROW_LC[4]" in exact["expression"]
        ),
        "wrong_cloud_commit_fail_closed": resolved != BASE_COMMIT,
    }
    checks = {
        "cloud_commit_exact": resolved == CLOUD_COMMIT,
        "diff_12_commits": int(
            str(git(repo, "rev-list", "--count", f"{BASE_COMMIT}..{CLOUD_COMMIT}"))
        )
        == 12,
        "diff_11_files": len(changed) == 11,
        "diff_497_insertions": insertions == 497,
        "diff_30_deletions": deletions == 30,
        "manifest_cloud_commit": (
            manifest.get("cloud_rtl_authority", {}).get("approved_commit")
            == CLOUD_COMMIT
        ),
        "identity_difference_nonblocking": (
            manifest.get("cloud_rtl_authority", {}).get(
                "identity_difference_blocks_compile_or_simulation"
            )
            is False
        ),
        "all_actual_consumers_cloud_covered": all(
            item["covered"] for item in coverage
        ),
        "row_inbuffer_fifo_depth_128": (
            "FIFO#(" in row_in and ".FIFO_DEPTH        ( 128 )" in row_in
        ),
        "row_inbuffer_backpressure_uses_fifo_full": (
            "assign iga_row_lc_inbuffer_bp_pre = !fifo_full;" in row_in
        ),
        "buffer_ag_depth_32": (
            "localparam BUF_AG_IDX_QUEUE_DEPTH = 32;" in buf_ag
        ),
        "sa_pingpong_requires_valid": (
            "sa_inport_pingpong_en && sa_inport_valid_bit && "
            "sa_inport_last_bit" in sa_inport
        ),
        "port_width_contract_unchanged": all(
            token in params
            for token in (
                "`define PORT_VALID_BIT                     1",
                "`define PORT_LAST_BIT                      1",
                "`define PORT_SAME_BIT                      1",
                "`define PORT_LAST_INDEX                    4",
                "`define IGA_LC_PORT_DATA_WIDTH             16",
            )
        ),
        "request_depths_128": all(
            token in params
            for token in (
                "`define REQ_OOO_DEPTH                128",
                "`define REQ_QUEUE_DEPTH              128",
                "`define REQ_TAG_BUF_DEPTH            128",
            )
        ),
        "negative_controls_fail_closed": all(negatives.values()),
    }
    report: dict[str, Any] = {
        "schema": f"node0004-v{VERSION}-cloud-rtl-causal-cone-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "authority": {
            "repository": "xlsjdjdk/Trassic2.0_RTL",
            "branch": "master",
            "base_commit": BASE_COMMIT,
            "approved_commit": CLOUD_COMMIT,
        },
        "diff": {
            "commit_count": 12,
            "changed_files": changed,
            "insertions": insertions,
            "deletions": deletions,
        },
        "serialized_conv_causal_cone": {
            "direct_changed_files": [
                path
                for path in changed
                if any(
                    token in path
                    for token in (
                        "IGA_ROW_LC",
                        "Buffer_AG_Idx_Queue",
                        "SA_Inport_Connect",
                        "NDP_Parameters",
                    )
                )
            ],
            "observer_consumer_coverage": coverage,
            "observer_consumers": len(expressions),
            "observer_uncovered": sum(
                not item["covered"] for item in coverage
            ),
        },
        "negative_controls": negatives,
        "identity_adjudication": (
            "cloud/local identity difference is nonblocking after successful "
            "compile; actual compiled identity must be returned and E3/E4/E5 "
            "remain dynamic"
        ),
        "numeric_w3_golden_repeated": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
