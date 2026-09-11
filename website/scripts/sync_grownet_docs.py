"""Synchronize the two public GrowNet references; preserve the website shell.

Requires Markdown 3.10.3. Only the four named source documents are copied.
Existing numbered-section fragment URLs remain stable for inbound links.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import markdown


DOCUMENTS = (
    (
        "GrowNet_Journal_Reference_Final", "grownet-journal-reference", "grownet.html", 1,
        (
            "origin-motivation", "high-level-vision", "structural-vocabulary",
            "growth-rules", "connectivity-loops", "pruning-dormancy", "memory-paths",
            "emotions-regulation", "prototype-path", "research-observations",
            "open-questions", "concise-definition", "future-updates",
            "appendix-golden-rule", "appendix-knowledge-units",
        ),
    ),
    (
        "GrowNet_Formal_Spec_Final", "grownet-formal-spec", "grownet-formal-spec.html", 2,
        (
            "specification-posture", "architectural-thesis", "golden-rule", "core-entities",
            "resource-economics", "learning-model", "connectivity-routing",
            "tick-state-semantics", "formal-growth-rules", "feedback-loops",
            "regions-specialization", "pruning-dormancy", "memory-access-paths",
            "knowledge-units", "prototype-roadmap", "long-term-direction", "non-goals",
            "open-questions", "concise-formal-definition", "appendix-minimal-invariants",
            "appendix-relationship-journal",
        ),
    ),
)


def render_reference(source: str, section_level: int, section_ids: tuple[str, ...]) -> tuple[str, str]:
    heading_pattern = re.compile(rf"^{'#' * section_level} (.+)$", re.MULTILINE)
    headings = list(heading_pattern.finditer(source))
    if section_level == 1:
        headings = headings[1:]  # The document title already lives in the page hero.
    if len(headings) != len(section_ids):
        raise ValueError("Source section structure changed; review stable section URLs before syncing")

    # Include source metadata and its exact summary, without duplicating the page h1.
    preamble = source[:headings[0].start()].split("\n", 1)[1]
    preamble_html = markdown.markdown(preamble, extensions=["tables", "fenced_code"])
    sections = [f'<section id="document-posture">\n<h2>Document posture</h2>\n{preamble_html}\n</section>']
    main_links = ['<li><a href="#document-posture">Document posture</a></li>']
    appendix_links = []
    for section_index, (heading, section_id) in enumerate(zip(headings, section_ids)):
        section_end = headings[section_index + 1].start() if section_index + 1 < len(headings) else len(source)
        section_source = source[heading.start():section_end]
        # Journal h1 sections become h2, its h2 cards become h3, etc.
        if section_level == 1:
            section_source = re.sub(r"^(#{1,5}) ", r"#\1 ", section_source, flags=re.MULTILINE)
        rendered = markdown.markdown(section_source, extensions=["tables", "fenced_code"])
        rendered = rendered.replace(
            "<table>",
            '<div class="grownet-table-wrap" tabindex="0" role="region" aria-label="Scrollable reference table">\n<table>',
        )
        rendered = rendered.replace("</table>", "</table>\n</div>")
        rendered = rendered.replace(
            "<pre>", '<pre tabindex="0" role="region" aria-label="Code or text diagram">',
        )
        sections.append(f'<section id="{section_id}">\n{rendered}\n</section>')
        label = html.escape(heading.group(1))
        link = f'<li><a href="#{section_id}">{label}</a></li>'
        (appendix_links if section_id.startswith("appendix-") else main_links).append(link)
    article = "\n\n".join(sections) + '\n<p class="grownet-toplink"><a href="#top">Back to top</a></p>'
    toc = (
        "<h2>On this page</h2>\n"
        "<p>The full reference is synchronized from its canonical document's Markdown mirror. "
        "The Word editions jointly define the architecture.</p>\n<ol>\n"
        + "\n".join(main_links) + "\n</ol>\n<ul>\n" + "\n".join(appendix_links) + "\n</ul>"
    )
    return article, toc


def replace_inside(page: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, lambda match: match[1] + "\n" + replacement + "\n" + match[3], page, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected one website content region; found {count}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grownet-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Check synchronization without writing")
    arguments = parser.parse_args()
    website_root = Path(__file__).resolve().parents[1]
    source_root = arguments.grownet_root.resolve() / "docs"
    expected_files: dict[Path, bytes] = {}
    for source_name, asset_name, page_name, section_level, section_ids in DOCUMENTS:
        source_text = (source_root / f"{source_name}.md").read_text(encoding="utf-8")
        article, toc = render_reference(source_text, section_level, section_ids)
        page_path = website_root / page_name
        page = page_path.read_text(encoding="utf-8")
        page = replace_inside(page, r'(<article class="grownet-paper grownet-prose">)(.*?)(</article>)', article)
        page = replace_inside(page, r'(<aside class="grownet-toc"[^>]*>)(.*?)(</aside>)', toc)
        expected_files[page_path] = page.encode("utf-8")
        for suffix in ("md", "docx"):
            expected_files[website_root / "assets" / "docs" / f"{asset_name}.{suffix}"] = (
                source_root / f"{source_name}.{suffix}"
            ).read_bytes()
    differences = []
    for path, expected in expected_files.items():
        actual = path.read_bytes() if path.exists() else None
        # Git CRLF normalization is irrelevant to text synchronization.
        if actual is not None and path.suffix != ".docx":
            actual = actual.replace(b"\r\n", b"\n")
            expected = expected.replace(b"\r\n", b"\n")
        if actual != expected:
            differences.append(path.relative_to(website_root).as_posix())
            if not arguments.check:
                path.write_bytes(expected)
    if arguments.check and differences:
        print("Out of sync: " + ", ".join(differences))
        return 1
    print(f"{'Checked' if arguments.check else 'Synchronized'} {len(expected_files)} reference pages/downloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
