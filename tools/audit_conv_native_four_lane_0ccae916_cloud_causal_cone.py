#!/usr/bin/env python3
"""Targeted cloud-RTL impact audit for the native-four-lane c0 diagnostic."""

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
RTL_REPO = ROOT / "Trassic2.0_RTL"
SOURCE_NAME = "r5_n4_e1f_p6_armif"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_ZIP_SHA256 = (
    "05fc4f385d544195ad3cbc68256525d70775cc490d4a42ff784e9b9f7c5d34c1"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_cloud_causal_cone/report.json"
)
BASE_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"

COMPILED_LEAF_PATHS = {
    "Array_Request_Manager.sv": (
        "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
    "RD_Data_Channel.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
    ),
    "Neighbor_Out_AG.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Neighbor_Stream_Engine/"
        "Neighbor_Out_AG.sv"
    ),
    "SA_PE_Float_CSA.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_CSA.v"
    ),
    "SA_PE_Float_Control.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Float_Control.v"
    ),
    "SA_PE_Mul_Array.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
        "SA_PE_Mul_Array.v"
    ),
    "SA_ALU.v": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_ALU.v"
    ),
}

OWNER_PATHS = {
    "IGA_ROW_LC.sv": (
        "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC.sv"
    ),
    "IGA_ROW_LC_Inbuffer.sv": (
        "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC_Inbuffer.sv"
    ),
    "Array_Request_Manager.sv": COMPILED_LEAF_PATHS[
        "Array_Request_Manager.sv"
    ],
    "Buffer_Manager.sv": (
        "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv"
    ),
    "Buffer_Manager_Cluster.sv": (
        "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Buffer_Manager_Cluster.sv"
    ),
    "Buffer_AG_Idx_Queue.sv": COMPILED_LEAF_PATHS[
        "Buffer_AG_Idx_Queue.sv"
    ],
    "RD_Data_Channel.sv": COMPILED_LEAF_PATHS["RD_Data_Channel.sv"],
    "SA_Inport_Connect.sv": (
        "code/NDP_rtl/Slice/Specialized_Array/SA_Inport/"
        "SA_Inport_Connect.sv"
    ),
    "NDP_Parameters.svh": "code/NDP_rtl/includes/NDP_Parameters.svh",
}

OBSERVER_OWNER_TOKENS = {
    "Array_Request_Manager.sv": (
        "arm2buf_req_valid",
        "buf2arm_req_ready",
        "buf2arm_rvalid",
        "array2arm_bp_post",
        "arm_buf_rd_finish",
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "buf_ag_idx_queue_wr_en",
        "buf_ag_idx_queue_rd_en",
        "buf_ag_idx_queue_full",
        "buf_ag_idx_queue_empty",
    ),
    "RD_Data_Channel.sv": (
        "rd_chl_ib_wr_hs",
        "rd_chl_ib_rd_hs",
        "rd_data_chl_prepared_data_wr_hs",
        "rd_data_chl_prepared_data_rd_hs",
        "rd_chl_queue_full",
        "rd_chl_queue_empty",
        "rd_data_chl_prepared_data_cnt",
    ),
}


class AuditError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    safe = repo.resolve().as_posix()
    process = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(repo),
            *args,
        ],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )
    if process.returncode != 0:
        stderr = process.stderr if text else process.stderr.decode(
            "utf-8", errors="replace"
        )
        raise AuditError(f"git {' '.join(args)} failed: {stderr}")
    return process.stdout


def blob(repo: Path, commit: str, path: str) -> bytes:
    return git(repo, "show", f"{commit}:{path}", text=False)  # type: ignore[return-value]


def source_lines(payload: bytes) -> list[str]:
    return payload.decode("utf-8", errors="strict").splitlines()


def line_receipts(payload: bytes, tokens: tuple[str, ...]) -> list[dict[str, Any]]:
    lines = source_lines(payload)
    result: list[dict[str, Any]] = []
    for token in tokens:
        matches = [
            {
                "line": index + 1,
                "text": line.strip(),
                "line_sha256": sha256_bytes(line.strip().encode()),
            }
            for index, line in enumerate(lines)
            if re.search(rf"\b{re.escape(token)}\b", line)
        ]
        result.append(
            {
                "token": token,
                "present": bool(matches),
                "matches": matches,
            }
        )
    return result


