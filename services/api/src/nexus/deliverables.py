"""Render drafted work product into the file the lawyer asked for.

Agents write in a small, predictable subset of Markdown: headings (#, ##,
###), paragraphs, bullet and numbered lists, **bold**, *italic*, and pipe
tables. Source markers like [S3] become superscript numbers that point to a
Sources section listing the document, location and exact quote.
"""

import io
import re

from docx import Document
from docx.enum.text import WD_BREAK
from docx.shared import Pt

MARKER = re.compile(r"\[(S\d+)\]")
_INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|\[S\d+\])")


def _add_inline(paragraph, text: str, numbers: dict[str, int]) -> None:
    for piece in _INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            paragraph.add_run(piece[2:-2]).bold = True
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            paragraph.add_run(piece[1:-1]).italic = True
        elif MARKER.fullmatch(piece):
            n = numbers.get(piece[1:-1])
            run = paragraph.add_run(f"[{n}]" if n else "[unverified]")
            run.font.superscript = bool(n)
        else:
            paragraph.add_run(piece)


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue  # the |---|---| separator row
        rows.append(cells)
    return rows


def number_sources(content: str, verified: set[str]) -> dict[str, int]:
    """Number verified sources in order of first use."""
    numbers: dict[str, int] = {}
    for sid in MARKER.findall(content):
        if sid in verified and sid not in numbers:
            numbers[sid] = len(numbers) + 1
    return numbers


def to_docx(content: str, sources: list[dict]) -> bytes:
    verified = {s["id"]: s for s in sources if s.get("verified")}
    numbers = number_sources(content, set(verified))
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(11)

    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            rows = _table_rows(block)
            if rows:
                width = max(len(r) for r in rows)
                table = doc.add_table(rows=0, cols=width)
                table.style = "Table Grid"
                for r, cells in enumerate(rows):
                    row_cells = table.add_row().cells
                    for c in range(width):
                        paragraph = row_cells[c].paragraphs[0]
                        _add_inline(paragraph, cells[c] if c < len(cells) else "", numbers)
                        if r == 0:
                            for run in paragraph.runs:
                                run.bold = True
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            doc.add_heading(MARKER.sub("", heading.group(2)).strip(), level=len(heading.group(1)))
        elif re.match(r"^[-*]\s+", stripped):
            _add_inline(doc.add_paragraph(style="List Bullet"), re.sub(r"^[-*]\s+", "", stripped), numbers)
        elif re.match(r"^\d+[.)]\s+", stripped):
            _add_inline(doc.add_paragraph(style="List Number"), re.sub(r"^\d+[.)]\s+", "", stripped), numbers)
        else:
            _add_inline(doc.add_paragraph(), stripped, numbers)
        i += 1

    if numbers:
        doc.add_paragraph().add_run().add_break(WD_BREAK.LINE)
        doc.add_heading("Sources", level=2)
        for sid, n in sorted(numbers.items(), key=lambda kv: kv[1]):
            s = verified[sid]
            where = s.get("document", "Document")
            if s.get("page") and s.get("location_label"):
                where += f", {s['location_label']} {s['page']}"
            p = doc.add_paragraph()
            p.add_run(f"[{n}] {where}: ").bold = True
            p.add_run(f"“{s['quote']}”")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def to_xlsx(content: str) -> bytes:
    """Every Markdown table becomes a sheet; text outside tables goes to a Notes sheet."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    wb.remove(wb.active)
    notes, block, title = [], [], None
    tables: list[tuple[str, list[list[str]]]] = []
    for line in content.splitlines() + [""]:
        if line.strip().startswith("|"):
            block.append(line)
            continue
        if block:
            tables.append((title or f"Table {len(tables) + 1}", _table_rows(block)))
            block = []
        heading = re.match(r"^#{1,3}\s+(.*)$", line.strip())
        if heading:
            title = heading.group(1).strip()
        elif line.strip():
            notes.append(MARKER.sub("", line.strip()))
    for name, rows in tables:
        sheet = wb.create_sheet(re.sub(r"[\[\]:*?/\\]", "", name)[:31] or "Sheet")
        for r, cells in enumerate(rows):
            sheet.append([MARKER.sub("", c).strip() for c in cells])
            if r == 0:
                for cell in sheet[1]:
                    cell.font = Font(bold=True)
    if notes or not tables:
        sheet = wb.create_sheet("Notes")
        for n in notes:
            sheet.append([n])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def render(filename: str, content: str, sources: list[dict]) -> tuple[bytes, str]:
    """Returns (file bytes, content type) for the requested filename."""
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return to_xlsx(content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith((".md", ".txt")):
        verified = {s["id"]: s for s in sources if s.get("verified")}
        numbers = number_sources(content, set(verified))
        body = MARKER.sub(lambda m: f"[{numbers[m.group(1)]}]" if m.group(1) in numbers else "[unverified]", content)
        if numbers:
            body += "\n\n## Sources\n\n" + "\n".join(
                f"[{n}] {verified[sid].get('document', 'Document')}: “{verified[sid]['quote']}”"
                for sid, n in sorted(numbers.items(), key=lambda kv: kv[1]))
        return body.encode(), "text/markdown"
    return to_docx(content, sources), (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
