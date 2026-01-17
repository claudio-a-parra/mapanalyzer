#!/usr/bin/env python3
"""
Generate root/index.html from root/index_template.html by replacing:

    <li>__ITEMS_PLACEHOLDER__</li>

with dynamically generated HTML listing example outputs.

Run:
if 
    python3 root/fill_template.py

(or from inside site/):
    python3 fill_template.py
"""

from __future__ import annotations

import sys
import html
from pathlib import Path
from typing import Iterable

EXAMPLES_SUBDIR_DEFAULT = "__EXPORT"
EXAMPLES_SUBDIR = EXAMPLES_SUBDIR_DEFAULT
INDEX_TEMPLATE = "index_template.html"
INDEX = "index.html"
HTML_PLACEHOLDER = "<div>__ITEMS_PLACEHOLDER__</div>"


def validate_root(given_root) -> Path:
    """
    The directory given to this tool must have two elements:
    - "index_template.html": The html template that this tool fills up.
    - EXAMPLES_SUBDIR      : The sub-directory with the examples' outputs.

    If the default name of the examples sub-dir is not found, then try
    "examples", and set the global variable to that.
    """
    root_path = Path(given_root)
    global EXAMPLES_SUBDIR
    
    if (root_path / EXAMPLES_SUBDIR).is_dir() and \
       (root_path / INDEX_TEMPLATE).is_file():
        return root_path.resolve()

    EXAMPLES_SUBDIR = "examples"

    if (root_path / EXAMPLES_SUBDIR).is_dir() and \
       (root_path / INDEX_TEMPLATE).is_file():
        return root_path.resolve()
    
    raise FileNotFoundError(
        f"Given root path '{given_root}' does not look right. I was expecting to find:\n"
        f"- either: {given_root}/{{{EXAMPLES_SUBDIR_DEFAULT},{EXAMPLES_SUBDIR}}}/\n"
        f"- and   : {given_root}/{INDEX_TEMPLATE}"
    )

def href(p: Path, *, root: Path) -> str:
    # relative link from site root
    return p.relative_to(root).as_posix()

def human_size(nbytes: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB"]
    v = float(nbytes)
    u = 0
    while v >= 1024.0 and u < len(units) - 1:
        v /= 1024.0
        u += 1

    if units[u] == "B":
        return f"{int(v)}B"

    if v.is_integer():
        s = str(int(v))
    else:
        s = f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{s}{units[u]}"

def kind_order(p: Path) -> int:
    ext = p.suffix.lower()
    if ext == ".map":
        return 0
    if ext == ".json":
        return 1
    if ext == ".pdf":
        return 2
    return 3

def iter_example_files(example_dir: Path) -> Iterable[Path]:
    # Files live under these subdirectories (some may be absent).
    for sub in ("maps", "pdata", "plots", "aggr"):
        d = example_dir / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file():
                yield p

def render_items_html(*, root: Path, examples_base: Path) -> str:
    examples: list[str] = []

    example_dirs = sorted(
        (p for p in examples_base.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )

    for exdir in example_dirs:
        exname = exdir.name.title()

        files = list(iter_example_files(exdir))
        files.sort(key=lambda p: (kind_order(p), p.name))

        file_lis: list[str] = []
        for p in files:
            size = human_size(p.stat().st_size)
            display = p.name.removeprefix(f"{exname}_")

            file_lis.append(
                '<li class="file-item">'
                f'<span class="file-size">{html.escape(size)}</span> '
                f'<a class="file-name" href="{html.escape(href(p, root=root))}">{html.escape(display)}</a>'
                "</li>"
            )

        file_list = ('<ul class="file-list">\n' +
                    '\n'.join(file_lis) + '\n'
                    '</ul>')
        examples.append('<div class="example">\n'
                        f'<h2 class="example-title">{html.escape(exname)}</h2>\n'
                        f'{file_list}\n'
                        '</div>')

    return '\n'.join(examples)

def main() -> int:
    if len(sys.argv) >= 2:
        given_root_str = sys.argv[1] 
    else:
        given_root_str = Path(__file__).resolve().parent
        
    root = validate_root(given_root_str)
    base = root / EXAMPLES_SUBDIR

    template_path = root / INDEX_TEMPLATE
    output_path = root / INDEX

    template = template_path.read_text(encoding="utf-8")

    if HTML_PLACEHOLDER not in template:
        raise ValueError(f"HTML placeholder '{HTML_PLACEHOLDER!r}'not found in {template_path}.")

    items_html = render_items_html(root=root, examples_base=base)
    rendered = template.replace(HTML_PLACEHOLDER, items_html)

    output_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

