import gzip
import tempfile
import unittest
from pathlib import Path

from thrust.raw_compression import compress_raw_log


class RawCompressionTests(unittest.TestCase):
    def test_compresses_losslessly_and_removes_plaintext(self):
        original = b"Time[s]\tPOSX\tPOSY\n0.000000\t1.250000\t-3.500000\n"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.tsv"
            source.write_bytes(original)
            compressed = compress_raw_log(source)
            self.assertEqual(compressed.name, "sample.tsv.gz")
            self.assertFalse(source.exists())
            with gzip.open(compressed, "rb") as handle:
                self.assertEqual(handle.read(), original)

    def test_gzip_input_is_left_unchanged(self):
        original = b"TIME\tLX\n0\t1\n"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.tsv.gz"
            with gzip.open(source, "wb") as handle:
                handle.write(original)
            self.assertEqual(compress_raw_log(source), source)
            with gzip.open(source, "rb") as handle:
                self.assertEqual(handle.read(), original)


if __name__ == "__main__":
    unittest.main()
