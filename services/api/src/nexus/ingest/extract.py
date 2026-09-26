"""Pull text out of uploaded files, page by page.

PDFs keep their real page numbers. Word and text files have no pages, so
everything is page 1 and passages are located by paragraph instead.
"""

import io
from dataclasses import dataclass

from docx import Document as DocxDocument
from pypdf import PdfReader

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT = "text/plain"
SUPPORTED = {PDF: ".pdf", DOCX: ".docx", TEXT: ".txt"}


class UnsupportedFile(ValueError):
    pass


class UnreadableFile(ValueError):
    pass


@dataclass
class Page:
    number: int
    text: str


def content_type_for(filename: str, declared: str | None) -> str:
    lower = filename.lower()
    for content_type, suffix in SUPPORTED.items():
        if lower.endswith(suffix):
            return content_type
    if declared in SUPPORTED:
        return declared
    raise UnsupportedFile("Only PDF, Word (.docx) and plain-text files can be uploaded.")


def extract(data: bytes, content_type: str) -> list[Page]:
    if content_type == PDF:
        return _pdf(data)
    if content_type == DOCX:
        return _docx(data)
    if content_type == TEXT:
        return [Page(1, data.decode("utf-8", errors="replace"))]
    raise UnsupportedFile(content_type)


def _pdf(data: bytes) -> list[Page]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise UnreadableFile("This PDF is password-protected. Remove the password and upload it again.")
        pages = [Page(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    except UnreadableFile:
        raise
    except Exception as exc:  # pypdf raises a wide range of parse errors
        raise UnreadableFile(f"This PDF could not be read ({exc.__class__.__name__}).") from exc
    if not any(p.text.strip() for p in pages):
        raise UnreadableFile(
            "This PDF has no text layer (it is probably a scan). Run it through OCR and upload it again."
        )
    return pages


def _docx(data: bytes) -> list[Page]:
    try:
        document = DocxDocument(io.BytesIO(data))
    except Exception as exc:
        raise UnreadableFile("This Word file could not be opened.") from exc
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for table_row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in table_row.cells))
    return [Page(1, "\n\n".join(parts))]
