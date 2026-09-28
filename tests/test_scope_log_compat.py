import tempfile
import unittest
from pathlib import Path

from scope.scope_config import ScopeConfig
from thrust.analysis.scope_log import analyze_scope_log


class ScopeLogNamingTests(unittest.TestCase):
    def test_legacy_tsv_columns_are_normalized_to_new_axes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.tsv"
            path.write_text(
                "TIME\tAILE\tELEV\tTHRO\tRUDD\tAREQ\tEREQ\tTREQ\tRREQ\n"
                "0.00\t0\t0\t0\t0\t0\t0\t0\t0\n"
                "0.01\t100\t100\t100\t100\t200\t200\t200\t200\n",
                encoding="utf-8",
            )
            result = analyze_scope_log(path)
        self.assertEqual(set(result["columns"]), {
            "TIME", "LX", "LY", "RY", "RX", "LXRQ", "LYRQ", "RYRQ", "RXRQ"
        })
        self.assertEqual(result["schema_version"], "scope-analysis-v4")

    def test_legacy_axis_map_settings_load_into_new_keys(self):
        config = ScopeConfig.from_dict({
            "axis_map": {"AILE": 3, "ELEV": 2, "THRO": 1, "RUDD": 0}
        })
        self.assertEqual(config.axis_map, {"LX": 3, "LY": 2, "RY": 1, "RX": 0})


if __name__ == "__main__":
    unittest.main()
