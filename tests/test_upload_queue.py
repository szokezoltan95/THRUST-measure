import json
import tempfile
import unittest
from pathlib import Path

from thrust.upload_queue import MeasurementUploadQueue


class UploadQueueTests(unittest.TestCase):
    def test_upload_queue_survives_a_new_instance_without_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = MeasurementUploadQueue(Path(directory))
            queue_id = queue.enqueue({
                "participant_code": "A1234",
                "participant_id": "participant-uuid",
                "raw_log_path": "/measurements/run.tsv",
                "client": object(),
            })

            restored = MeasurementUploadQueue(Path(directory)).pending()

            self.assertEqual(len(restored), 1)
            self.assertEqual(restored[0]["queue_id"], queue_id)
            self.assertEqual(restored[0]["participant_code"], "A1234")
            self.assertNotIn("client", restored[0])

    def test_queue_updates_atomically_and_removes_completed_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = MeasurementUploadQueue(Path(directory))
            queue_id = queue.enqueue({"raw_log_path": "/measurements/run.tsv"})
            queue.update(queue_id, raw_log_path="/measurements/run.tsv.gz", queue_status="failed")

            record = json.loads((Path(directory) / f"{queue_id}.json").read_text(encoding="utf-8"))
            self.assertTrue(record["raw_log_path"].endswith(".gz"))
            self.assertEqual(record["queue_status"], "failed")

            queue.remove(queue_id)
            self.assertEqual(queue.pending(), [])
