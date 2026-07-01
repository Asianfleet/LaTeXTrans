"""Tests for the Zotero adapter used by the Textual UI."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.tui.zotero_adapter import ZoteroAdapter


class ZoteroAdapterTests(unittest.TestCase):
    """Verify Zotero CLI delegation and Web API PDF attachment upload."""

    def test_list_libraries_runs_existing_zotero_cli(self):
        """List libraries through the existing Zotero skill CLI command."""
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps([{"library_id": "1", "library_type": "user"}]),
            stderr="",
        )
        with patch("subprocess.run", return_value=completed) as run_mock:
            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
            ).list_libraries()

        self.assertEqual(result[0]["library_id"], "1")
        self.assertIn("list-libraries", run_mock.call_args.args[0])

    def test_search_items_passes_selected_library_to_existing_zotero_cli(self):
        """Search items with the selected explicit Zotero library scope."""
        completed = subprocess.CompletedProcess(
            args=["python"],
            returncode=0,
            stdout=json.dumps([{"key": "ITEM123", "title": "Paper"}]),
            stderr="",
        )
        with patch("subprocess.run", return_value=completed) as run_mock:
            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
            ).search_items("Paper", "42", "group")

        command = run_mock.call_args.args[0]
        self.assertEqual(result[0]["key"], "ITEM123")
        self.assertIn("--library-id", command)
        self.assertIn("42", command)
        self.assertIn("--library-type", command)
        self.assertIn("group", command)

    def test_attach_pdf_creates_child_attachment_and_uploads_file(self):
        """Attach a translated PDF through child attachment and upload requests."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "translated.pdf"
            pdf_path.write_bytes(b"%PDF translated")

            session = Mock()
            create_response = Mock()
            create_response.json.return_value = {"successful": {"0": {"key": "ATTACH1"}}}
            create_response.raise_for_status.return_value = None
            auth_response = Mock()
            auth_response.json.return_value = {
                "url": "https://upload.example.test",
                "contentType": "multipart/form-data; boundary=x",
                "prefix": "PREFIX",
                "suffix": "SUFFIX",
                "uploadKey": "UPLOAD1",
            }
            auth_response.raise_for_status.return_value = None
            upload_response = Mock()
            upload_response.raise_for_status.return_value = None
            register_response = Mock()
            register_response.raise_for_status.return_value = None
            session.post.side_effect = [create_response, auth_response, upload_response, register_response]

            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
                session=session,
            ).attach_pdf("ITEM123", str(pdf_path), "42", "group")

        self.assertEqual(result["attachment_key"], "ATTACH1")
        self.assertEqual(result["status"], "uploaded")
        create_call = session.post.call_args_list[0]
        self.assertEqual(create_call.args[0], "https://api.zotero.org/groups/42/items")
        self.assertEqual(create_call.kwargs["json"][0]["parentItem"], "ITEM123")
        self.assertEqual(create_call.kwargs["json"][0]["linkMode"], "imported_file")
        write_token = create_call.kwargs["headers"]["Zotero-Write-Token"]
        self.assertEqual(len(write_token), 32)
        self.assertNotIn("-", write_token)
        register_call = session.post.call_args_list[3]
        self.assertEqual(register_call.kwargs["data"]["upload"], "UPLOAD1")

    def test_attach_pdf_returns_exists_when_zotero_reports_existing_file(self):
        """Return the existing-file status without uploading duplicate bytes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / "translated.pdf"
            pdf_path.write_bytes(b"%PDF translated")
            session = Mock()
            create_response = Mock()
            create_response.json.return_value = {"successful": {"0": {"key": "ATTACH1"}}}
            create_response.raise_for_status.return_value = None
            auth_response = Mock()
            auth_response.json.return_value = {"exists": 1}
            auth_response.raise_for_status.return_value = None
            session.post.side_effect = [create_response, auth_response]

            result = ZoteroAdapter(
                python_cmd=["python"],
                script_path="zotero.py",
                api_key="secret",
                session=session,
            ).attach_pdf("ITEM123", str(pdf_path), "42", "group")

        self.assertEqual(result, {"attachment_key": "ATTACH1", "status": "exists"})
        self.assertEqual(session.post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
