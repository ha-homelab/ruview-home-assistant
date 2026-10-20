# SPDX-License-Identifier: MIT
"""Release staging must retain the inputs required by the shipped recipes."""

import importlib.util
import shlex
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_release_under_test", ROOT / "scripts/build_release.py"
)
assert SPEC and SPEC.loader
BUILDER = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules):
    with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
        SPEC.loader.exec_module(BUILDER)


class ReleaseSourcesTests(unittest.TestCase):
    def test_selected_source_retains_complete_shipped_recipe_inputs(self):
        paths = BUILDER.selected_files()
        self.assertTrue(all(path.is_file() for path in paths))
        selected = {path.relative_to(ROOT).as_posix() for path in paths}
        # These are data/code dependencies of Dockerfile, the qualified release
        # clients, and public governance links, not optional packaging metadata.
        required = {
            "container/requirements-installer.txt",
            ".github/cosign/LICENSE",
            ".github/cosign/go.mod",
            ".github/cosign/go.sum",
            ".github/gh/LICENSE",
            ".github/gh/release.json",
            "scripts/download_release_gh.go",
            "GOVERNANCE.md",
            "CODE_OF_CONDUCT.md",
            "ROADMAP.md",
        }
        self.assertFalse(required - selected, sorted(required - selected))
        for line in (ROOT / "Dockerfile").read_text().splitlines():
            if not line.startswith("COPY "):
                continue
            for source in shlex.split(line)[1:-1]:
                with self.subTest(docker_source=source):
                    self.assertTrue(
                        source in selected
                        or any(
                            name.startswith(source.rstrip("/") + "/")
                            for name in selected
                        ),
                        f"Dockerfile source missing from release: {source}",
                    )
        self.assertEqual(len(selected), len(paths))
        self.assertFalse(
            any(
                {".git", ".venv", "__pycache__"}.intersection(Path(name).parts)
                or name.endswith(".local.json")
                for name in selected
            )
        )


if __name__ == "__main__":
    unittest.main()
