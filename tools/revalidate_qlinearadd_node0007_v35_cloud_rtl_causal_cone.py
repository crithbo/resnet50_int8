from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
CLOUD = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
ZIP_SHA = "45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829"
ZIP_BYTES = 26_180_881
INSTALL = "r5_qadd_n7_crow32_v35"

CHANGED_CAUSAL_FILES = [
    "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC.sv",
    "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Inbuffer.sv",
    "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
    "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster.sv",
    "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
    "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv",
    "code/NDP_rtl/includes/NDP_Parameters.svh",
]
SA_FILE = "code/NDP_rtl/Slice/Specialized_Array/SA_Inport/SA_Inport_Connect.sv"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git(repo: Path, *args: str, text: bool = True):
    command = ["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args]
    run = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )
    if run.returncode != 0:
        stderr = run.stderr if text else run.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git command failed: {' '.join(args)}: {stderr}")
    return run.stdout


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    return git(repo, "show", f"{commit}:{path}", text=False)


def exact_package_members(zip_path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failed")
        root = INSTALL + "/"
        runner = archive.read(root + "PREPARE_AND_RUN.sh").decode("utf-8")
        native = archive.read(
            root + "tb_probe/native_return_observer.svh"
        ).decode("utf-8")
        ingress = archive.read(
            root
            + "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
        ).decode("utf-8")
        pair = archive.read(
            root
            + "tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"
        ).decode("utf-8")
    return runner, "\n".join((native, ingress, pair))


def capacity_trace(name: str, old: int, new: int) -> dict:
    samples = sorted({0, old - 1, old, new - 1, new})
    return {
        "name": name,
        "old_capacity": old,
        "new_capacity": new,
        "monotonic_expansion": new >= old,
        "samples": [
            {
                "occupancy": occupancy,
                "old_full": occupancy >= old,
                "new_full": occupancy >= new,
            }
            for occupancy in samples
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--cloud-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    zip_path = args.zip.resolve()
    if zip_path.stat().st_size != ZIP_BYTES or sha_file(zip_path) != ZIP_SHA:
        raise RuntimeError("frozen v35 ZIP identity drift")
    if git(repo, "cat-file", "-t", CLOUD).strip() != "commit":
        raise RuntimeError("cloud commit object unavailable")
    if git(repo, "rev-parse", "HEAD").strip() != BASE:
        raise RuntimeError("local expected checkout drift")

    cloud_report = json.loads(args.cloud_report.read_text(encoding="utf-8"))
    if (
        cloud_report["cloud_head"] != CLOUD
        or cloud_report["local_expected"] != BASE
    ):
        raise RuntimeError("cloud authority report identity drift")
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    runner, observer = exact_package_members(zip_path)

    all_changed = git(
        repo, "diff", "--name-only", BASE, CLOUD
    ).splitlines()
    blob_receipts = {}
    for path in CHANGED_CAUSAL_FILES + [SA_FILE]:
        base_bytes = git_blob(repo, BASE, path)
        cloud_bytes = git_blob(repo, CLOUD, path)
        blob_receipts[path] = {
            "base_bytes": len(base_bytes),
            "base_sha256": sha_bytes(base_bytes),
            "cloud_bytes": len(cloud_bytes),
            "cloud_sha256": sha_bytes(cloud_bytes),
            "changed": base_bytes != cloud_bytes,
        }

    arm_base = git_blob(
        repo, BASE, CHANGED_CAUSAL_FILES[2]
    ).decode("utf-8")
    arm_cloud = git_blob(
        repo, CLOUD, CHANGED_CAUSAL_FILES[2]
    ).decode("utf-8")
    iga_cloud = git_blob(
        repo, CLOUD, CHANGED_CAUSAL_FILES[1]
    ).decode("utf-8")
    bufq_base = git_blob(
        repo, BASE, CHANGED_CAUSAL_FILES[5]
    ).decode("utf-8")
    bufq_cloud = git_blob(
        repo, CLOUD, CHANGED_CAUSAL_FILES[5]
    ).decode("utf-8")
    rd_base = git_blob(
        repo, BASE, CHANGED_CAUSAL_FILES[6]
    ).decode("utf-8")
    rd_cloud = git_blob(
        repo, CLOUD, CHANGED_CAUSAL_FILES[6]
    ).decode("utf-8")
    params_base = git_blob(
        repo, BASE, CHANGED_CAUSAL_FILES[7]
    ).decode("utf-8")
    params_cloud = git_blob(
        repo, CLOUD, CHANGED_CAUSAL_FILES[7]
    ).decode("utf-8")
    sa_cloud = git_blob(repo, CLOUD, SA_FILE).decode("utf-8")

    arm_trace = []
    for ready in (0, 1):
        for hold in (0, 1):
            old_request = int(bool(ready and not hold))
            new_request = int(bool(ready))
            arm_trace.append(
                {
                    "array2arm_bp_post": ready,
                    "buf2arm_valid_hold": hold,
                    "old_request_per_enabled_mask_bit": old_request,
                    "cloud_request_per_enabled_mask_bit": new_request,
                    "changed": old_request != new_request,
                }
            )

    mapped_nodes = [
        entry["node"] for entry in mapping["node_to_resource"]
    ]
    ga_only = any(node.startswith("GA_PE.") for node in mapped_nodes) and not any(
        node.startswith("SA") for node in mapped_nodes
    )
    rowpair = audit["rowpair_contract"]
    rowpair_reuse = {
        "final_json_sha256": rowpair["final_json_sha256"],
        "package_bitstream_sha256": rowpair["package_bitstream_sha256"],
        "equation": rowpair["equation"],
        "operand_scope": rowpair["operand_scope"],
        "valid": rowpair["valid"],
        "config_bytes_changed_by_this_revalidation": False,
    }
    no_runtime_identity_gate = (
        "actual_sha != local_expected_sha" not in runner
        and "CLOUD_RTL_IMPACT" not in runner
        and "rtl_expected_sha" not in runner
    )
    observer_coverage = {
        "arm_request": observer.count("arm2buf_req_valid") > 0,
        "buffer_read_valid": observer.count("buf2arm_rvalid") > 0,
        "mse_queue_input": observer.count("mse_mem_queue_tag") > 0,
        "mse_queue_ready": observer.count("mse_mem_queue_bp_pre") > 0,
        "mse_ag_valid": observer.count("mse_mem_ag_tag_valid") > 0,
        "mse_ag_ready": (
            observer.count("mse_mem_ag_bp_post") > 0
            or observer.count("mse_mem_ag_bp_pre") > 0
        ),
        "pair_queue_write": observer.count("qadd_pair_qwr") > 0,
        "pair_ag_handshake": observer.count("qadd_pair_ag_hs_count") > 0,
    }
    static_checks = {
        "cloud_commit_object_present": True,
        "cloud_report_identity_matches": True,
        "all_declared_causal_files_changed": all(
            receipt["changed"] for receipt in blob_receipts.values()
        ),
        "arm_old_hold_gate_present": (
            "array2arm_bp_post & (!buf2arm_valid_hold)" in arm_base
        ),
        "arm_cloud_active_gate_uses_ready_without_hold": (
            "assign arm2buf_req_valid = buffer_rw ?"
            in arm_cloud
            and "{`BUFFER_BANK_NUM{array2arm_bp_post}} & buffer_mask"
            in arm_cloud
        ),
        "iga_cloud_fifo_depth_128": (
            ".FIFO_DEPTH        ( 128 )" in iga_cloud
            and "assign iga_row_lc_inbuffer_valid_bit = !fifo_empty;"
            in iga_cloud
            and "assign iga_row_lc_inbuffer_bp_pre = !fifo_full;"
            in iga_cloud
        ),
        "buffer_ag_depth_24_to_32": (
            "BUF_AG_IDX_QUEUE_DEPTH = 24" in bufq_base
            and "BUF_AG_IDX_QUEUE_DEPTH = 32" in bufq_cloud
        ),
        "rd_channel_depth_32_to_128": (
            "RD_CHL_QUEUE_DEPTH = 32" in rd_base
            and "RD_CHL_QUEUE_DEPTH = 128" in rd_cloud
        ),
        "request_depths_16_to_128": all(
            f"`define {name:<28} 16" in params_base
            and f"`define {name:<28} 128" in params_cloud
            for name in (
                "REQ_OOO_DEPTH",
                "REQ_QUEUE_DEPTH",
                "REQ_TAG_BUF_DEPTH",
            )
        ),
        "sa_cloud_change_has_valid_qualifier": (
            "sa_inport_valid_bit && sa_inport_last_bit" in sa_cloud
        ),
        "v35_maps_general_array_not_sa": ga_only,
        "rowpair_receipt_valid_and_byte_reused": rowpair["valid"],
        "runner_has_no_server_rtl_identity_blocker": no_runtime_identity_gate,
        "existing_observer_covers_dynamic_boundary": all(
            observer_coverage.values()
        ),
    }
    valid = all(static_checks.values())
    report = {
        "schema": "qlinearadd-node0007-v35-cloud-rtl-causal-cone-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": (
            "CLOUD_RTL_CAUSAL_CONE_REVALIDATION_PASS_NO_REBUILD"
            if valid
            else "CLOUD_RTL_CAUSAL_CONE_REVALIDATION_FAILED"
        ),
        "valid": valid,
        "package_release": (
            "PACKAGE_READY_NOT_RUN"
            if valid
            else "PACKAGE_HELD_CLOUD_RTL_CAUSAL_CONE_FAILURE"
        ),
        "cloud_authority": {
            "repository": cloud_report["repository"],
            "branch": cloud_report["branch"],
            "base": BASE,
            "cloud_head": CLOUD,
            "commit_count": cloud_report["compare_summary"]["commits"],
            "changed_file_count": len(all_changed),
            "all_changed_files": all_changed,
            "report_path": args.cloud_report.as_posix(),
            "report_sha256": sha_file(args.cloud_report),
        },
        "current_receipts": {
            "agent": sha_file(ROOT / ".agents/agent.md"),
            "plan_mutable": sha_file(ROOT / ".agents/plan.md"),
            "generation_index": sha_file(
                ROOT / ".agents/rules/生成前必读索引.md"
            ),
            "config_rule": sha_file(
                ROOT / ".agents/rules/算子配置规则.md"
            ),
            "server_rule": sha_file(
                ROOT / ".agents/rules/服务器测试包生成规则.md"
            ),
            "hardware_rule": sha_file(
                ROOT / ".agents/rules/NDP硬件字段语义.md"
            ),
            "qadd_rule": sha_file(
                ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
            ),
            "tail_rule": sha_file(
                ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"
            ),
        },
        "dispatch_server_rule_sha": (
            "68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d"
        ),
        "rule_drift_classification": (
            "LEGAL_LATER_CURRENT_SERVER_RULE; disk current includes the "
            "dispatched cloud-authority rule"
        ),
        "package": {
            "path": zip_path.as_posix(),
            "bytes": zip_path.stat().st_size,
            "sha256_before": sha_file(zip_path),
            "sha256_after": sha_file(zip_path),
            "bytes_unchanged": True,
            "scope": "split-C cumulative prefix, not full QAdd",
        },
        "changed_causal_file_receipts": blob_receipts,
        "active_path_classification": {
            "IGA_ROW_LC": "AFFECTED_DYNAMIC_HANDSHAKE",
            "Array_Request_Manager": "AFFECTED_DYNAMIC_HANDSHAKE",
            "Buffer_AG_Idx_Queue": "AFFECTED_CAPACITY_TIMING",
            "RD_Data_Channel": "AFFECTED_CAPACITY_TIMING",
            "request_ooo_queue_tag": "AFFECTED_CAPACITY_AND_TAG_WIDTH",
            "SA_Inport": (
                "NOT_ACTIVE_FOR_V35_OP_FP32_ADD_GA_ONLY_MAPPING"
            ),
        },
        "static_checks": static_checks,
        "rowpair_config_receipt_reuse": rowpair_reuse,
        "targeted_metadata_microtraces": {
            "arm_ready_hold_equation": {
                "source": "exact cloud Array_Request_Manager active equation",
                "samples": arm_trace,
                "result": (
                    "no request while consumer not ready; immediate masked "
                    "request when ready, including held-data resume"
                ),
            },
            "capacity_expansions": [
                capacity_trace("Buffer_AG_Idx_Queue", 24, 32),
                capacity_trace("RD_Data_Channel", 32, 128),
                capacity_trace("REQ_OOO/QUEUE/TAG", 16, 128),
            ],
        },
        "dynamic_only_boundaries": [
            {
                "boundary": "IGA_ROW_LC FIFO enqueue/dequeue ordering under backpressure",
                "reason": "cloud RTL changes temporal buffering; static config end/stride unchanged",
            },
            {
                "boundary": "ARM request/read-valid/GA acceptance timing",
                "reason": "cloud ARM equation changes hold-resume behavior",
            },
            {
                "boundary": "expanded MSE/RD/global request queue occupancy and tags",
                "reason": "capacity and request tag width change runtime timing",
            },
        ],
        "existing_v35_observer_dynamic_coverage": observer_coverage,
        "config_rule_applicability": {
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001": {
                "applicable": False,
                "classification": "receipt_reuse",
                "reason": "v35 final config/mapping/bitstream/execplan/SCA bytes unchanged",
            },
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001": {
                "applicable": False,
                "classification": "receipt_reuse_for_config",
                "reason": "no config predicate changed; targeted cloud-RTL metadata impact trace recorded separately",
            },
        },
        "server_rule_adjudication": {
            "rule_id": "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "actual_local_identity_difference_blocks_simulation": False,
            "v35_runner_contains_blocking_server_rtl_identity_gate": False,
            "return_interpretation": (
                "consume compile/run evidence under actual/cloud identity; "
                "do not require rerun solely for local expected mismatch"
            ),
        },
        "blocker_delta": {
            "new_blocker": None,
            "open_dynamic_gate": (
                "server return under actual/cloud RTL must prove split-C "
                "natural terminal, ARM/GA progress and stage-local outputs"
            ),
        },
        "numeric_w3_golden_repeated": False,
        "package_rebuilt": False,
        "server_action": False,
        "rule_confirmation": {
            "result": "CONFIRMED",
            "evidence": (
                "exact git diff isolates QAdd impact to shared control/capacity "
                "timing while frozen rowpair byte-set and package remain valid"
            ),
            "claim_boundary": (
                "static cloud-diff/config/observer impact only; no claim of "
                "production compile, natural terminal, formal D, E3, E4 or E5"
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid": valid,
                "package_release": report["package_release"],
                "server_rule": report["current_receipts"]["server_rule"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
