from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_gap_probe_return import build_return


class BuildGapProbeReturnTests(unittest.TestCase):
    def test_builds_allowlist_only_bounded_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ndp = root / "NDP_copy99"
            run = ndp / "run_gap_probe"
            evidence = ndp / "probe_evidence"
            package = root / "package"
            output = root / "return_output"
            cfg = ndp / "install" / "cfg_pkg" / "gap_probe"
            readback = ndp / "install" / "op0" / "slice00"
            sim_results = run / "sim_results"
            for directory in (
                evidence,
                package,
                cfg,
                readback,
                sim_results,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            (package / "TEST_PACKAGE_MANIFEST.json").write_text(
                '{"schema":"test"}\n', encoding="utf-8"
            )
            (cfg / "sca_cfg.json").write_text("{}\n", encoding="utf-8")
            (cfg / "sca_cfg_D.json").write_text(
                json.dumps(
                    {
                        "op0_matrixD_slice0": {
                            "base_addr": "0x0",
                            "path": (
                                "install/op0/slice00/"
                                "matrix_D_linearized_128bit.txt"
                            ),
                            "length": 1,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (readback / "matrix_D_linearized_128bit.txt").write_text(
                "0" * 32 + "\n", encoding="utf-8"
            )
            for name in (
                "server_identity_pre_install.json",
                "server_identity_post_install.json",
                "server_identity_post_run.json",
                "observer_install_report.json",
            ):
                (evidence / name).write_text("{}\n", encoding="utf-8")
            (evidence / "run_exit_status.txt").write_text(
                "0\n", encoding="utf-8"
            )
            (evidence / "server_command.txt").write_text(
                "make compile sim\n", encoding="utf-8"
            )
            (evidence / "return_observer.log").write_text(
                "1 | GA_ACCUM_STATE | n=1 input2=0x00000000\n",
                encoding="utf-8",
            )
            (sim_results / "compile.log").write_text(
                "compile ok\n", encoding="utf-8"
            )
            (sim_results / "sim.log").write_text(
                "Simulation completed successfully!\n", encoding="utf-8"
            )
            (sim_results / "wave.fsdb").write_bytes(b"not returned")
            (sim_results / "simv.daidir").mkdir()
            (sim_results / "simv.daidir" / "build_db").write_bytes(
                b"not returned"
            )

            report = build_return(
                ndp_root=ndp,
                run_dir=run,
                evidence_root=evidence,
                package_root=package,
                install_name="gap_probe",
                output_dir=output,
                run_status=0,
                server_command="make compile sim",
            )

            self.assertEqual(report["required_missing"], [])
            self.assertLessEqual(report["zip_size_bytes"], 16 * 1024 * 1024)
            with zipfile.ZipFile(report["zip"]) as archive:
                names = archive.namelist()
                self.assertTrue(
                    any(name.endswith("/RETURN_MANIFEST.json") for name in names)
                )
                self.assertFalse(any(name.endswith(".fsdb") for name in names))
                self.assertFalse(any("simv.daidir" in name for name in names))
                manifest_name = next(
                    name
                    for name in names
                    if name.endswith("/RETURN_MANIFEST.json")
                )
                manifest = json.loads(archive.read(manifest_name))
            self.assertEqual(
                manifest["zip_size_bytes"], Path(report["zip"]).stat().st_size
            )
            self.assertEqual(manifest["wave_policy"]["DUMP_FSDB"], 0)


if __name__ == "__main__":
    unittest.main()
