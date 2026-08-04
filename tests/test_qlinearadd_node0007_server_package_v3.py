from __future__ import annotations

import unittest

from tools.build_qlinearadd_node0007_server_package_v3 import (
    INSTALL_NAME,
    SIMULATION_TIMEOUT,
)
from tools.validate_qlinearadd_node0007_server_package_v3 import (
    PACKAGE,
    audit,
)


class QLinearAddNode0007ServerPackageV3Test(unittest.TestCase):
    def test_fresh_timeout_only_package_is_fail_closed(self) -> None:
        if not PACKAGE.is_dir():
            self.skipTest("v3 package is not built")
        report = audit()
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(PACKAGE.name, INSTALL_NAME)
        self.assertEqual(report["simulation_timeout"], SIMULATION_TIMEOUT)
        self.assertTrue(report["zip_crc_clean"])
        self.assertTrue(report["zip_package_exact_set"])
        self.assertEqual(report["rtl_or_tb_entry_count"], 0)
        self.assertEqual(report["preloaded_runtime_d_target_count"], 0)
        self.assertTrue(report["contract_binds_v3"])
        self.assertTrue(report["contract_cycle_break"]["valid"])
        self.assertTrue(all(report["reuse_equivalence"].values()))


if __name__ == "__main__":
    unittest.main()
