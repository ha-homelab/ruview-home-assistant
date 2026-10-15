# SPDX-License-Identifier: MIT
"""Check the real project's changelog against its actual publication parser."""

import base64
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "project_release_control", ROOT / "scripts/release_control.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ProjectReleaseNotesTests(unittest.TestCase):
    def test_current_changelog_can_publish_the_base_version(self):
        policy = json.loads((ROOT / ".release-policy.json").read_text())
        source = "a" * 40
        raw = (ROOT / "CHANGELOG.md").read_bytes()
        response = {
            "type": "file",
            "path": "CHANGELOG.md",
            "encoding": "base64",
            "content": base64.b64encode(raw).decode(),
            "size": len(raw),
            "sha": hashlib.sha1(
                b"blob " + str(len(raw)).encode() + b"\0" + raw,
                usedforsecurity=False,
            ).hexdigest(),
        }
        github = Mock()
        github.api.return_value = response
        with patch.object(
            release, "source_policy_snapshot", return_value={"data": policy}
        ):
            notes = release.release_notes(
                github, "v0.1.0-beta.3", source, "Verified source provenance."
            )
        github.api.assert_called_once_with(f"contents/CHANGELOG.md?ref={source}")
        self.assertIn("### Upgrade", notes)
        self.assertIn("### Security", notes)
        self.assertIn("Verified source provenance.", notes)
