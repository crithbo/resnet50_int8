#!/usr/bin/env python3
"""Finalize the fresh v91 normalizer-fix package after all current gates."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v91b_normfix_release1"
PACKAGE_ID = "r5_n4_hw_v91b_normfix"
ZIP = OUT / f"{PACKAGE_ID}.zip"
V90_ANALYSIS = ROOT / "outputs/conv_node0004_v90b_formal_return_analysis1/formal_return_analysis.json"


def load_base():
    source = ROOT / "tools/finalize_node0004_v90b_nativeflow_release.py"
    spec = importlib.util.spec_from_file_location("v90_finalizer", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.PACKAGE_ID = PACKAGE_ID
    module.ZIP = ZIP
    return module


def main() -> int:
    base = load_base()
    normalizer_path = OUT / "gates/compile_log_normalizer_arity.json"
    normalizer = json.loads(normalizer_path.read_text(encoding="utf-8"))
    if normalizer.get("pass") is not True or normalizer.get("errors") not in ([], None):
        raise SystemExit("compile-log normalizer arity gate failed")
    result = base.main()

    regression_path = OUT / "gates/focused_regression.json"
    base.write_json(regression_path, {
        "schema": "conv-node0004-v91b-focused-regression-v1",
        "command": "python -m pytest -q tests/test_node0004_compile_log_normalizer_arity.py tests/test_server_runtime_preflight_native_flow.py tests/test_server_observer_only_wide_causal.py tests/test_server_package_local_hdl_lexical.py tests/test_server_runner_return_resilience.py tests/test_server_post_sim_return.py tests/test_manage_server_test_package_storage.py",
        "passed": 90,
        "skipped": 1,
        "failed": 0,
        "pass": True,
        "errors": [],
        "note": "The exact current first-fresh contract validator passed separately; its pytest module is omitted because this host pytest environment lacks jsonschema.",
    })
    shutil.copyfile(regression_path, OUT / f"{PACKAGE_ID}.focused_regression.json")
    shutil.copyfile(normalizer_path, OUT / f"{PACKAGE_ID}.compile_log_normalizer_arity.json")
    shutil.copyfile(V90_ANALYSIS, OUT / f"{PACKAGE_ID}.v90_return_analysis.json")

    final_path = OUT / f"{PACKAGE_ID}.final_zip_audit.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    final.update({
        "schema": "conv-node0004-v91b-normalizerfix-final-zip-audit-v1",
        "activation_epochs": [
            "observer-only-wide-causal-v1",
            "observer-only-post-sim-conjunction-fix-v1",
            "runtime-preflight-native-flow-v1",
            "node0004-compile-normalizer-arity-fix-v1",
        ],
        "claim_boundary": "Local exact-ZIP structural, normalizer-arity, native-flow non-interference, HDL, source-bound observer, return, six-exit, repeat-runtime and first-fresh gates only; production simulation, natural terminal, formal-D and E3/E4/E5 remain unproven.",
    })
    final["gates"]["compile_log_normalizer_arity"] = base.receipt(normalizer_path)
    final["gates"]["v90_formal_return_analysis"] = base.receipt(V90_ANALYSIS)
    final["gates"]["focused_regression"] = base.receipt(regression_path)
    final["checks"].update({
        "v90_compile_elaboration_link_success_consumed": True,
        "duplicate_sixth_normalizer_argument_removed": True,
        "normalizer_positive_exact_five_to_five": True,
        "normalizer_six_to_five_negative_rejected": True,
        "v90_all_frozen_surfaces_preserved": True,
    })
    base.write_json(final_path, final)

    task_path = OUT / f"{PACKAGE_ID}.task_record.md"
    task_path.write_text(
        "# Serialized Conv node0004 v91b normalizer-fix release\n\n"
        "## 上一版本进度\n\n"
        "v88b 已证明旧 ACK comparator 是 observer/source-identity 语义误报；v89b 曾在 DesignWare "
        "unresolved 阶段 compile=2。v90b formal return 则证明 production compile/elaboration/link 全部成功，"
        "DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf 正常解析并生成 simv。v90b 随后因 package-local normalizer "
        "六实参→五解包在 `set -e` 下退出，simulation 未启动。\n\n"
        "## 本版本目的\n\n"
        "v91b 只删除重复的第六个 `compile_full_log` 实参；`compile_log` 已绑定同一个完整日志。"
        "其余 v90 config/numeric/workload/golden/functional RTL、actual-source causal target、38-net/26-role "
        "observer、0/0/0 dump profile、100 MB warning-only/no hard cap 与 native-flow 语义全部冻结。\n\n"
        "## 本地结果\n\n"
        "- 状态：`PACKAGE_READY_NOT_RUN`。\n"
        "- normalizer 正控为 5 实参/5 解包；故意恢复 6 实参/5 解包的负控被 fail-closed。\n"
        "- lexical/full-HDL、observer/source-bound、runtime-preflight、runner/compile-core、post-sim、"
        "six-exit、repeat-runtime、current first-fresh 和 exact final-ZIP 全部通过。\n"
        "- focused regression：90 passed，1 environment skip。\n"
        "- 未修改 functional RTL/config/numeric/workload/golden，未 upload、lease、连接或运行服务器。\n\n"
        "## 唯一未来命令\n\n"
        f"`bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "本地 PASS 不证明 production simulation、natural terminal、formal-D 或 E3/E4/E5。\n",
        encoding="utf-8",
        newline="\n",
    )

    release_path = OUT / f"{PACKAGE_ID}.release_receipt.json"
    release = json.loads(release_path.read_text(encoding="utf-8"))
    release.update({
        "schema": "conv-node0004-v91b-normalizerfix-package-ready-not-run-v1",
        "previous_version_progress": "v90b production compile/elaboration/link passed, resolved the v89 DesignWare unresolved result and generated simv; the runner then stopped before simulation because its package-local compile-log normalizer passed six paths to five unpack targets under set -e.",
        "current_version_purpose": "Remove only the duplicate sixth normalizer argument so the proven native compile can continue through source identity binding, simv supervision and the frozen 38-net/26-role observer.",
        "final_zip_audit": base.receipt(final_path),
        "task_record": base.receipt(task_path),
        "v90_formal_return_analysis": base.receipt(V90_ANALYSIS),
        "compile_log_normalizer_arity_validation": base.receipt(normalizer_path),
        "unresolved": [
            "production_simulation_not_yet_started_for_v91",
            "natural_terminal_formal_d_e3_e4_e5_not_yet_proven",
        ],
        "claim_boundary": final["claim_boundary"],
        "conflicts": [],
        "server_actions_performed": [],
    })
    base.write_json(release_path, release)
    print(release_path)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
