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
import os
import html
import pypandoc
from pathlib import Path
from typing import Iterable

EXAMPLES_SUBDIR_DEFAULT = "__EXPORT"
EXAMPLES_SUBDIR = EXAMPLES_SUBDIR_DEFAULT
INDEX_TEMPLATE = "index_template.html"
INDEX = "index.html"
HTML_PLACEHOLDER = "<div>__ITEMS_PLACEHOLDER__</div>"
BASELINK = "https://github.com/parra-ca/mapanalyzer/tree/main/examples/"
SUBDIRS = ("maps", "pdata", "plots", "aggr")


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


def drop_last_line(md: str) -> str:
    """remove the last (real) Markdown line"""    
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    lines = md.strip().split("\n")
    lines = lines[:-1]
    return "\n".join(lines) + "\n"


def files_by_subdir(example_dir: Path) -> dict[str, list[Path]]:
    """return {'maps' -> [files in map]), 'pdata' -> ..., }"""
    grouped: dict[str, list[Path]] = {}
    for sub in SUBDIRS:
        d = example_dir / sub
        if not d.is_dir():
            continue
        files = [p for p in d.rglob("*") if p.is_file()]
        if files:
            files.sort()
            grouped[sub] = files
    return grouped


def render_file_groups_html(*, example_dir: Path, root: Path) -> str:
    grouped = files_by_subdir(example_dir)
    if not grouped:
        return ""

    kind_lists: list[str] = []
    for kind_name, kind_files in grouped.items():
        this_kind_items: list[str] = []
        for p in kind_files:
            size = human_size(p.stat().st_size)
            display = p.name
            this_kind_items.append(
                '<li class="file-item">'
                f'<span class="file-size">{html.escape(size)}</span> '
                f'<a class="file-name" href="{html.escape(href(p, root=root))}">{html.escape(display)}</a>'
                "</li>"
            )

        kind_lists.append(
            '<li class="kind-item">'
            f'<span class="kind-name">{html.escape(kind_name)}</span>\n'
            f'<ul class="file-list">\n' + "\n".join(this_kind_items) + "\n</ul>\n"
            "</li>"
        )

    return '<ul class="kind-list">\n' + "\n".join(kind_lists) + "\n</ul>\n"


def render_items_html(*, root: Path, examples_base: Path) -> str:
    examples: list[str] = []

    example_dirs = sorted(
        (p for p in examples_base.iterdir() if p.is_dir()),
        key=lambda p: p.name,
    )

    for example_dir in example_dirs:
        example_name = example_dir.name

        # create title for this example
        href_id = example_name.replace(" ", "_").lower()
        pretty_name = example_name.title()
        src_link = BASELINK + example_name
        title_html = f'<h2 id="{href_id}" class="example-title">' +\
            f'{html.escape(pretty_name)} (<a href="{src_link}">source</a>)' +\
            f'</h2>\n'

        
        # get text from README.md and inject as html
        readme_path = example_dir / "README.md"
        if readme_path.is_file():
            # last line is a link to this same page. drop it.
            readme_md = drop_last_line(
                readme_path.read_text(encoding="utf-8")
            )
            readme_html = pypandoc.convert_text(
                readme_md,
                to="html5",
                format="md",
                extra_args=["--shift-heading-level-by=2"],
            )
            readme_html = f'<div class="readme">\n{readme_html}\n</div>\n'
        else:
            readme_html = ""

        # compose list of files
        grouped_file_list_html =  render_file_groups_html(
            example_dir=example_dir,
            root=root,
        )
            
        # put all parts together for this example (in one div)
        examples.append('<div class="example">\n'
                        f'{title_html}'
                        f'{readme_html}'
                        f'{grouped_file_list_html}'
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

