"""Tests for resume text extraction (pure, no network)."""

import io

import docx
import pytest
from app.resume import extract_resume_text


def _make_docx(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for line in paragraphs:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_extract_docx() -> None:
    data = _make_docx(["Jane Doe", "Senior Engineer", "Python, FastAPI"])
    text = extract_resume_text(data, "resumes/uid/jane.docx")
    assert "Jane Doe" in text
    assert "FastAPI" in text


def test_unsupported_extension_raises() -> None:
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_resume_text(b"some bytes", "resume.txt")
