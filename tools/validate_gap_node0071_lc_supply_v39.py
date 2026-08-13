from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v40_lc_supply_conservation_diag"
SOURCE = "r5_n71_gap_v37_dbclk_rdready_compilefix"
TEST_ID = "r5-gap-node0071-v40-lc-supply-conservation-information-gain"
OBSERVER = "tb_probe/native_return_observer.svh"
RUNNER = "PREPARE_AND_RUN.sh"
FEATURE = "RETURN_OBS_LC_SUPPLY_CONSERVATION"
CURRENT_FILES = {
    "agent_sha256": ROOT / ".agents/agent.md",
    "plan_sha256_mutable_provenance_only": ROOT / ".agents/plan.md",
    "generation_index_sha256": ROOT / ".agents/rules/生成前必读索引.md",
    "server_rule_sha256": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_operator_rule_sha256": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_field_rule_sha256": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "gap_int32_rule_sha256":
        ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md",
    "gap_probe_rule_sha256":
        ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md",
    "exact_uint8_tail_rule_sha256":
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def checks(
    manifest: dict[str, Any], observer: str, runner: str
) -> dict[str, bool]:
    contract = manifest.get(
        "lc_supply_conservation_information_gain_contract", {}
    )
    cloud = contract.get("cloud_rtl_authority_contract", {})
    matrix = manifest.get("release_gate_matrix", {})
    rules = set(manifest.get("applicable_rule_ids") or [])
    receipts = manifest.get("rule_receipts", {})
    sampler = observer.split(
        "// v38 sampler: exact owner-clock qualified FIFO accepts "
        "and surface edges.", 1
    )[-1].split(
        "// v33 sampler: qualified input accepts and FIFO accepts only.", 1
    )[0]
    sim_args = runner.split("sim_args=(", 1)[-1].split("\n)", 1)[0]
    required_xmr = (
        "u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.add_wr_ptr",
        "u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.add_rd_ptr",
        "u_Buffer_AG_Idx_Queue.u_buf_ag_idx_queue.fifo_counter",
        "u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.add_wr_ptr",
        "u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.add_rd_ptr",
        "u_Memory_AG_Idx_Queue.u_mem_ag_idx_queue.fifo_counter",
    )
    public = (
        "u_Memory_AG_Idx_Queue.mse_mem_queue_tag",
        "u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre",
        "u_Memory_AG_Idx_Queue.mse_mem_ag_tag_valid",
        "u_Memory_AG_Idx_Queue.mse_mem_ag_bp_post",
        "u_RD_Memory_AG.rd_data_chl_req_valid",
        "u_RD_Memory_AG.rd_data_chl_req_ready",
        "u_Buffer_AG_Idx_Queue.mse_buf_ag_tag_valid",
        "u_Buffer_AG_Idx_Queue.mse_buf_ag_bp_post",
    )
    return {
        "identity": (
            manifest.get("test_id") == TEST_ID
            and manifest.get("package_name") == NAME
            and manifest.get("install_name") == NAME
            and manifest.get("run_name") == f"run_{NAME}"
            and manifest.get("return_name") == f"{NAME}_return"
        ),
        "diagnostic_only": (
            manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("evidence_ceiling") == "E2_LOCAL_ONLY"
        ),
        "source_and_trigger": (
            manifest.get("supersedes_package_sha256")
            == "796312c5c4c5ed941a78fd4a0cf245bb580edac9b1b7ff5960b8e78c3eb8fa7b"
            and manifest.get("trigger_return_sha256")
            == "dd9f4551f4fd324f100fcb01ff50ec4a7a123df0e0bdc4a8705f02f52ce15f87"
        ),
        "current_receipts": all(
            receipts.get(key) == sha_path(path)
            for key, path in CURRENT_FILES.items()
            if key != "plan_sha256_mutable_provenance_only"
        ) and receipts.get("current_match") is True,
        "feature_contract": (
            contract.get("feature") == FEATURE
            and contract.get("limit") == 512
            and contract.get("owner_clock") == "clk_db / u_NDP_Top_new.clk"
            and contract.get("flows") == ["MSE0", "MSE3"]
            and contract.get("stable_level_policy")
            == "state/witness only; never monotonic progress"
        ),
        "cloud_rtl_authority_contract": (
            cloud.get("repository") == "xlsjdjdk/Trassic2.0_RTL"
            and cloud.get("branch") == "master"
            and cloud.get("approved_commit")
            == "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
            and cloud.get("local_expected_provenance_hint")
            == "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
            and cloud.get("runtime_success_predicate") is False
            and cloud.get(
                "actual_sha_mismatch_must_not_prevent_simulator_start"
            ) is True
            and cloud.get("gap_causal_cone_receipts", {}).get(
                "Buffer_AG_Idx_Queue.sv", {}
            ).get("depth") == 32
            and cloud.get("gap_causal_cone_receipts", {}).get(
                "RD_Data_Channel.sv", {}
            ).get("rd_channel_queue_depth") == 128
        ),
        "cloud_width_bound_observer": (
            "logic [1:0][5:0] return_obs_lcsc_bq_count_mon;"
            in observer
            and contract.get("necessary_private_xmr", {}).get(
                "buffer_ag_fifo_depth"
            ) == 32
            and contract.get("necessary_private_xmr", {}).get(
                "buffer_ag_fifo_counter_width"
            ) == 6
        ),
        "observer_runtime_enable": (
            f'$test$plusargs("{FEATURE}")' in observer
            and f'"{FEATURE}_LIMIT=%d"' in observer
        ),
        "observer_time0_marker": (
            "lc_supply_conservation=%0d "
            "lc_supply_conservation_limit=%0d owner_clock=clk_db"
            in observer
        ),
        "observer_record_schemas": all(
            item in observer
            for item in (
                "LC_SUPPLY_CONSERVATION_COUNTS_V1",
                "LC_SUPPLY_CONSERVATION_STATE_V1",
                "LC_SUPPLY_CONSERVATION_WITNESS_V1",
                "LC_SUPPLY_CONSERVATION_EVENT_V1",
            )
        ),
        "observer_owner_clock": (
            "// v38 sampler: exact owner-clock qualified FIFO accepts "
            "and surface edges." in observer
            and "always @(posedge u_NDP_Top_new.clk)" in sampler
            and "clk_sg" not in sampler
        ),
        "observer_exact_predicate": (
            "return_obs_lcsc_bq_add_wr_mon[lcsc_flow] ||" in observer
            and "return_obs_lcsc_bq_add_rd_mon[lcsc_flow] ||" in observer
            and "return_obs_lcsc_mq_add_wr_mon[lcsc_flow] ||" in observer
            and "return_obs_lcsc_mq_add_rd_mon[lcsc_flow] ||" in observer
            and "lcsc_req || lcsc_surface_edge;" in observer
        ),
        "qualified_updates": all(
            item in observer
            for item in (
                "return_obs_lcsc_bq_wr[lcsc_flow]++;",
                "return_obs_lcsc_bq_rd[lcsc_flow]++;",
                "return_obs_lcsc_mq_wr[lcsc_flow]++;",
                "return_obs_lcsc_mq_rd[lcsc_flow]++;",
                "if (lcsc_req) return_obs_lcsc_req[lcsc_flow]++;",
            )
        ),
        "private_xmr_exact_consumers": all(
            observer.count(item) >= 2 for item in required_xmr
        ),
        "public_surface_consumers": all(
            observer.count(item) == 2 for item in public
        ),
        "runner_actual_argv": (
            f"  +{FEATURE}\n" in sim_args
            and f"  +{FEATURE}_LIMIT=512\n" in sim_args
        ),
        "runner_return_binding": (
            "lc_supply_conservation_enabled=true" in runner
            and "lc_supply_conservation_records_returned=true" in runner
            and "LC_SUPPLY_CONSERVATION_COUNTS_V1" in runner
            and "LC_SUPPLY_CONSERVATION_STATE_V1" in runner
            and "LC_SUPPLY_CONSERVATION_WITNESS_V1" in runner
        ),
        "release_gate_matrix": (
            matrix.get("single_matrix") is True
            and matrix.get("core_always", {}).get("blocking") is True
            and matrix.get("runner", {}).get("blocking") is True
            and matrix.get("package_local_hdl", {}).get("blocking") is True
            and matrix.get("diagnostic_semantics", {}).get("blocking") is True
            and matrix.get("return_result", {}).get("blocking") is True
            and matrix.get("materialized_config", {}).get(
                "applicable"
            ) is False
            and matrix.get("materialized_config", {}).get(
                "blocking"
            ) is False
        ),
        "current_rule_ids": all(
            item in rules
            for item in (
                "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
                "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            )
        ),
        "functional_boundaries_frozen": (
            contract.get("config_changed") is False
            and contract.get("timeout_changed") is False
            and contract.get("backpressure_changed") is False
            and contract.get("functional_rtl_modified") is False
        ),
    }


def predicate_trace() -> dict[str, Any]:
    cases = [
        ("none_stable", 0, 0, 0, 0, 0, 0, False),
        ("bq_wr", 1, 0, 0, 0, 0, 0, True),
        ("bq_rd", 0, 1, 0, 0, 0, 0, True),
        ("mq_wr", 0, 0, 1, 0, 0, 0, True),
        ("mq_rd", 0, 0, 0, 1, 0, 0, True),
        ("req_valid_only", 0, 0, 0, 0, 1, 0, False),
        ("req_ready_only", 0, 0, 0, 0, 0, 1, False),
        ("req_handshake", 0, 0, 0, 0, 1, 1, True),
        ("surface_edge", 0, 0, 0, 0, 0, 0, True),
        ("simultaneous", 1, 1, 1, 1, 1, 1, True),
        ("stage_inactive", 1, 1, 1, 1, 1, 1, False),
        ("reset", 1, 1, 1, 1, 1, 1, False),
    ]
    results = []
    for name, bw, br, mw, mr, rv, rr, expected in cases:
        surface_edge = name == "surface_edge"
        active = name not in {"stage_inactive", "reset"}
        reset = name == "reset"
        exact = bool(
            active
            and not reset
            and (bw or br or mw or mr or (rv and rr) or surface_edge)
        )
        results.append(
            {
                "name": name,
                "event": exact,
                "expected": expected,
                "pass": exact == expected,
            }
        )
    recent_escape = [
        {"cycle": 0, "event": False, "last_progress": None},
        {"cycle": 1, "event": True, "last_progress": 1},
        {"cycle": 2, "event": False, "last_progress": 1},
        {"cycle": 3, "event": False, "last_progress": 1},
    ]
    return {
        "schema": "gap-node0071-lc-supply-predicate-trace-v1",
        "owner_clock": "clk_db",
        "cases": results,
        "recent_escape_trace": recent_escape,
        "stable_level_not_progress": True,
        "pass": all(item["pass"] for item in results),
    }


def analyze(target: Path, source: Path) -> dict[str, Any]:
    errors: list[str] = []
    with zipfile.ZipFile(target) as archive:
        crc = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        roots = {
            PurePosixPath(name).parts[0]
            for name in names if PurePosixPath(name).parts
        }
        unsafe = [
            name for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        symlinks = [
            item.filename for item in infos
            if stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF)
        ]
        prefix = f"{NAME}/"
        manifest_payload = archive.read(
            prefix + "TEST_PACKAGE_MANIFEST.json"
        )
        manifest = json.loads(manifest_payload)
        observer_payload = archive.read(prefix + OBSERVER)
        runner_payload = archive.read(prefix + RUNNER)
        observer = observer_payload.decode("utf-8")
        runner = runner_payload.decode("utf-8")
        member_records = manifest["files"]
        receipt_ok = all(
            archive.getinfo(prefix + path).file_size == item["size_bytes"]
            and sha_bytes(archive.read(prefix + path)) == item["sha256"]
            for path, item in member_records.items()
        )
        exact_set = set(names) == {
            prefix + "TEST_PACKAGE_MANIFEST.json",
            *(prefix + path for path in member_records),
        }
    sidecar = Path(str(target) + ".sha256")
    sidecar_ok = (
        sidecar.is_file()
        and sidecar.read_text(encoding="ascii").strip()
        == f"{sha_path(target)}  {target.name}"
    )
    content_checks = checks(manifest, observer, runner)
    trace = predicate_trace()
    if crc is not None:
        errors.append(f"CRC failed at {crc}")
    if roots != {NAME}:
        errors.append("single root differs")
    if len(names) != len(set(names)):
        errors.append("duplicate members")
    if unsafe:
        errors.append("unsafe paths")
    if symlinks:
        errors.append("symlink members")
    if not receipt_ok:
        errors.append("manifest file receipts differ")
    if not exact_set:
        errors.append("manifest exact-set differs")
    if not sidecar_ok:
        errors.append("sidecar differs")
    for name, value in content_checks.items():
        if not value:
            errors.append(f"content check failed: {name}")
    if not trace["pass"]:
        errors.append("predicate trace failed")

    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target) as new:
        source_prefix = f"{SOURCE}/workload/"
        target_prefix = f"{NAME}/workload/"
        source_workload = {
            item.filename[len(source_prefix):]: old.read(item.filename)
            for item in old.infolist()
            if item.filename.startswith(source_prefix)
        }
        target_workload = {
            item.filename[len(target_prefix):]: new.read(item.filename)
            for item in new.infolist()
            if item.filename.startswith(target_prefix)
        }
    numeric_names = set(source_workload) - {
        "sca_cfg.json", "sca_cfg_D.json"
    }
    numeric_equal = (
        numeric_names
        == set(target_workload) - {"sca_cfg.json", "sca_cfg_D.json"}
        and len(numeric_names) == 73
        and all(
            source_workload[name] == target_workload[name]
            for name in numeric_names
        )
    )
    normalized_sca = {}
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        normalized = target_workload[name].decode("utf-8").replace(
            NAME, SOURCE
        ).encode("utf-8")
        normalized_sca[name] = normalized == source_workload[name]
    if not numeric_equal:
        errors.append("frozen numeric/workload tree differs")
    if not all(normalized_sca.values()):
        errors.append("identity-normalized SCA semantics differ")

    mutations = [
        (
            "feature_runtime_enable_removed",
            manifest, observer,
            runner.replace(f"  +{FEATURE}\n", "", 1),
        ),
        (
            "feature_binding_receipt_removed",
            manifest, observer,
            runner.replace(
                "lc_supply_conservation_records_returned=true",
                "lc_supply_conservation_records_returned=REMOVED",
                1,
            ),
        ),
        (
            "feature_time0_marker_removed",
            manifest,
            observer.replace(
                "# lc_supply_conservation=%0d "
                "lc_supply_conservation_limit=%0d owner_clock=clk_db",
                "# lc_supply_conservation_marker_removed",
                1,
            ),
            runner,
        ),
        (
            "feature_return_target_removed",
            manifest,
            observer,
            runner.replace(
                "LC_SUPPLY_CONSERVATION_COUNTS_V1",
                "LC_SUPPLY_CONSERVATION_COUNTS_REMOVED",
                1,
            ),
        ),
        (
            "actual_fifo_consumer_misspelled",
            manifest,
            observer.replace(
                "u_buf_ag_idx_queue.add_wr_ptr",
                "u_buf_ag_idx_queue.add_wr_typo",
                1,
            ),
            runner,
        ),
        (
            "critical_update_removed",
            manifest,
            observer.replace(
                "return_obs_lcsc_mq_wr[lcsc_flow]++;",
                "/* required update removed */",
                1,
            ),
            runner,
        ),
        (
            "owner_clock_reverted",
            manifest,
            observer.replace(
                "// v38 sampler: exact owner-clock qualified FIFO accepts "
                "and surface edges.\n"
                "    always @(posedge u_NDP_Top_new.clk)",
                "// v38 sampler: exact owner-clock qualified FIFO accepts "
                "and surface edges.\n"
                "    always @(posedge u_NDP_Top_new.clk_sg)",
                1,
            ),
            runner,
        ),
    ]
    controls = []
    for name, m, o, r in mutations:
        result = checks(m, o, r)
        controls.append(
            {
                "name": name,
                "failed_closed": not all(result.values()),
                "failed_checks": [
                    key for key, value in result.items() if not value
                ],
            }
        )
    all_controls = all(item["failed_closed"] for item in controls)
    if not all_controls:
        errors.append("negative control escaped")
    return {
        "schema": "gap-node0071-lc-supply-v40-validation-v1",
        "status": "PASS" if not errors else "FAIL",
        "valid": not errors,
        "target_zip": str(target),
        "target_zip_size_bytes": target.stat().st_size,
        "target_zip_sha256": sha_path(target),
        "source_zip": str(source),
        "source_zip_sha256": sha_path(source),
        "crc_valid": crc is None,
        "single_root": roots == {NAME},
        "path_safe": not unsafe,
        "duplicate_free": len(names) == len(set(names)),
        "symlink_free": not symlinks,
        "manifest_exact_set": exact_set,
        "manifest_file_receipts_valid": receipt_ok,
        "sidecar_valid": sidecar_ok,
        "content_checks": content_checks,
        "predicate_trace": trace,
        "frozen_numeric_workload_file_count": len(numeric_names),
        "frozen_numeric_workload_byte_equal": numeric_equal,
        "sca_identity_normalized_semantics_equal": normalized_sca,
        "negative_controls": controls,
        "all_negative_controls_fail_closed": all_controls,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(
        args.target_zip.resolve(), args.source_zip.resolve()
    )
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
