"""The workspace build (U8 plan Step 43; decision "The workspace build", performance-design
§ 2.2, P6).

    backend/.venv/bin/python scripts/u8_build_workspace.py [--frontend frontend]

1. `vite build` (the frontend's own `vite.config.ts`: the workspace shell and the three
   script-free pages) into `<frontend>/dist`. Nothing else builds: never `next build`;
2. a `.gz` copy, with Python's `gzip`, of every content-hashed file (`assets/<name>-<hash>.
   <ext>`);
3. `dist/.docsuri-build.json`, the file list the host reads (`backend.production_boundary.
   BuildManifest`): `{"version": 1, "files": [{"path", "sha256", "size",
   "contentHashed"}]}`, every file of the build but the source maps and the `.gz` copies;
4. the first-load budget: the scripts and styles `index.html` loads at once (its module
   entry, its module preloads and its stylesheets), measured compressed, fail the build
   above 300 KB of scripts or 50 KB of styles. The budget is never raised to pass.

One JSON result is printed; the exit code is 1 when the build or the budget fails.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ".docsuri-build.json"
SCRIPT_BUDGET = 300 * 1000
STYLE_BUDGET = 50 * 1000
BUILD_SECONDS = 240
# Vite's content-hashed output names: `<name>-<hash>.<ext>` under `assets/`.
HASHED = re.compile(r"assets/[A-Za-z0-9_.-]+-[A-Za-z0-9_-]{8,}\.(?:js|css|woff2?|png|svg|webp)")
EXCLUDED = (".map", ".gz")


class BuildRefused(RuntimeError):
    """A fixed reason; the build's own output stays in its log."""


def run_vite(frontend: Path) -> dict:
    """`vite build` through the repository's pinned pnpm, never `next build`."""
    completed = subprocess.run(
        ["corepack", "pnpm@9.15.9", "--dir", str(frontend), "exec", "vite", "build"],
        cwd=ROOT, capture_output=True, text=True, timeout=BUILD_SECONDS, check=False,
        env={**{key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR")
                if key in os.environ}, "CI": "true", "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0"},
    )
    if completed.returncode != 0:
        raise BuildRefused("vite build failed")
    return {"command": "vite build"}


def listed(dist: Path) -> list[Path]:
    files = []
    for path in sorted(dist.rglob("*")):
        if path.is_symlink():
            raise BuildRefused("the build holds a link")
        if path.is_file() and path.name != MANIFEST and not path.name.endswith(EXCLUDED):
            files.append(path)
    return files


def content_hashed(relative: str) -> bool:
    return HASHED.fullmatch(relative) is not None


def compress(path: Path) -> int:
    raw = path.read_bytes()
    packed = gzip.compress(raw, compresslevel=9, mtime=0)
    target = path.with_name(path.name + ".gz")
    target.write_bytes(packed)
    return len(packed)


class FirstLoad(HTMLParser):
    """The scripts and styles a page loads at once."""

    def __init__(self):
        super().__init__()
        self.scripts: list[str] = []
        self.styles: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.scripts.append(values["src"])
        if tag == "link" and values.get("href"):
            relation = values.get("rel", "")
            if relation == "stylesheet":
                self.styles.append(values["href"])
            elif relation == "modulepreload":
                self.scripts.append(values["href"])


def first_load(dist: Path, sizes: dict[str, int]) -> dict:
    parser = FirstLoad()
    parser.feed((dist / "index.html").read_text())

    def measured(hrefs: list[str]) -> int:
        total = 0
        for href in dict.fromkeys(hrefs):
            relative = href.lstrip("/")
            if relative not in sizes:
                raise BuildRefused("the first load names a file the build lacks")
            total += sizes[relative]
        return total

    scripts, styles = measured(parser.scripts), measured(parser.styles)
    return {"scriptBytesCompressed": scripts, "styleBytesCompressed": styles,
            "scriptBudget": SCRIPT_BUDGET, "styleBudget": STYLE_BUDGET,
            "withinBudget": scripts <= SCRIPT_BUDGET and styles <= STYLE_BUDGET}


def manifest(dist: Path) -> dict:
    """The `.gz` copies and `dist/.docsuri-build.json`; returns the first-load figures."""
    entries, compressed = [], {}
    for path in listed(dist):
        relative = path.relative_to(dist).as_posix()
        hashed = content_hashed(relative)
        raw = path.read_bytes()
        entries.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(),
                        "size": len(raw), "contentHashed": hashed})
        compressed[relative] = compress(path) if hashed else len(gzip.compress(raw, mtime=0))
    # The first-load figures come before the manifest is written, so a build that names a
    # file it lacks never leaves one.
    figures = first_load(dist, compressed)
    (dist / MANIFEST).write_text(json.dumps({"version": 1, "files": entries}, indent=1,
                                            sort_keys=True))
    return {"files": len(entries), "contentHashed": sum(e["contentHashed"] for e in entries),
            "firstLoad": figures}