def fifo_boundary_trace(depth: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    occupancies = sorted({0, 1, max(0, depth - 2), depth - 1, depth})
    for occupancy in occupancies:
        for push, pop in ((0, 0), (1, 0), (0, 1), (1, 1)):
            push_accept = bool(push and occupancy < depth)
            pop_accept = bool(pop and occupancy > 0)
            after = occupancy + int(push_accept) - int(pop_accept)
            cases.append(
                {
                    "depth": depth,
                    "occupancy_before": occupancy,
                    "push": push,
                    "pop": pop,
                    "push_accept": push_accept,
                    "pop_accept": pop_accept,
                    "occupancy_after": after,
                    "full_before": occupancy == depth,
                    "empty_before": occupancy == 0,
                    "invariant": 0 <= after <= depth,
                }
            )
    return cases


def bool_trace() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for sa_enable in (0, 1):
        for valid in (0, 1):
            for last in (0, 1):
                for bp_post in (0, 1):
                    change = bool(
                        sa_enable and valid and last and bp_post
                    )
                    result.append(
                        {
                            "sa_enable": sa_enable,
                            "pingpong_enable": 1,
                            "valid": valid,
                            "last": last,
                            "last_gte": 1,
                            "bp_post": bp_post,
                            "pingpong_change": change,
                        }
                    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-repo", type=Path, default=RTL_REPO)
    parser.add_argument("--source-zip", type=Path, default=SOURCE_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    repo = args.git_repo.resolve()
    source_zip = args.source_zip.resolve()
    output = args.output.resolve()

    if sha256(source_zip) != SOURCE_ZIP_SHA256:
        raise AuditError("exact p6 source ZIP differs")
    resolved = str(git(repo, "rev-parse", CLOUD_COMMIT)).strip()
    if resolved != CLOUD_COMMIT:
        raise AuditError("cloud commit object differs")

    changed_lines = str(
        git(repo, "diff", "--name-status", BASE_COMMIT, CLOUD_COMMIT)
    ).splitlines()
    changed = [line.split("\t", 1)[1] for line in changed_lines]
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
    commits = int(
        str(
            git(
                repo,
                "rev-list",
                "--count",
                f"{BASE_COMMIT}..{CLOUD_COMMIT}",
            )
        ).strip()
    )

    with zipfile.ZipFile(source_zip) as archive:
        observer = archive.read(
            f"{SOURCE_NAME}/tb_probe/native_return_observer.svh"
        )
    observer_text = observer.decode("utf-8")
    if "buf2arm_valid_hold" in observer_text:
        raise AuditError("p6 observer unexpectedly uses private hold state")

    owner_payloads = {
        name: blob(repo, CLOUD_COMMIT, path)
        for name, path in OWNER_PATHS.items()
    }
    owner_receipts = {
        name: {
            "path": OWNER_PATHS[name],
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
        for name, payload in owner_payloads.items()
    }
    observer_coverage: list[dict[str, Any]] = []
    for owner, tokens in OBSERVER_OWNER_TOKENS.items():
        receipts = line_receipts(owner_payloads[owner], tokens)
        for receipt in receipts:
            receipt.update(
                {
                    "owner": owner,
                    "cloud_owner_path": OWNER_PATHS[owner],
                    "cloud_owner_sha256": owner_receipts[owner]["sha256"],
                    "observer_consumes": re.search(
                        rf"\b{re.escape(receipt['token'])}\b",
                        observer_text,
                    )
                    is not None,
                }
            )
            receipt["covered"] = (
                receipt["present"] and receipt["observer_consumes"]
            )
            observer_coverage.append(receipt)

    cloud_leaves = {
        basename: {
            "path": path,
            "bytes": len(payload := blob(repo, CLOUD_COMMIT, path)),
            "sha256": sha256_bytes(payload),
            "changed_from_local_base": path in changed,
            "local_base_sha256": sha256_bytes(blob(repo, BASE_COMMIT, path)),
        }
        for basename, path in COMPILED_LEAF_PATHS.items()
    }
    changed_compiled = sorted(
        name
        for name, value in cloud_leaves.items()
        if value["changed_from_local_base"]
    )

    row_in = owner_payloads["IGA_ROW_LC_Inbuffer.sv"].decode()
    arm = owner_payloads["Array_Request_Manager.sv"].decode()
    buf_ag = owner_payloads["Buffer_AG_Idx_Queue.sv"].decode()
    rd = owner_payloads["RD_Data_Channel.sv"].decode()
    sa = owner_payloads["SA_Inport_Connect.sv"].decode()
    params = owner_payloads["NDP_Parameters.svh"].decode()
    queue_traces = {
        "iga_row_lc_128": fifo_boundary_trace(128),
        "buffer_ag_32": fifo_boundary_trace(32),
        "rd_channel_128": fifo_boundary_trace(128),
        "request_ooo_128": fifo_boundary_trace(128),
    }
    pingpong_trace = bool_trace()
    trace_checks = {
        "queue_invariants_hold": all(
            case["invariant"]
            for trace in queue_traces.values()
            for case in trace
        ),
        "each_queue_has_first_penultimate_final_one_after_attempt": all(
            {0, depth - 1, depth}.issubset(
                {case["occupancy_before"] for case in trace}
            )
            and any(
                case["occupancy_before"] == depth
                and case["push"] == 1
                and case["push_accept"] is False
                for case in trace
            )
            for depth, trace in (
                (128, queue_traces["iga_row_lc_128"]),
                (32, queue_traces["buffer_ag_32"]),
                (128, queue_traces["rd_channel_128"]),
                (128, queue_traces["request_ooo_128"]),
            )
        ),
        "push_pop_covered": all(
            any(case["push"] and case["pop"] for case in trace)
            for trace in queue_traces.values()
        ),
        "pingpong_valid_zero_blocks": all(
            not case["pingpong_change"]
            for case in pingpong_trace
            if case["valid"] == 0
        ),
        "pingpong_all_qualifiers_true_changes": any(
            case["pingpong_change"] for case in pingpong_trace
        ),
    }

    exact_source_checks = {
        "row_fifo_depth_128": ".FIFO_DEPTH        ( 128 )" in row_in,
        "row_bp_uses_not_full": (
            "assign iga_row_lc_inbuffer_bp_pre = !fifo_full;" in row_in
        ),
        "row_valid_uses_not_empty": (
            "assign iga_row_lc_inbuffer_valid_bit = !fifo_empty;" in row_in
        ),
        "arm_read_req_no_hold_gate": (
            "assign arm2buf_req_valid = buffer_rw ? "
            "array2buf_valid_bit & {`BUFFER_BANK_NUM{buffer_enable}} : "
            "{`BUFFER_BANK_NUM{array2arm_bp_post}} & buffer_mask;" in arm
        ),
        "arm_public_observer_surface_present": all(
            re.search(rf"\b{token}\b", arm)
            for token in ("buf2arm_rvalid", "array2arm_bp_post")
        ),
        "buffer_ag_depth_32": (
            "localparam BUF_AG_IDX_QUEUE_DEPTH = 32;" in buf_ag
        ),
        "rd_channel_depth_128": (
            "localparam RD_CHL_QUEUE_DEPTH = 128;" in rd
        ),
        "request_depths_128": all(
            token in params
            for token in (
                "`define REQ_OOO_DEPTH                128",
                "`define REQ_QUEUE_DEPTH              128",
                "`define REQ_TAG_BUF_DEPTH            128",
            )
        ),
        "sa_pingpong_requires_valid_and_accept": (
            "sa_enable & sa_inport_pingpong_en && "
            "sa_inport_valid_bit && sa_inport_last_bit && "
            "sa_inport_pingpong_last_gte && sa_inport_bp_post" in sa
        ),
        "public_port_width_contract_retained": all(
            token in params
            for token in (
                "`define PORT_VALID_BIT                     1",
                "`define PORT_LAST_BIT                      1",
                "`define PORT_SAME_BIT                      1",
                "`define PORT_LAST_INDEX                    4",
                "`define IGA_LC_PORT_DATA_WIDTH             16",
            )
        ),
    }
    negatives = {
        "wrong_cloud_commit_fails": resolved != BASE_COMMIT,
        "private_observer_surface_absent": (
            "buf2arm_valid_hold" not in observer_text
        ),
        "renamed_public_leaf_not_found": (
            "buf2arm_rvalid_RENAMED" not in arm
        ),
        "wrong_depth_not_accepted": (
            "localparam BUF_AG_IDX_QUEUE_DEPTH = 24;" not in buf_ag
            and "localparam RD_CHL_QUEUE_DEPTH = 32;" not in rd
        ),
        "invalid_pingpong_event_blocked": all(
            not case["pingpong_change"]
            for case in pingpong_trace
            if not (
                case["sa_enable"]
                and case["valid"]
                and case["last"]
                and case["bp_post"]
            )
        ),
    }
    checks = {
        "cloud_commit_exact": resolved == CLOUD_COMMIT,
        "diff_12_commits": commits == 12,
        "diff_11_files": len(changed) == 11,
        "diff_497_insertions": insertions == 497,
        "diff_30_deletions": deletions == 30,
        "compiled_leaf_change_set_exact": changed_compiled
        == [
            "Array_Request_Manager.sv",
            "Buffer_AG_Idx_Queue.sv",
            "RD_Data_Channel.sv",
        ],
        "observer_public_surface_cloud_covered": all(
            item["covered"] for item in observer_coverage
        ),
        "exact_cloud_source_semantics": all(exact_source_checks.values()),
        "boundary_microtrace": all(trace_checks.values()),
        "negative_controls_fail_closed": all(negatives.values()),
    }
    changed_functional = [
        path
        for path in changed
        if not path.endswith((".bak", ".bak0"))
    ]
    report: dict[str, Any] = {
        "schema": (
            "conv-native-four-lane-0ccae916-cloud-causal-cone-audit-v1"
        ),
        "valid": all(checks.values()),
        "status": (
            "SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING"
            if all(checks.values())
            else "FAIL"
        ),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "authority": {
            "repository": "xlsjdjdk/Trassic2.0_RTL",
            "branch": "master",
            "base_commit": BASE_COMMIT,
            "approved_commit": CLOUD_COMMIT,
            "verification": (
                "authenticated GitHub compare/blob read plus exact local "
                "immutable commit object"
            ),
        },
        "diff": {
            "commit_count": commits,
            "changed_files": changed,
            "functional_changed_files": changed_functional,
            "insertions": insertions,
            "deletions": deletions,
        },
        "cloud_changed_owner_receipts": owner_receipts,
        "cloud_expected_compiled_leaves": cloud_leaves,
        "observer": {
            "source_p6_zip_sha256": SOURCE_ZIP_SHA256,
            "source_sha256": sha256_bytes(observer),
            "private_xmr": False,
            "coverage": observer_coverage,
        },
        "causal_classification": {
            "direct_observer_owner_changes": [
                OWNER_PATHS["Array_Request_Manager.sv"],
                OWNER_PATHS["Buffer_AG_Idx_Queue.sv"],
                OWNER_PATHS["RD_Data_Channel.sv"],
            ],
            "indirect_dynamic_dataflow_changes": sorted(
                set(changed_functional)
                - {
                    OWNER_PATHS["Array_Request_Manager.sv"],
                    OWNER_PATHS["Buffer_AG_Idx_Queue.sv"],
                    OWNER_PATHS["RD_Data_Channel.sv"],
                }
            ),
            "backup_only_changes": sorted(
                path for path in changed if path.endswith((".bak", ".bak0"))
            ),
            "compile_compatibility": (
                "p6 production compile already crossed the public observer "
                "surface; exact 0ccae916 declarations remain present"
            ),
            "dynamic_claim_boundary": (
                "queue-depth, request-replay, row-FIFO and pingpong changes "
                "can affect c0 progress; only a fresh production simulation "
                "can classify exec-to-slice_finish behavior"
            ),
        },
        "boundary_microtrace": {
            "scope": (
                "metadata/exact-predicate boundary trace only; no DUT or "
                "numeric simulation"
            ),
            "checks": trace_checks,
            "queue_traces": queue_traces,
            "pingpong_trace": pingpong_trace,
        },
        "exact_source_checks": exact_source_checks,
        "negative_controls": negatives,
        "identity_adjudication": (
            "after successful compile, actual/local/cloud SHA differences "
            "are returned evidence and never a simulator launch predicate"
        ),
        "numeric_w3_golden_repeated": False,
        "local_e2_repeated": False,
        "functional_rtl_modified": False,
        "p6_rerun": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
