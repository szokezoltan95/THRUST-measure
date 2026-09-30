import gzip
import tempfile
import unittest
from pathlib import Path

from scripts.import_measurements import normalize_raw_log, resolve_test_descriptor


class LegacyImportNormalizationTests(unittest.TestCase):
    def test_legacy_scope_axes_are_renamed_and_rows_reordered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scope_log_ABCDE_HARD_old_SCOPE.tsv"
            path.write_text(
                "AILE\tTIME[s]\tRUDD\tELEV\tTHRO\tAREQ\tEREQ\tTREQ\tRREQ\n"
                "1\t0.25\t4\t2\t3\t5\t6\t7\t8\n",
                encoding="utf-8",
            )
            normalized, changed = normalize_raw_log(path, "SCOPE")
            rows = gzip.decompress(normalized).decode("utf-8").splitlines()
            self.assertTrue(changed)
            self.assertEqual(rows[0], "TIME\tLX\tLY\tRY\tRX\tLXRQ\tLYRQ\tRYRQ\tRXRQ")
            self.assertEqual(rows[1], "0.25\t1\t2\t3\t4\t5\t6\t7\t8")

    def test_legacy_test_definition_has_explicit_legacy_version(self):
        _, descriptor = resolve_test_descriptor(
            {"mode": "SCOPE", "profile": "SCOPE_HARD_OLD", "difficulty": "HARD", "legacy": "true"},
            [],
        )
        self.assertEqual(descriptor["version"], "LEGACY")
        self.assertEqual(descriptor["test_code"], "LEGACY_SCOPE_HARD_OLD")


if __name__ == "__main__":
    unittest.main()