INLINE_SCRIPT = "the build holds an inline script"
URL_ATTRIBUTES = frozenset({"href", "src", "action", "formaction", "xlink:href"})
URL_NOISE = str.maketrans("", "", "\t\n\r")
# A browser's URL parser strips every C0 control and space around a URL, not only the
# characters `str.strip()` treats as whitespace.
URL_EDGE = "".join(map(chr, range(0x21)))
FOREIGN = frozenset({"svg", "math"})
# `html.parser` reads these as raw text or RCDATA, while inside `<svg>` or `<math>` a
# browser parses their content as markup.
TEXT_IN_FOREIGN = frozenset({"style", "title", "textarea"})
# A browser reads these as raw text (`noscript` with scripting on), while `html.parser`
# parses their content as markup; an `iframe`'s `srcdoc` is a page of its own.
RAW_TEXT_ELSEWHERE = frozenset({"noscript", "xmp", "iframe", "noembed", "noframes",
                                "plaintext"})


class InlineScript(HTMLParser):
    """Whether a page holds an inline script (D7, csp-no-inline-script): a `<script>`
    without `src` or with non-blank text, an `on*` attribute, or a `javascript:` URL.
    Markup a browser parses differently from `html.parser` is refused outright: any
    marked section (`<![CDATA[`, which a browser ends at the first `>`); a `<style>`,
    `<title>` or `<textarea>` inside `<svg>` or `<math>` (whose children a browser parses
    as markup); and any `<noscript>`, `<xmp>`, `<iframe>`, `<noembed>`, `<noframes>` or
    `<plaintext>` (raw text to a browser, markup to `html.parser`). The two foreign
    namespaces are tracked apart: a browser ignores an end tag of the other namespace,
    so `</svg>` never closes an open `<math>`."""

    def __init__(self):
        super().__init__()
        self.found = False
        self._in_script = False
        self._foreign = dict.fromkeys(FOREIGN, 0)

    def handle_starttag(self, tag, attrs):
        self._attributes(tag, attrs)
        if tag in FOREIGN:
            self._foreign[tag] += 1
        if tag in TEXT_IN_FOREIGN and any(self._foreign.values()):
            self.found = True
        if tag in RAW_TEXT_ELSEWHERE:
            self.found = True
        if tag == "script":
            self._in_script = True
            if not dict(attrs).get("src"):
                self.found = True

    def handle_startendtag(self, tag, attrs):
        self._attributes(tag, attrs)
        if tag == "script" and not dict(attrs).get("src"):
            self.found = True

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = False
        if tag in FOREIGN and self._foreign[tag]:
            self._foreign[tag] -= 1

    def handle_data(self, data):
        if self._in_script and data.strip():
            self.found = True

    def unknown_decl(self, data):
        self.found = True

    def _attributes(self, tag, attrs):
        for name, value in attrs:
            if name.startswith("on"):
                self.found = True
            if name in URL_ATTRIBUTES and value is not None and (
                    value.strip(URL_EDGE).translate(URL_NOISE).lower()
                    .startswith("javascript:")):
                self.found = True


def refuse_inline_scripts(dist: Path) -> None:
    """Every `dist/**/*.html` is parsed; any inline script refuses the build."""
    for page in sorted(dist.rglob("*.html")):
        parser = InlineScript()
        parser.feed(page.read_text())
        parser.close()
        if parser.found:
            raise BuildRefused(INLINE_SCRIPT)


def build(frontend: Path, *, run=run_vite) -> dict:
    run(frontend)
    dist = frontend / "dist"
    if not (dist / "index.html").is_file():
        raise BuildRefused("the build has no workspace shell")
    for page in ("privacy.html", "terms.html", "maintenance.html"):
        if not (dist / page).is_file():
            raise BuildRefused("the build lacks a script-free page")
    # A refused build leaves no manifest, so nothing can serve it.
    (dist / MANIFEST).unlink(missing_ok=True)
    refuse_inline_scripts(dist)
    try:
        result = manifest(dist)
        if not result["firstLoad"]["withinBudget"]:
            raise BuildRefused("the first load passes its budget")
    except BaseException:
        (dist / MANIFEST).unlink(missing_ok=True)
        raise
    return {"state": "built", **result}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="u8_build_workspace.py")
    parser.add_argument("--frontend", type=Path, default=ROOT / "frontend")
    args = parser.parse_args(argv)
    try:
        result = build(args.frontend.resolve())
    except (BuildRefused, OSError, subprocess.SubprocessError) as error:
        reason = str(error) if isinstance(error, BuildRefused) else type(error).__name__
        print(json.dumps({"state": "refused", "reason": reason}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
