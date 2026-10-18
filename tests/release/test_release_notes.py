"""Release-note extraction and CLI regressions, runnable without HA dependencies."""

import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "generate_releasenotes.py"
SPEC = importlib.util.spec_from_file_location("release_notes", SCRIPT)
release_notes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## [Unreleased]

### Added
- Not released yet.

## [2.0.0] - 2026-10-18

### Fixed
- Preserve cached inventory.
- Report failed deletions.

### Security
- Redact API keys.

### Migration notes
- Existing TLS settings are unchanged.

## [1.1.1] - 2025-01-01

### Added
- Older changes.
"""


class TestReleaseNotes(unittest.TestCase):
    """Keep release publishing deterministic and fail closed for missing notes."""

    def test_exact_version_and_all_categories(self):
        for tag in ("2.0.0", "v2.0.0", "refs/tags/v2.0.0"):
            with self.subTest(tag=tag):
                notes = release_notes.extract_release_notes(CHANGELOG, tag)
                self.assertTrue(notes.startswith("### Fixed"))
                self.assertIn("### Security\n- Redact API keys.", notes)
                self.assertIn("### Migration notes", notes)
                self.assertNotIn("Not released yet", notes)
                self.assertNotIn("Older changes", notes)

    def test_missing_duplicate_and_undated_sections_fail(self):
        for changelog in (
            CHANGELOG.replace("[2.0.0]", "[2.0.1]"),
            CHANGELOG + "\n## [2.0.0] - 2026-10-18\n- Duplicate.",
            CHANGELOG.replace(" - 2026-10-18", ""),
        ):
            with self.subTest(changelog=changelog):
                with self.assertRaises(ValueError):
                    release_notes.extract_release_notes(changelog, "2.0.0")

    def test_empty_sections_fail(self):
        for body in ("", "### Fixed", "<!-- TODO: write notes -->", "### Added\n\n"):
            with self.subTest(body=body):
                with self.assertRaisesRegex(ValueError, "no release notes"):
                    release_notes.extract_release_notes(
                        "## [2.0.0] - 2026-10-18\n" + body, "2.0.0"
                    )

    def test_invalid_date_fails(self):
        with self.assertRaises(ValueError):
            release_notes.extract_release_notes(
                CHANGELOG.replace("2026-10-18", "2026-02-30"), "v2.0.0"
            )

    def test_invalid_tags_fail(self):
        for tag in ("Unreleased", "master", "2.0", "--help", "../2.0.0"):
            with self.subTest(tag=tag):
                with self.assertRaises(ValueError):
                    release_notes.extract_release_notes(CHANGELOG, tag)

    def test_prerelease(self):
        notes = release_notes.extract_release_notes(
            CHANGELOG.replace("[2.0.0]", "[2.0.0-rc.1]"), "v2.0.0-rc.1"
        )
        self.assertIn("Redact API keys", notes)

    def test_fenced_headings_do_not_split_sections(self):
        for fence in ("```", "~~~~"):
            with self.subTest(fence=fence):
                body = (
                    "### Example\n"
                    f"{fence}\n## [2.0.0] - 2026-10-18\n## Example\n{fence}\n"
                    "- Preserve this change."
                )
                changelog = f"## [2.0.0] - 2026-10-18\n{body}\n## [Unreleased]\n"
                self.assertEqual(
                    release_notes.extract_release_notes(changelog, "2.0.0"), body
                )

    def test_unicode_content_is_preserved(self):
        body = "### Fixed\n- Pr\u00e9server les donn\u00e9es."
        self.assertEqual(
            release_notes.extract_release_notes(
                "## [2.0.0] - 2026-10-18\n" + body, "2.0.0"
            ),
            body,
        )

    def run_cli(self, directory, *args):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--tag",
                "v2.0.0",
                "--output",
                "notes.md",
                *args,
            ],
            cwd=directory,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_cli_generates_exact_notes_without_github_credentials(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
            result = self.run_cli(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (root / "notes.md").read_text(encoding="utf-8"),
                release_notes.extract_release_notes(CHANGELOG, "v2.0.0") + "\n",
            )

    def test_cli_failure_does_not_overwrite_existing_notes(self):
        for changelog in (None, "## [Unreleased]\n- Pending."):
            with self.subTest(changelog=changelog), TemporaryDirectory() as directory:
                root = Path(directory)
                if changelog:
                    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
                (root / "notes.md").write_text("Keep existing notes", encoding="utf-8")
                result = self.run_cli(directory)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Release notes generation failed", result.stderr)
                self.assertEqual(
                    (root / "notes.md").read_text(encoding="utf-8"),
                    "Keep existing notes",
                )

    def test_cli_comparison_uses_ancestor_tag_not_unrelated_tag(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")

            def git(*args):
                subprocess.run(
                    ["git", *args], cwd=root, check=True, capture_output=True
                )

            git("init")
            git(
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-m",
                "Initial",
            )
            git("tag", "v1.1.1")
            git(
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-m",
                "Release",
            )
            git("tag", "v2.0.0")
            git(
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-m",
                "Future",
            )
            git("tag", "v3.0.0")

            result = self.run_cli(directory, "--repository", "owner/repo")
            self.assertEqual(result.returncode, 0, result.stderr)
            notes = (root / "notes.md").read_text(encoding="utf-8")
            self.assertIn(
                "https://github.com/owner/repo/compare/v1.1.1...v2.0.0", notes
            )
            self.assertNotIn("v3.0.0", notes)

            git("tag", "-d", "v1.1.1")
            result = self.run_cli(directory, "--repository", "owner/repo")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(
                "Full changelog", (root / "notes.md").read_text(encoding="utf-8")
            )


if __name__ == "__main__":
    unittest.main()
