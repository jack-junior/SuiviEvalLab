"""Word version of the guide, built from the same Markdown files as the site.

    python tools/docs/build_word.py [output.docx]

Needs pandoc (3.1 or newer) and python-docx. The pages are taken in the order of
the site navigation (mkdocs.yml); links between pages become plain text, images
keep their caption paragraph. The result gets a cover page, a table of contents
(updated when the document is opened in Word), numbered headings, page numbers
and the project's styles.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "docs" / "guide"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "SuiviEvalLab-documentation.docx"
AUTHORS = ["GAYI Komi Selassi", "SANOUSSI Moudjibou"]
BLUE = RGBColor(0x1D, 0x4F, 0x91)
INK = RGBColor(0x1F, 0x1E, 0x1C)
MUTED = RGBColor(0x5F, 0x5C, 0x57)
MONTHS = "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split()


def version() -> str:
    text = (ROOT / "engine" / "python" / "sme_engine" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def pages() -> list[Path]:
    """Markdown files in the order of the site navigation."""
    nav = (ROOT / "mkdocs.yml").read_text(encoding="utf-8").split("\nnav:", 1)[1]
    return [GUIDE / m for m in re.findall(r":\s*([\w/.-]+\.md)\s*$", nav, flags=re.M)]


def markdown() -> str:
    parts = []
    for page in pages():
        text = page.read_text(encoding="utf-8")
        # Images: paths relative to docs/guide, whatever the page depth.
        text = re.sub(r"\]\((?:\.\./)*img/", "](img/", text)
        # Links between pages are plain text in the printed document.
        text = re.sub(r"\[([^\]]+)\]\((?!https?:)[^)]+\.md(?:#[^)]*)?\)", r"\1", text)
        parts.append(text.strip())
    return "\n\n".join(parts) + "\n"


def reference_doc(path: Path) -> None:
    """Pandoc's default styles, set to the project's look."""
    with path.open("wb") as f:
        cmd = ["pandoc", "--print-default-data-file", "reference.docx"]
        f.write(subprocess.run(cmd, check=True, capture_output=True).stdout)
    doc = Document(str(path))
    # By name, as pandoc spells them (python-docx would translate "Heading 1").
    styles = {s.name: s for s in doc.styles}
    for name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        if name in styles:
            st = styles[name]
            st.font.name = "Calibri"
            st.font.size = Pt(10.5)
            st.font.color.rgb = INK
            st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
            if name != "Compact":
                st.paragraph_format.space_after = Pt(6)
                st.paragraph_format.line_spacing = 1.12
    headings = (("Heading 1", 18, 18), ("Heading 2", 13.5, 14), ("Heading 3", 11.5, 10), ("Title", 26, 0))
    for name, size, before in headings:
        st = styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = name != "Title"
        st.font.color.rgb = BLUE
        st.font.italic = False
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(6)
        rpr = st.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            fonts.set(qn(attr), "Calibri")
        for theme in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            fonts.attrib.pop(qn(theme), None)
    styles["Heading 1"].paragraph_format.page_break_before = True
    for name in ("Source Code", "Verbatim Char"):
        if name in styles:
            styles[name].font.size = Pt(8)
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    doc.save(str(path))


def shade(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def borders(table) -> None:
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "4")
        e.set(qn("w:color"), "C9C6BF")
        b.append(e)
    tblPr.append(b)


def field(paragraph, instruction: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, instruction), ("separate", None), (None, placeholder), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
            if kind == "begin":
                el.set(qn("w:dirty"), "true")
            run._r.append(el)
        elif text is not None:
            if text == instruction:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = f" {text} "
            else:
                el = OxmlElement("w:t")
                el.text = text
            run._r.append(el)


def field_start(paragraph, instruction: str) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    for el in (begin, instr, sep):
        run._r.append(el)


def field_end(paragraph) -> None:
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(end)


def page_numbers(pdf: Path, entries: list[tuple[int, str]]) -> dict[str, int]:
    """Page of each heading in a rendering of the document, found in order after the table of contents."""
    count = int(
        re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout)[1]
    )
    texts = [
        subprocess.run(
            ["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(pdf), "-"], capture_output=True, text=True
        ).stdout
        for n in range(1, count + 1)
    ]
    found, page = {}, 0
    # Skip the cover and the table of contents (lines ending with dot leaders).
    while page < count and ("Sommaire" in texts[page] or page == 0 or re.search(r"\.{5,}", texts[page])):
        page += 1
    for _, text in entries:
        number, title = text.split("  ", 1)
        pattern = re.compile(rf"^\s*{re.escape(number)}\s+{re.escape(title[:25])}", re.M)
        for n in range(page, count):
            if pattern.search(texts[n].replace("\u2019", "'").replace("'", "\u2019")) or pattern.search(texts[n]):
                found[text] = n + 1
                page = n
                break
    return found


def finish(src: Path, dst: Path, today: str, page_of: dict[str, int] | None = None) -> list[tuple[int, str]]:
    """Styles, cover page, table of contents and properties. Returns the TOC entries (level, text)."""
    doc = Document(str(src))
    entries = [
        (int(p.style.name[-1]), p.text.replace("\t", "  "))
        for p in doc.paragraphs
        if p.style.name in ("Heading 1", "Heading 2")
    ]
    body = doc.element.body

    # Tables: header row in the project blue, light borders, full width.
    for table in doc.tables:
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        borders(table)
        for c in table.rows[0].cells:
            shade(c, "1D4F91")
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    r.font.bold = True
        for row in table.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    p.paragraph_format.space_after = Pt(2)
                    for r in p.runs:
                        r.font.size = Pt(9.5)

    # Tall images (diagrams) are reduced to fit on a page with their caption.
    for shape in doc.inline_shapes:
        if shape.height > Cm(18):
            ratio = Cm(18) / shape.height
            shape.height = Cm(18)
            shape.width = int(shape.width * ratio)

    # Figure captions (an italic paragraph right after an image): small, grey, centred.
    for p in doc.paragraphs:
        if p.runs and all(r.italic for r in p.runs if r.text.strip()) and p.text.startswith("Figure "):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(12)
            for r in p.runs:
                r.font.size = Pt(9)
                r.font.color.rgb = MUTED
        if p._p.xpath(".//pic:pic"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.keep_with_next = True

    # Cover page and table of contents, before the first heading.
    first = body[0]
    cover = []

    def para(text="", size=11, bold=False, color=INK, align=WD_ALIGN_PARAGRAPH.LEFT, before=0, after=6):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        if text:
            r = p.add_run(text)
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
        cover.append(p._p)
        return p

    logo = ROOT / "apps" / "desktop" / "build-resources" / "icon.png"
    p = para(before=60)
    p.add_run().add_picture(str(logo), width=Cm(2.6))
    para("SuiviEvalLab", 34, True, BLUE, before=18, after=4)
    para("Documentation de l'application", 18, False, INK, after=4)
    para(f"Version {version()}", 12, False, MUTED, after=60)
    para("Présentation, architecture, manuel de l'application, contribution et tests", 11, False, MUTED, after=120)
    para("Auteurs", 9, True, MUTED, after=2)
    for a in AUTHORS:
        para(a, 12, False, INK, after=2)
    para(today, 11, False, MUTED, before=18)
    p = para("Licence GPL-3.0-or-later. Dépôt : github.com/jack-junior/SuiviEvalLab", 9, False, MUTED, before=6)
    p.runs[0].add_break(WD_BREAK.PAGE)
    p = para("Sommaire", 18, True, BLUE, after=12)
    # The TOC is a real Word field (it can be updated in Word), filled in advance with
    # the page numbers of the first rendering so it reads correctly as soon as it opens.
    toc_paras = []
    for level, text in entries:
        p = para(after=2 if level == 2 else 4, before=0 if level == 2 else 6)
        p.paragraph_format.left_indent = Cm(0 if level == 1 else 0.7)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(16.6), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        toc_paras.append((p, level, text))
    for i, (p, level, text) in enumerate(toc_paras):
        if i == 0:
            field_start(p, 'TOC \\o "1-2" \\h \\z \\u')
        r = p.add_run(f"{text}\t{(page_of or {}).get(text, 0) or '00'}")
        r.font.size = Pt(10.5 if level == 1 else 10)
        r.font.bold = level == 1
        if i == len(toc_paras) - 1:
            field_end(p)
    for el in cover:
        first.addprevious(el)

    # Page numbers in the footer, document properties.
    sec = doc.sections[0]
    sec.different_first_page_header_footer = True
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run(f"SuiviEvalLab {version()}, documentation    ")
    r.font.size = Pt(8.5)
    r.font.color.rgb = MUTED
    field(fp, "PAGE", "1")

    props = doc.core_properties
    props.title = "SuiviEvalLab, documentation de l'application"
    props.subject = f"Version {version()}"
    props.author = "; ".join(AUTHORS)
    props.last_modified_by = AUTHORS[0]
    props.keywords = "suivi-évaluation; S&E; indicateurs; enquêtes"
    props.comments = ""
    props.category = "Documentation"
    props.language = "fr-FR"
    doc.save(str(dst))
    return entries


def main() -> None:
    d = date.today()
    today = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / "guide.md"
        src.write_text(markdown(), encoding="utf-8")
        ref = tmp / "reference.docx"
        reference_doc(ref)
        subprocess.run(
            [
                "pandoc",
                str(src),
                "-f",
                "markdown-implicit_figures+pipe_tables",
                "-t",
                "docx",
                "--reference-doc",
                str(ref),
                "--resource-path",
                str(GUIDE),
                "--number-sections",
                "--dpi",
                "180",
                "-o",
                str(raw := tmp / "raw.docx"),
            ],
            check=True,
        )
        # Two passes: render once to know on which page each heading falls.
        draft = tmp / "draft.docx"
        entries = finish(raw, draft, today)
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(draft)],
            check=True,
            capture_output=True,
        )
        pages = page_numbers(tmp / "draft.pdf", entries)
        missing = [t for _, t in entries if t not in pages]
        if missing:
            print(f"Page not found for {len(missing)} headings, for example {missing[0]}")
        finish(raw, OUT, today, pages)
    print(OUT)


if __name__ == "__main__":
    main()
