import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from src.events import SCHEMA_VERSION, JsonLinesEventSink, build_event


class EventBuilderTests(unittest.TestCase):
    def test_build_event_adds_schema_type_and_timestamp(self):
        event = build_event("project_start", project_name="paper")

        self.assertEqual(event["schema_version"], SCHEMA_VERSION)
        self.assertEqual(event["type"], "project_start")
        self.assertEqual(event["project_name"], "paper")
        self.assertIn("T", event["timestamp"])
        self.assertRegex(event["timestamp"], r"(Z|[+-]\d\d:\d\d)$")


class JsonLinesEventSinkTests(unittest.TestCase):
    def test_stdout_sink_writes_one_json_object_per_line(self):
        stdout = StringIO()
        sink = JsonLinesEventSink(stdout=True, stdout_stream=stdout)

        sink.write({"type": "project_start", "project_name": "论文"})
        sink.close()

        lines = stdout.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        payload = json.loads(lines[0])
        self.assertEqual(payload["type"], "project_start")
        self.assertEqual(payload["project_name"], "论文")

    def test_file_sink_writes_utf8_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "nested" / "events.jsonl"
            sink = JsonLinesEventSink(file_path=str(path))
            sink.write({"type": "run_complete", "project_name": "论文", "ok": True})
            sink.close()

            raw_text = path.read_text(encoding="utf-8").strip()
            self.assertIn('"论文"', raw_text)
            payload = json.loads(raw_text)

        self.assertEqual(payload["type"], "run_complete")
        self.assertEqual(payload["project_name"], "论文")
        self.assertTrue(payload["ok"])

    def test_stdout_and_file_receive_same_event(self):
        stdout = StringIO()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "events.jsonl"
            sink = JsonLinesEventSink(stdout=True, file_path=str(path), stdout_stream=stdout)
            event = {"type": "project_complete", "pdf_path": r"D:\paper.pdf"}
            sink.write(event)
            sink.close()

            stdout_payload = json.loads(stdout.getvalue().strip())
            file_payload = json.loads(path.read_text(encoding="utf-8").strip())

        self.assertEqual(stdout_payload, file_payload)
        self.assertEqual(file_payload["pdf_path"], r"D:\paper.pdf")


if __name__ == "__main__":
    unittest.main()
