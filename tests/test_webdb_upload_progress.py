import base64
import gzip
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from thrust.webdb_client import WebDbClient


class WebDbUploadProgressTests(unittest.TestCase):
    def test_upload_stream_reports_progress_and_confirmation_stage(self):
        received = {}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received["path"] = self.path
                received["csrf"] = self.headers.get("X-CSRF-Token")
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received["payload"] = json.loads(body)
                response = json.dumps({"id": "measurement-1", "raw_size_bytes": 20}).encode()
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, *_args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with TemporaryDirectory() as directory:
                archive = Path(directory) / "measurement.tsv.gz"
                archive.write_bytes(gzip.compress(b"Time[s]\tLX\n0\t1\n"))
                client = WebDbClient(f"http://127.0.0.1:{server.server_port}", timeout=2)
                client.csrf_token = "csrf-test"
                events = []
                result = client.upload_measurement(
                    participant_id="participant-1",
                    test_definition_id="test-1",
                    started_at="2026-10-15T00:00:00Z",
                    raw_log_path=archive,
                    analysis_data={"valid": True},
                    precompressed=True,
                    progress_callback=lambda *event: events.append(event),
                )

            self.assertEqual(result["id"], "measurement-1")
            self.assertEqual(received["path"], "/api/admin/measurements")
            self.assertEqual(received["csrf"], "csrf-test")
            raw = base64.b64decode(received["payload"]["raw_log_base64"])
            self.assertEqual(gzip.decompress(raw), b"Time[s]\tLX\n0\t1\n")
            upload_events = [event for event in events if event[0] == "Uploading measurement"]
            self.assertGreaterEqual(len(upload_events), 2)
            self.assertEqual(upload_events[-1][1], upload_events[-1][2])
            self.assertEqual(events[-1][0], "Waiting for WebDB confirmation")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
