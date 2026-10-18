# MIT License
#
# Copyright (c) 2019 Joakim Sørensen @ludeeus
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
from datetime import date
from pathlib import Path
import re
import subprocess
from urllib.parse import quote

VERSION_PATTERN = r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
RELEASE_HEADING = re.compile(
    rf"## \[(?P<version>{VERSION_PATTERN})\] - (?P<date>\d{{4}}-\d{{2}}-\d{{2}})"
)


def normalize_tag(tag: str) -> str:
    """Accept a release tag with an optional Git ref and leading v."""
    version = tag.removeprefix("refs/tags/").removeprefix("v")
    if not re.fullmatch(VERSION_PATTERN, version):
        raise ValueError(f"Invalid release tag: {tag}")
    return version


def extract_release_notes(changelog: str, tag: str) -> str:
    """Extract exactly one dated release section, preserving its Markdown."""
    version = normalize_tag(tag)
    sections = []
    current_lines = None
    fence = None
    for line in changelog.splitlines():
        stripped = line.lstrip()
        if fence:
            if re.fullmatch(
                re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", stripped
            ):
                fence = None
        elif stripped.startswith(("```", "~~~")):
            fence = re.match(r"(`{3,}|~{3,})", stripped).group()
        elif line.startswith("## "):
            current_lines = None
            heading = RELEASE_HEADING.fullmatch(line.strip())
            if heading and heading["version"] == version:
                date.fromisoformat(heading["date"])
                current_lines = []
                sections.append(current_lines)
            continue
        if current_lines is not None:
            current_lines.append(line)

    if len(sections) != 1:
        raise ValueError(
            f"Expected exactly one '## [{version}] - YYYY-MM-DD' section; "
            f"found {len(sections)}"
        )
    notes = "\n".join(sections[0]).strip()
    visible_notes = re.sub(r"<!--.*?-->", "", notes, flags=re.DOTALL)
    if not any(
        line.strip() and not line.lstrip().startswith("#")
        for line in visible_notes.splitlines()
    ):
        raise ValueError(f"Changelog section [{version}] has no release notes")
    return notes


def previous_tag(tag: str) -> str | None:
    """Find the nearest ancestor version tag, excluding the release being built."""
    normalize_tag(tag)
    tag = tag.removeprefix("refs/tags/")
    ref = f"refs/tags/{tag}"
    tags = subprocess.check_output(
        ["git", "tag", "--merged", ref], text=True
    ).splitlines()
    candidates = [
        candidate
        for candidate in tags
        if candidate != tag and re.fullmatch(rf"v?{VERSION_PATTERN}", candidate)
    ]
    if not candidates:
        return None
    command = ["git", "describe", "--tags", "--abbrev=0"]
    for candidate in candidates:
        command.extend(["--match", candidate])
    return subprocess.check_output([*command, ref], text=True).strip()


def main() -> None:
    """Generate a notes file locally; publishing is the workflow's responsibility."""
    parser = argparse.ArgumentParser(
        description="Extract release notes from CHANGELOG.md"
    )
    parser.add_argument("--tag", required=True)
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--repository", help="owner/repo, to append a full changelog link"
    )
    parser.add_argument("--server-url", default="https://github.com")
    args = parser.parse_args()
    try:
        notes = extract_release_notes(
            args.changelog.read_text(encoding="utf-8"), args.tag
        )
        if args.repository:
            tag = args.tag.removeprefix("refs/tags/")
            previous = previous_tag(tag)
            if previous:
                compare = (
                    f"{args.server_url.rstrip('/')}/{args.repository}/compare/"
                    f"{quote(previous, safe='')}...{quote(tag, safe='')}"
                )
                notes += f"\n\n**Full changelog:** {compare}"
        args.output.write_text(notes + "\n", encoding="utf-8")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release notes generation failed: {error}\n")


if __name__ == "__main__":
    main()
