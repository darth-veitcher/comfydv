"""Generate the code reference pages and the home page (from README.md).

See: https://mkdocstrings.github.io/recipes/
"""

import re
from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

root = Path(__file__).parent.parent
src = root / "src"

for path in sorted(src.rglob("*.py")):
    module_path = path.relative_to(src).with_suffix("")
    doc_path = path.relative_to(src).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    elif parts[-1] == "__main__":
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"::: {ident}")

    mkdocs_gen_files.set_edit_path(full_doc_path, path.relative_to(root))

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())

# The site home page is README.md, so the two can never drift apart. README
# links are relative to the repository root; the site serves docs/ as its root.
REPO_BLOB = "https://github.com/darth-veitcher/comfydv/blob/main/"


def _site_link(match: re.Match[str]) -> str:
    """Make a README link work on the site: docs/ paths become site-relative,
    other repository paths become links to the file on GitHub."""
    target = match.group(1)
    if target.startswith(("http://", "https://", "#", "mailto:")):
        return match.group(0)
    if target.startswith("docs/"):
        return f"]({target.removeprefix('docs/')})"
    return f"]({REPO_BLOB}{target})"


readme = (root / "README.md").read_text(encoding="utf-8")
with mkdocs_gen_files.open("index.md", "w") as index:
    index.write(re.sub(r"\]\(([^)\s]+)\)", _site_link, readme))
mkdocs_gen_files.set_edit_path("index.md", "README.md")
